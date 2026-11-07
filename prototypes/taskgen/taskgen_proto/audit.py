"""Grader audit (VerifierBench-style): does the grader accept valid
alternatives and reject wrong targets, incomplete work, collateral changes,
wrong outcomes, and completion claims without action?

Cases are derived mechanically from the scenario and reference. False
acceptances and false rejections are counted separately.
"""

from __future__ import annotations

from typing import Literal

from .common import Model
from .env import MUTATING_TOOLS, Environment, ToolCall, WorldState
from .grader import Assertion, grade
from .policy import PlanChangeRequest
from .spec import Outcome

CaseKind = Literal[
    "valid_alternative", "incomplete", "wrong_target", "collateral", "wrong_outcome",
    "claim_without_action",
]


class AuditCase(Model):
    id: str
    kind: CaseKind
    expected_pass: bool
    rationale: str
    procedure: list[ToolCall]


class AuditOutcome(Model):
    case_id: str
    kind: CaseKind
    expected_pass: bool
    actual_pass: bool
    failed_assertions: list[str]

    @property
    def correct(self) -> bool:
        return self.expected_pass == self.actual_pass


class AuditSummary(Model):
    outcomes: list[AuditOutcome]
    not_applicable: list[str]
    false_accepts: int
    false_rejects: int


def outcome_mutations(req: PlanChangeRequest, outcome: Outcome) -> list[ToolCall]:
    """Canonical state-changing calls for a branch (used only to build wrong-outcome cases)."""
    if outcome == "escalated":
        return [ToolCall(tool="escalate_ticket",
                         args={"ticket_id": req.ticket_id, "reason": "Needs account team."})]
    calls = []
    if outcome == "plan_changed":
        calls.append(ToolCall(tool="change_plan", args={"subscription_id": req.subscription_id,
                                                        "new_plan": req.requested_plan}))
    calls.append(ToolCall(tool="resolve_ticket",
                          args={"ticket_id": req.ticket_id, "resolution_code": outcome}))
    return calls


def _retarget(call: ToolCall, mapping: dict[str, str]) -> ToolCall:
    return ToolCall(tool=call.tool,
                    args={k: mapping.get(v, v) if k.endswith("_id") else v
                          for k, v in call.args.items()})


def build_audit_cases(
    state: WorldState, req: PlanChangeRequest, outcome: Outcome,
    reference: list[ToolCall], plans: list[str],
) -> tuple[list[AuditCase], list[str]]:
    reads = [c for c in reference if c.tool not in MUTATING_TOOLS]
    muts = [c for c in reference if c.tool in MUTATING_TOOLS]
    sub = state.get("subscriptions", req.subscription_id)
    others = [s for s in state.subscriptions if s.id != req.subscription_id]
    others.sort(key=lambda s: s.customer_id != sub.customer_id)  # prefer same customer
    other_tickets = [k for k in state.tickets if k.id != req.ticket_id]
    cases: list[AuditCase] = []
    na: list[str] = []

    def add(id_: str, kind: CaseKind, expected: bool, why: str, proc: list[ToolCall]) -> None:
        cases.append(AuditCase(id=id_, kind=kind, expected_pass=expected, rationale=why,
                               procedure=proc))

    # --- valid alternatives (must pass) -----------------------------------
    add("alt_minimal", "valid_alternative", True,
        "Only the state-changing calls, no reads: outcome scoring must not require a path.",
        muts)
    reworded = [ToolCall(tool=c.tool, args={k: (f"[alt] {v}" if k in ("note", "reason", "text")
                                                  else v) for k, v in c.args.items()})
                for c in muts]
    add("alt_extra_steps", "valid_alternative", True,
        "Extra read calls, an extra note, and different free text.",
        [ToolCall(tool="add_note", args={"ticket_id": req.ticket_id,
                                         "text": "Looking into this."})]
        + list(reversed(reads))
        + [ToolCall(tool="get_ticket", args={"ticket_id": req.ticket_id})]
        + reworded)
    tools = [c.tool for c in muts]
    if "change_plan" in tools and "resolve_ticket" in tools:
        add("alt_reordered", "valid_alternative", True,
            "Resolve before changing the plan; same final state.",
            [c for c in muts if c.tool != "change_plan"]
            + [c for c in muts if c.tool == "change_plan"])
    else:
        na.append("alt_reordered")

    # --- negatives (must fail) --------------------------------------------
    add("incomplete_noop", "incomplete", False, "Does nothing.", reads)
    if len(muts) >= 2:
        add("incomplete_truncated", "incomplete", False, "Drops the last state-changing call.",
            reads + muts[:-1])
    else:
        na.append("incomplete_truncated")

    if others and other_tickets:
        mapping = {req.subscription_id: others[0].id, req.ticket_id: other_tickets[0].id}
        add("wrong_target", "wrong_target", False,
            f"Applies the reference to {others[0].id} / {other_tickets[0].id}.",
            reads + [_retarget(c, mapping) for c in muts])
        new_plan = next(p for p in plans if p != others[0].plan)
        add("collateral_change", "collateral", False,
            f"Reference plus an unrelated change to {others[0].id}.",
            reference + [ToolCall(tool="change_plan", args={"subscription_id": others[0].id,
                                                            "new_plan": new_plan})])
    else:
        na += ["wrong_target", "collateral_change"]

    wrong = "plan_changed" if outcome == "escalated" else "escalated"
    add("wrong_outcome", "wrong_outcome", False, f"Takes the {wrong} branch instead.",
        reads + outcome_mutations(req, wrong))
    add("claim_without_action", "claim_without_action", False,
        "Writes a note claiming completion without changing anything else.",
        [ToolCall(tool="add_note", args={"ticket_id": req.ticket_id,
                                         "text": f"Done. Outcome: {outcome}. Ticket closed."})])
    return cases, na


def run_audit(
    state: WorldState, cases: list[AuditCase], assertions: list[Assertion],
    *, plans: list[str], resolution_codes: list[str], not_applicable: list[str] | None = None,
) -> AuditSummary:
    outcomes = []
    for case in cases:
        env = Environment(state, plans=plans, resolution_codes=resolution_codes)
        env.run(case.procedure)
        g = grade(env.initial_tables(), env.snapshot(), assertions)
        outcomes.append(AuditOutcome(case_id=case.id, kind=case.kind,
                                     expected_pass=case.expected_pass, actual_pass=g.passed,
                                     failed_assertions=g.failed_ids))
    return AuditSummary(
        outcomes=outcomes,
        not_applicable=list(not_applicable or []),
        false_accepts=sum(1 for o in outcomes if o.actual_pass and not o.expected_pass),
        false_rejects=sum(1 for o in outcomes if o.expected_pass and not o.actual_pass),
    )
