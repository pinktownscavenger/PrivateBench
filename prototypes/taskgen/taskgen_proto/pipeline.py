"""Generation -> validation -> reference replay -> grader audit -> admission."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .audit import AuditSummary, build_audit_cases, run_audit
from .common import Issue, Model, sha256_json, sha256_text
from .env import Environment, ToolCall
from .generator import GenerationRequest, GeneratorClient, build_prompt
from .grader import AssertionCompiler, compile_assertions, describe, grade
from .metering import (
    BudgetSummary, CallRecord, CostBreakdown, DispatchStopped, GenerationUnavailable,
    Guarantee, MeteredClient,
)
from .package import EvaluatorBundle, Provenance, SolverView, TaskPackage
from .policy import decide
from .proposal import ProposalParseError, ScenarioProposal, parse_proposal
from .spec import WorkloadSpec, require_approved
from .validate import static_issues

PIPELINE_VERSION = "taskgen-proto-0.1"


class CheckRecord(Model):
    name: str
    passed: bool
    detail: str = ""


class CandidateRecord(Model):
    candidate_id: str
    status: Literal["admitted", "rejected"]
    family_id: str | None
    issues: list[Issue]
    checks: list[CheckRecord]
    provenance: Provenance
    task_id: str | None = None
    audit: AuditSummary | None = None
    raw_response: str
    # Live generation only: every provider call made for this candidate,
    # including retries and failed billable calls.
    generation_calls: list[CallRecord] = []


class ReportRow(Model):
    candidate_id: str
    parent_candidate_id: str | None
    family_id: str | None
    status: str
    issue_codes: list[str]
    task_id: str | None


class AdmissionReport(Model):
    spec_id: str
    spec_version: int
    spec_sha256: str
    source: str
    generator: str | None
    model: str | None
    pipeline_version: str
    slots: int
    slots_filled: int
    unfilled_slots: list[str]
    attempted: int  # candidate records, including provider failures
    admitted: int
    rejected: int
    admitted_by_family: dict[str, int]
    rejection_codes: dict[str, int]
    audit_cases_run: int
    audit_false_accepts: int
    audit_false_rejects: int
    # Cost (None when the generator is not metered, e.g. the offline fake).
    # Reported cost and unknown-billing exposure are never summed into one figure
    # except in `committed_usd`, which is what the cap is checked against.
    metered: bool = False
    budget_mode: str | None = None
    budget_cap_usd: Decimal | None = None
    budget_guarantee: Guarantee | None = None
    budget_guarantee_note: str | None = None
    cost_total: CostBreakdown | None = None
    cost_initial_attempts: CostBreakdown | None = None
    cost_repairs: CostBreakdown | None = None
    cost_per_admitted_task: CostBreakdown | None = None
    outstanding_reservations_usd: Decimal | None = None
    committed_usd: Decimal | None = None
    committed_exceeds_cap: bool | None = None
    calls_dispatched: int | None = None
    calls_failed: int | None = None
    calls_retried: int | None = None
    unknown_billing_calls: int | None = None
    calls_without_upper_bound: int | None = None
    overruns: int | None = None
    overrun_total_usd: Decimal | None = None
    stopped_reason: str | None = None
    rows: list[ReportRow]


class GenerationRun(Model):
    records: list[CandidateRecord]
    packages: list[TaskPackage]
    report: AdmissionReport
    budget: BudgetSummary | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def evaluate_candidate(
    raw: str, spec: WorkloadSpec, provenance: Provenance,
    *, compiler: AssertionCompiler = compile_assertions,
) -> tuple[CandidateRecord, TaskPackage | None]:
    """Run every admission check on one raw generator response."""
    checks: list[CheckRecord] = []
    issues: list[Issue] = []
    family_id: str | None = None

    def done(task: TaskPackage | None = None,
             audit: AuditSummary | None = None) -> tuple[CandidateRecord, TaskPackage | None]:
        rec = CandidateRecord(
            candidate_id=provenance.candidate_id,
            status="admitted" if task is not None else "rejected",
            family_id=family_id, issues=issues, checks=checks, provenance=provenance,
            task_id=task.task_id if task else None, audit=audit, raw_response=raw)
        return rec, task

    # 1. parse + schema
    try:
        p: ScenarioProposal = parse_proposal(raw)
    except ProposalParseError as exc:
        issues.append(Issue(stage="parse", code=exc.code, message=exc.message))
        checks.append(CheckRecord(name="parse", passed=False, detail=exc.message))
        return done()
    family_id = p.family_id
    checks.append(CheckRecord(name="parse", passed=True))

    # 2. static checks incl. policy-oracle agreement
    issues += static_issues(spec, p)
    checks.append(CheckRecord(name="static", passed=not issues,
                              detail="; ".join(i.code for i in issues)))
    if issues:
        return done()
    decision = decide(spec, p.initial_state, p.request)
    assertions = compiler(p.request, decision.outcome, p.initial_state)

    # 3. replay the reference through the solver's tools from a clean state
    kw = dict(plans=spec.plan_names, resolution_codes=spec.resolution_codes)

    def replay(proc: list[ToolCall]) -> Environment:
        env = Environment(p.initial_state, **kw)
        env.run(proc)
        return env

    env = replay(p.reference_procedure)
    errors = [e for e in env.events if not e.ok]
    if errors:
        issues.append(Issue(stage="replay", code="reference_tool_error",
                            message="; ".join(f"#{e.seq} {e.tool}: {e.error}" for e in errors)))
    g = grade(env.initial_tables(), env.snapshot(), assertions)
    if not g.passed:
        issues.append(Issue(stage="replay", code="reference_replay_failed",
                            message="reference final state fails assertions: " + "; ".join(
                                f"{r.id} ({r.detail})" for r in g.results if not r.passed)))
    checks.append(CheckRecord(name="reference_replay", passed=not errors and g.passed))
    if issues:
        return done()

    # 4. repeatability
    env2 = replay(p.reference_procedure)
    same = env.state_hash() == env2.state_hash() and env.events == env2.events
    checks.append(CheckRecord(name="repeatable_replay", passed=same))
    if not same:
        issues.append(Issue(stage="replay", code="nondeterministic_replay",
                            message="two clean replays produced different state or events"))
        return done()

    # 5. grader audit
    cases, na = build_audit_cases(p.initial_state, p.request, decision.outcome,
                                  p.reference_procedure, spec.plan_names)
    audit = run_audit(p.initial_state, cases, assertions, not_applicable=na, **kw)
    for o in audit.outcomes:
        if not o.correct:
            code = "grader_false_accept" if o.actual_pass else "grader_false_reject"
            issues.append(Issue(stage="audit", code=code,
                                message=f"audit case {o.case_id} expected "
                                        f"{'pass' if o.expected_pass else 'fail'}, got "
                                        f"{'pass' if o.actual_pass else 'fail'}"))
    checks.append(CheckRecord(name="grader_audit", passed=not issues,
                              detail=f"{len(audit.outcomes)} cases, FA={audit.false_accepts}, "
                                     f"FR={audit.false_rejects}, n/a={na}"))
    if issues:
        return done(audit=audit)

    # 6. package
    solver = SolverView(task_id="", instruction=p.instruction,
                        policies=spec.solver_policy_text(),
                        tools=list(env.specs.values()))
    task_id = "tg-" + sha256_json({"solver": solver, "state": p.initial_state})[:12]
    solver = solver.model_copy(update={"task_id": task_id})
    required, forbidden = describe(assertions)
    task = TaskPackage(
        task_id=task_id, solver=solver, initial_state=p.initial_state,
        evaluator=EvaluatorBundle(
            family_id=p.family_id, expected_outcome=decision.outcome,
            decision_trace=decision.trace, request=p.request,
            required_outcomes=required, forbidden_effects=forbidden, assertions=assertions,
            reference_procedure=p.reference_procedure, audit=audit, provenance=provenance))
    return done(task, audit)


def default_plan(spec: WorkloadSpec) -> list[tuple[str, int]]:
    return [(f.id, s) for f in spec.families for s in range(1, f.target_count + 1)]


def run_generation(
    spec: WorkloadSpec, client: GeneratorClient, plan: list[tuple[str, int]] | None = None,
    *, compiler: AssertionCompiler = compile_assertions,
) -> GenerationRun:
    """Fill each (family, seed) slot, repairing up to `max_repairs` times.

    Provider failures become rejected candidate records (never dropped).
    BudgetExhausted stops all further dispatch; remaining slots stay unfilled.
    """
    require_approved(spec)
    plan = default_plan(spec) if plan is None else plan
    metered = client if isinstance(client, MeteredClient) else None
    records: list[CandidateRecord] = []
    packages: list[TaskPackage] = []
    unfilled: list[str] = []
    stopped: str | None = None
    for family_id, seed in plan:
        if stopped:
            unfilled.append(f"{family_id}/seed{seed}")
            continue
        parent: str | None = None
        feedback: list[str] = []
        lineage_cost = CostBreakdown()
        filled = False
        for revision in range(spec.generation.max_repairs + 1):
            req = GenerationRequest(spec_id=spec.spec_id, family_id=family_id, seed=seed,
                                    revision=revision, feedback=feedback)
            prompt = build_prompt(spec, req)
            cid = f"{family_id}-s{seed}-r{revision}"
            failure: GenerationUnavailable | None = None
            try:
                raw = client.complete(prompt, req)
            except GenerationUnavailable as exc:
                failure, raw = exc, ""
            calls = metered.drain_calls() if metered else []
            cost = CostBreakdown.of(calls) if metered else None
            if cost is not None:
                lineage_cost = lineage_cost + cost
            prov = Provenance(
                source="generator", candidate_id=cid, parent_candidate_id=parent,
                revision=revision, generator=client.name, model=client.model, seed=seed,
                prompt_sha256=sha256_text(prompt), response_sha256=sha256_text(raw),
                spec_id=spec.spec_id, spec_version=spec.version, spec_sha256=spec.digest(),
                pipeline_version=PIPELINE_VERSION, created_at=_now(),
                generation_cost=cost,
                lineage_generation_cost=lineage_cost if metered else None)
            if failure is not None:
                if isinstance(failure, DispatchStopped):
                    stopped = failure.message
                if calls or not isinstance(failure, DispatchStopped):
                    records.append(CandidateRecord(
                        candidate_id=cid, status="rejected", family_id=family_id,
                        issues=[Issue(stage="generation", code=failure.code,
                                      message=failure.message)],
                        checks=[CheckRecord(name="generation", passed=False,
                                            detail=failure.code)],
                        provenance=prov, raw_response="", generation_calls=calls))
                break  # no repair for an unavailable generator
            rec, task = evaluate_candidate(raw, spec, prov, compiler=compiler)
            rec = rec.model_copy(update={"generation_calls": calls})
            records.append(rec)
            if task is not None:
                packages.append(task)
                filled = True
                break
            parent = cid
            feedback = [f"[{i.code}] {i.message}" for i in rec.issues]
        if not filled:
            unfilled.append(f"{family_id}/seed{seed}")
    budget = metered.budget_summary() if metered else None
    report = build_report(spec, records, slots=len(plan), unfilled=unfilled,
                          source="generator", generator=client.name, model=client.model,
                          budget=budget)
    return GenerationRun(records=records, packages=packages, report=report, budget=budget)


def build_report(spec: WorkloadSpec, records: list[CandidateRecord], *, slots: int,
                 unfilled: list[str], source: str, generator: str | None,
                 model: str | None, budget: BudgetSummary | None = None) -> AdmissionReport:
    admitted = [r for r in records if r.status == "admitted"]
    audits = [r.audit for r in records if r.audit is not None]
    spend: dict = {}
    if budget is not None:
        def cost(rs: list[CandidateRecord]) -> CostBreakdown:
            return CostBreakdown.of(c for r in rs for c in r.generation_calls)
        total = cost(records)
        spend = dict(
            metered=True, budget_mode=budget.mode, budget_cap_usd=budget.cap_usd,
            budget_guarantee=budget.guarantee, budget_guarantee_note=budget.guarantee_note,
            cost_total=total,
            cost_initial_attempts=cost([r for r in records if r.provenance.revision == 0]),
            cost_repairs=cost([r for r in records if r.provenance.revision > 0]),
            cost_per_admitted_task=total.divided(len(admitted)) if admitted else None,
            outstanding_reservations_usd=budget.outstanding_reservations_usd,
            committed_usd=budget.committed_usd,
            committed_exceeds_cap=budget.committed_usd > budget.cap_usd,
            calls_dispatched=budget.calls_dispatched, calls_failed=budget.calls_failed,
            calls_retried=budget.calls_retried,
            unknown_billing_calls=budget.unknown_billing_calls,
            calls_without_upper_bound=budget.calls_without_upper_bound,
            overruns=budget.overruns, overrun_total_usd=budget.overrun_total_usd,
            stopped_reason=budget.stopped_reason)
    return AdmissionReport(
        spec_id=spec.spec_id, spec_version=spec.version, spec_sha256=spec.digest(),
        source=source, generator=generator, model=model, pipeline_version=PIPELINE_VERSION,
        slots=slots, slots_filled=slots - len(unfilled), unfilled_slots=unfilled,
        attempted=len(records), admitted=len(admitted), rejected=len(records) - len(admitted),
        admitted_by_family=dict(Counter(r.family_id or "?" for r in admitted)),
        rejection_codes=dict(Counter(i.code for r in records for i in r.issues)),
        audit_cases_run=sum(len(a.outcomes) for a in audits),
        audit_false_accepts=sum(a.false_accepts for a in audits),
        audit_false_rejects=sum(a.false_rejects for a in audits),
        **spend,
        rows=[ReportRow(candidate_id=r.candidate_id,
                        parent_candidate_id=r.provenance.parent_candidate_id,
                        family_id=r.family_id, status=r.status,
                        issue_codes=[i.code for i in r.issues], task_id=r.task_id)
              for r in records])


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data + "\n", encoding="utf-8")


def prepare_out_dir(out: Path) -> None:
    """Only clears a directory this tool created (marked by report.json)."""
    if out.exists() and any(out.iterdir()):
        if not (out / "report.json").exists():
            raise FileExistsError(f"{out} is non-empty and was not created by this tool")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def write_run(run: GenerationRun, out: Path) -> None:
    """Layout:
    tasks/<task_id>/solver.json        <- the only solver-visible file
    tasks/<task_id>/environment.json   <- initial state, loaded by the environment
    tasks/<task_id>/evaluator.json     <- private: reference, assertions, audit, provenance
    candidates/<candidate_id>.json     <- every candidate, admitted or rejected, with reasons
    budget.json                        <- live runs only: cap, spend, calls, stop reason
    report.json / report.md
    All of these except tasks/*/solver.json are evaluator-side.
    """
    for t in run.packages:
        d = out / "tasks" / t.task_id
        _write(d / "solver.json", t.solver_json())
        _write(d / "environment.json", t.initial_state.model_dump_json(indent=2))
        _write(d / "evaluator.json", t.evaluator.model_dump_json(indent=2))
    for r in run.records:
        _write(out / "candidates" / f"{r.candidate_id}.json", r.model_dump_json(indent=2))
    if run.budget is not None:
        _write(out / "budget.json", run.budget.model_dump_json(indent=2))
    _write(out / "report.md", render_report_md(run.report))
    _write(out / "report.json", run.report.model_dump_json(indent=2))


def render_report_md(r: AdmissionReport) -> str:
    lines = [
        f"# Admission report: {r.spec_id} v{r.spec_version}",
        "",
        f"- Source: {r.source} ({r.generator} / {r.model}); pipeline {r.pipeline_version}",
        f"- Spec sha256: `{r.spec_sha256[:16]}…`",
        f"- Slots filled: {r.slots_filled}/{r.slots}"
        + (f" (unfilled: {', '.join(r.unfilled_slots)})" if r.unfilled_slots else ""),
        f"- Attempted: {r.attempted} (admitted {r.admitted}, rejected {r.rejected})",
        f"- Grader audit: {r.audit_cases_run} cases, false accepts {r.audit_false_accepts}, "
        f"false rejects {r.audit_false_rejects}",
        *(_spend_lines(r) if r.metered else ["- Spend: not metered (offline generator)"]),
        "",
        "## Admitted by family",
        "",
        *[f"- {k}: {v}" for k, v in sorted(r.admitted_by_family.items())],
        "",
        "## Rejection reasons",
        "",
        *([f"- `{k}`: {v}" for k, v in sorted(r.rejection_codes.items())] or ["- none"]),
        "",
        "## Candidates",
        "",
        "| candidate | parent | family | status | issues | task |",
        "|---|---|---|---|---|---|",
        *[f"| {x.candidate_id} | {x.parent_candidate_id or ''} | {x.family_id or ''} | "
          f"{x.status} | {', '.join(x.issue_codes)} | {x.task_id or ''} |" for x in r.rows],
    ]
    return "\n".join(lines)


def _usd(x: Decimal | None) -> str:
    return "n/a" if x is None else f"${x:.6f}"


def _cb(c: CostBreakdown | None) -> str:
    if c is None:
        return "n/a"
    return f"reported {_usd(c.reported_usd)} + unknown-billing exposure " \
           f"{_usd(c.unknown_exposure_usd)}"


def _spend_lines(r: AdmissionReport) -> list[str]:
    return [
        f"- Budget: {_usd(r.budget_cap_usd)} ({r.budget_mode} mode) — guarantee: "
        f"**{r.budget_guarantee}**. {r.budget_guarantee_note}",
        f"- Reported cost: {_usd(r.cost_total.reported_usd if r.cost_total else None)}",
        f"- Unknown-billing exposure: "
        f"{_usd(r.cost_total.unknown_exposure_usd if r.cost_total else None)} "
        f"({r.unknown_billing_calls} call(s), counted at their reserved estimate)",
        f"- Outstanding reservations: {_usd(r.outstanding_reservations_usd)}",
        f"- Committed against budget (sum of the three): {_usd(r.committed_usd)}"
        + (" — EXCEEDS BUDGET" if r.committed_exceeds_cap else ""),
        f"- Initial attempts: {_cb(r.cost_initial_attempts)}; repairs: {_cb(r.cost_repairs)}",
        f"- Per admitted task (all paid calls incl. rejected attempts, repairs, retries, "
        f"failures): {_cb(r.cost_per_admitted_task)}",
        f"- Calls: {r.calls_dispatched} dispatched, {r.calls_failed} failed, "
        f"{r.calls_retried} retries, {r.calls_without_upper_bound} without a declared upper "
        f"bound, {r.overruns} overrun(s) totalling {_usd(r.overrun_total_usd)}",
        f"- Stopped: {r.stopped_reason or 'no'}",
    ]


def summary_json(r: AdmissionReport) -> str:
    keep = ["slots", "slots_filled", "attempted", "admitted", "rejected",
            "rejection_codes", "audit_cases_run", "audit_false_accepts", "audit_false_rejects"]
    if r.metered:
        keep += ["budget_mode", "budget_guarantee", "cost_total", "cost_repairs",
                 "cost_per_admitted_task", "outstanding_reservations_usd", "committed_usd",
                 "committed_exceeds_cap", "calls_dispatched", "calls_failed",
                 "unknown_billing_calls", "overruns", "stopped_reason"]
    return json.dumps(r.model_dump(mode="json", include=set(keep)), indent=2)
