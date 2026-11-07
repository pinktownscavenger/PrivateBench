"""Independently authored fixture: hand-labelled tasks that check the pipeline.

The fixture does not come from the generator. For each hand-written task it
checks, separately:
  1. the policy oracle agrees with the hand-written outcome label;
  2. the admission gate admits/rejects as the author expected;
  3. replaying the hand reference satisfies the author's own field
     expectations (checked directly, not via the compiled assertions);
  4. the pipeline's grader gives each hand-written solution the verdict the
     author assigned (valid alternatives pass; wrong ones fail).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml

from .common import Model, sha256_json, sha256_text
from .env import Environment, ToolCall, WorldState
from .grader import AssertionCompiler, compile_assertions, grade
from .package import Provenance
from .pipeline import PIPELINE_VERSION, CandidateRecord, evaluate_candidate
from .policy import PlanChangeRequest, decide
from .spec import Outcome, WorkloadSpec

DEFAULT_FIXTURE_PATH = (Path(__file__).resolve().parent.parent / "fixtures"
                        / "independent_tasks.yaml")


class HandExpectation(Model):
    table: str
    record_id: str
    field: str
    value: Any


class HandSolution(Model):
    id: str
    expected_verdict: Literal["pass", "fail"]
    why: str
    procedure: list[ToolCall]


class FixtureTask(Model):
    id: str
    note: str
    family_id: str
    expected_outcome: Outcome
    expected_admission: Literal["admitted", "rejected"]
    expected_rejection_codes: list[str] = []
    initial_state: WorldState
    request: PlanChangeRequest
    instruction: str
    reference_procedure: list[ToolCall]
    expected_final: list[HandExpectation] = []
    solutions: list[HandSolution] = []


class Fixture(Model):
    fixture_id: str
    authorship: str
    tasks: list[FixtureTask]


class SolutionResult(Model):
    id: str
    expected: str
    actual: str
    failed_assertions: list[str]

    @property
    def agrees(self) -> bool:
        return self.expected == self.actual


class FixtureTaskResult(Model):
    id: str
    oracle_outcome: Outcome
    oracle_agrees: bool
    admission_status: str
    admission_agrees: bool
    rejection_codes: list[str]
    expected_final_holds: bool | None
    expected_final_failures: list[str]
    solutions: list[SolutionResult]

    @property
    def disagreements(self) -> list[str]:
        out = []
        if not self.oracle_agrees:
            out.append(f"{self.id}: oracle says {self.oracle_outcome}")
        if not self.admission_agrees:
            out.append(f"{self.id}: admission {self.admission_status} {self.rejection_codes}")
        if self.expected_final_holds is False:
            out.append(f"{self.id}: hand expectations failed {self.expected_final_failures}")
        out += [f"{self.id}/{s.id}: expected {s.expected}, grader said {s.actual}"
                for s in self.solutions if not s.agrees]
        return out


class FixtureReport(Model):
    fixture_id: str
    results: list[FixtureTaskResult]
    records: list[CandidateRecord]
    disagreements: list[str]

    @property
    def all_agree(self) -> bool:
        return not self.disagreements


def load_fixture(path: str | Path = DEFAULT_FIXTURE_PATH) -> Fixture:
    with open(path, encoding="utf-8") as fh:
        return Fixture.model_validate(yaml.safe_load(fh))


def run_fixture(spec: WorkloadSpec, fixture: Fixture,
                *, compiler: AssertionCompiler = compile_assertions) -> FixtureReport:
    kw = dict(plans=spec.plan_names, resolution_codes=spec.resolution_codes)
    results: list[FixtureTaskResult] = []
    records: list[CandidateRecord] = []
    for t in fixture.tasks:
        raw = json.dumps({
            "family_id": t.family_id, "initial_state": t.initial_state.model_dump(mode="json"),
            "request": t.request.model_dump(), "instruction": t.instruction,
            "claimed_outcome": t.expected_outcome,
            "reference_procedure": [c.model_dump() for c in t.reference_procedure],
            "rationale": t.note,
        })
        prov = Provenance(
            source="independent_fixture", candidate_id=f"{fixture.fixture_id}/{t.id}",
            parent_candidate_id=None, revision=0, generator=None, model=None, seed=None,
            prompt_sha256=None, response_sha256=sha256_text(raw), spec_id=spec.spec_id,
            spec_version=spec.version, spec_sha256=spec.digest(),
            pipeline_version=PIPELINE_VERSION, created_at="fixture")
        rec, _ = evaluate_candidate(raw, spec, prov, compiler=compiler)
        records.append(rec)
        codes = sorted({i.code for i in rec.issues})

        decision = decide(spec, t.initial_state, t.request)
        assertions = compiler(t.request, decision.outcome, t.initial_state)

        holds: bool | None = None
        failures: list[str] = []
        if t.expected_admission == "admitted":
            env = Environment(t.initial_state, **kw)
            env.run(t.reference_procedure)
            final = env.snapshot()
            for e in t.expected_final:
                actual = final.get(e.table, {}).get(e.record_id, {}).get(e.field)
                if actual != e.value:
                    failures.append(f"{e.table}.{e.record_id}.{e.field}={actual!r}")
            holds = not failures

        sols = []
        for s in t.solutions:
            env = Environment(t.initial_state, **kw)
            env.run(s.procedure)
            g = grade(env.initial_tables(), env.snapshot(), assertions)
            sols.append(SolutionResult(id=s.id, expected=s.expected_verdict,
                                       actual="pass" if g.passed else "fail",
                                       failed_assertions=g.failed_ids))

        admission_ok = rec.status == t.expected_admission and (
            set(t.expected_rejection_codes) <= set(codes))
        results.append(FixtureTaskResult(
            id=t.id, oracle_outcome=decision.outcome,
            oracle_agrees=decision.outcome == t.expected_outcome,
            admission_status=rec.status, admission_agrees=admission_ok, rejection_codes=codes,
            expected_final_holds=holds, expected_final_failures=failures, solutions=sols))
    disagreements = [d for r in results for d in r.disagreements]
    return FixtureReport(fixture_id=fixture.fixture_id, results=results, records=records,
                         disagreements=disagreements)


def fixture_digest(fixture: Fixture) -> str:
    return sha256_json(fixture)
