"""Deterministic policy oracle: which outcome does the approved spec require?

The oracle is the single place the prototype's assumed policies are executed.
It reads them from the spec in order, so reordering, disabling or changing
parameters in plan_change.yaml changes the expected outcomes.
"""

from __future__ import annotations

from .common import Model
from .env import WorldState
from .spec import Outcome, Policy, WorkloadSpec


class PlanChangeRequest(Model):
    """Evaluator-side binding: what the ticket actually asks for."""

    ticket_id: str
    subscription_id: str
    requested_plan: str


class Decision(Model):
    outcome: Outcome
    decided_by: str  # policy id, or "default"
    trace: list[str]


def _applies(policy: Policy, spec: WorkloadSpec, state: WorldState,
             req: PlanChangeRequest) -> tuple[Outcome, str] | None:
    sub = state.get("subscriptions", req.subscription_id)
    current, wanted = sub.plan, req.requested_plan
    if policy.kind == "inactive_blocks_change":
        if sub.status != "active":
            return "denied_inactive", f"subscription is {sub.status}"
    elif policy.kind == "already_on_plan_noop":
        if current == wanted:
            return "no_change_needed", f"already on {wanted}"
    elif policy.kind == "escalate_plans":
        plans = set(policy.params["plans"])
        if current in plans or wanted in plans:
            return "escalated", f"{current}->{wanted} involves {sorted(plans)}"
    elif policy.kind == "unpaid_blocks_downgrade":
        unpaid = [i.id for i in state.invoices
                  if i.subscription_id == sub.id and i.status == "unpaid"]
        if spec.rank(wanted) < spec.rank(current) and unpaid:
            return "denied_unpaid", f"downgrade with unpaid invoices {unpaid}"
    return None


def decide(spec: WorkloadSpec, state: WorldState, req: PlanChangeRequest) -> Decision:
    """Assumes the request has already passed referential validation."""
    trace: list[str] = []
    for policy in spec.policies:
        if not policy.enabled:
            trace.append(f"{policy.id} disabled")
            continue
        hit = _applies(policy, spec, state, req)
        if hit:
            outcome, why = hit
            trace.append(f"{policy.id} applies: {why} -> {outcome}")
            return Decision(outcome=outcome, decided_by=policy.id, trace=trace)
        trace.append(f"{policy.id} does not apply")
    trace.append("default -> plan_changed")
    return Decision(outcome="plan_changed", decided_by="default", trace=trace)
