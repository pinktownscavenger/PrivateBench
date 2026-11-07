"""Deterministic static checks on a parsed proposal (before any execution)."""

from __future__ import annotations

import re

from .common import Issue
from .env import integrity_issues
from .policy import decide
from .proposal import ScenarioProposal
from .spec import WorkloadSpec

STAGE = "static"


def _mentions(text: str, token: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text, re.IGNORECASE) is not None


def static_issues(spec: WorkloadSpec, p: ScenarioProposal) -> list[Issue]:
    issues: list[Issue] = []

    def bad(code: str, msg: str) -> None:
        issues.append(Issue(stage=STAGE, code=code, message=msg))

    family = spec.family(p.family_id)
    if family is None:
        bad("unknown_family", f"family {p.family_id!r} is not in the approved spec")

    for problem in integrity_issues(p.initial_state, spec.plan_names):
        bad("state_integrity", problem)

    s, req = p.initial_state, p.request
    ticket = s.get("tickets", req.ticket_id)
    sub = s.get("subscriptions", req.subscription_id)
    if ticket is None:
        bad("request_ticket_missing", f"ticket {req.ticket_id} not in initial state")
    elif ticket.status != "open":
        bad("ticket_not_open", f"ticket {req.ticket_id} starts {ticket.status}")
    if sub is None:
        bad("request_subscription_missing", f"subscription {req.subscription_id} not in state")
    if ticket and sub and ticket.customer_id != sub.customer_id:
        bad("request_ownership_mismatch",
            f"ticket {ticket.id} and subscription {sub.id} belong to different customers")
    if req.requested_plan not in spec.plan_names:
        bad("unknown_plan", f"requested plan {req.requested_plan!r} not in spec")

    g = spec.generation
    if len(s.subscriptions) - 1 < g.min_distractor_subscriptions:
        bad("insufficient_distractors", "not enough unrelated subscriptions to test preservation")
    if len(s.tickets) - 1 < g.min_distractor_tickets:
        bad("insufficient_distractors", "not enough unrelated tickets to test preservation")

    # Feasibility from solver-visible information only: the instruction plus
    # the target ticket (reachable via get_ticket) must identify the request.
    if ticket is not None:
        visible = f"{p.instruction}\n{ticket.subject}\n{ticket.body}"
        if not (_mentions(visible, req.subscription_id) and _mentions(visible, req.requested_plan)):
            bad("request_not_solver_reachable",
                "instruction + ticket text must name the subscription id and requested plan")
    if not _mentions(p.instruction, req.ticket_id):
        bad("instruction_missing_ticket", "instruction must name the ticket to work")
    if len(p.instruction) > g.instruction_max_chars:
        bad("instruction_too_long", f"instruction exceeds {g.instruction_max_chars} chars")
    lowered = p.instruction.lower()
    leaked = [t for t in spec.instruction_forbidden_terms if t.lower() in lowered]
    if leaked:
        bad("instruction_leaks_answer", f"instruction contains answer-revealing terms {leaked}")

    if issues:  # oracle needs a referentially valid request
        return issues

    decision = decide(spec, s, req)
    if p.claimed_outcome != decision.outcome:
        bad("label_disagrees_with_policy",
            f"generator claimed {p.claimed_outcome}; policy oracle says {decision.outcome} "
            f"({decision.trace[-1]})")
    if family is not None and family.outcome != decision.outcome:
        bad("family_branch_mismatch",
            f"family {family.id} targets {family.outcome}; scenario exercises {decision.outcome}")
    return issues
