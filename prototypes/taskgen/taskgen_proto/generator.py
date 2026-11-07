"""Injectable generator client, prompt construction, and an offline fake.

A real LLM client implements `GeneratorClient.complete(prompt, request) -> str`
and returns JSON matching `ScenarioProposal`. Nothing it returns is trusted:
the pipeline parses, validates, replays and audits every candidate.

`FakeGeneratorClient` is deterministic and offline. It deliberately emits
some defective candidates (on a configurable schedule) so the rejection and
repair paths are exercised.
"""

from __future__ import annotations

import json
import random
from typing import Literal, Protocol

from .common import Model
from .env import tool_specs
from .proposal import ScenarioProposal
from .spec import WorkloadSpec


class GenerationRequest(Model):
    spec_id: str
    family_id: str
    seed: int
    revision: int
    feedback: list[str] = []


class GeneratorClient(Protocol):
    name: str
    model: str

    def complete(self, prompt: str, request: GenerationRequest) -> str: ...


def build_prompt(spec: WorkloadSpec, request: GenerationRequest) -> str:
    family = spec.family(request.family_id)
    tools = [t.model_dump() for t in tool_specs(spec.plan_names, spec.resolution_codes)]
    parts = [
        "You design test scenarios for a support-agent benchmark. Return ONE JSON object "
        "matching the schema below and nothing else.",
        f"## Workload\n{spec.description.strip()}\n\nNOTE: {spec.disclaimer.strip()}",
        "## Policies (apply in order; first match decides)\n"
        + "\n".join(f"- {line}" for line in spec.solver_policy_text()),
        f"## Plans (low to high)\n{', '.join(spec.plan_names)}",
        f"## Tools\n{json.dumps(tools, indent=1)}",
        f"## Target family: {family.id if family else request.family_id}\n"
        f"{family.description if family else ''}\nIntended outcome: "
        f"{family.outcome if family else '?'}",
        "## Requirements\n"
        "- initial_state: realistic records, including at least one unrelated subscription "
        "and one unrelated open ticket.\n"
        "- The target ticket body must name the subscription id and the requested plan.\n"
        "- instruction: what the operator tells the agent. Name the ticket id. Do NOT reveal "
        "the outcome or which policy applies. Avoid these terms: "
        + ", ".join(spec.instruction_forbidden_terms) + ".\n"
        "- reference_procedure: tool calls that solve the task from the initial state.\n"
        "- claimed_outcome: the outcome the policies require.",
        f"## Output JSON schema\n{json.dumps(ScenarioProposal.model_json_schema())}",
        f"## Variation seed\n{request.seed}",
    ]
    if request.feedback:
        parts.append("## Your previous attempt was rejected. Fix these problems:\n"
                     + "\n".join(f"- {f}" for f in request.feedback))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# Offline fake
# --------------------------------------------------------------------------

Defect = Literal[
    "mislabeled", "leaky_instruction", "broken_procedure", "dangling_reference",
    "malformed_json", "unreachable_request",
]
PERSISTENT_DEFECTS: frozenset[str] = frozenset({"dangling_reference"})

DEFAULT_DEFECTS: dict[tuple[str, int], Defect] = {
    ("eligible_change", 1): "unreachable_request",
    ("eligible_change", 2): "leaky_instruction",
    ("unpaid_downgrade", 2): "mislabeled",
    ("already_on_plan", 2): "broken_procedure",
    ("inactive_subscription", 2): "dangling_reference",
    ("enterprise_escalation", 2): "malformed_json",
}

# (current plan, requested plan, flags) per family, cycled by seed.
_SHAPES: dict[str, list[tuple[str, str, dict[str, bool]]]] = {
    "eligible_change": [("team", "pro", {"sibling_unpaid": True}),
                        ("basic", "team", {"target_unpaid": True})],
    "unpaid_downgrade": [("team", "basic", {"target_unpaid": True}),
                         ("pro", "basic", {"target_unpaid": True})],
    "enterprise_escalation": [("pro", "enterprise", {}),
                              ("enterprise", "team", {"target_unpaid": True})],
    "already_on_plan": [("pro", "pro", {}), ("team", "team", {"target_unpaid": True})],
    "inactive_subscription": [("basic", "pro", {"cancelled": True}),
                              ("team", "basic", {"cancelled": True})],
}
_NAMES = ["Ada Park", "Ben Okafor", "Chen Li", "Dana Ruiz", "Eli Novak", "Fay Moreau",
          "Gus Tanaka", "Hana Weiss"]
_BODIES = [
    "Hi, please switch subscription {sub} to the {plan} plan. Thanks, {name}",
    "Could you move {sub} over to {plan}? - {name}",
    "Hello support, I'd like {sub} changed to the {plan} plan going forward. {name}",
]
_INSTRUCTIONS = [
    "Please handle support ticket {ticket}.",
    "Work on ticket {ticket} using the tools available to you.",
    "A customer opened ticket {ticket}. Take care of it following the support policies.",
]


class FakeGeneratorClient:
    name = "fake-offline"
    model = "fake-offline-v1"

    def __init__(self, spec: WorkloadSpec,
                 defects: dict[tuple[str, int], Defect] | None = None) -> None:
        self.spec = spec
        self.defects = DEFAULT_DEFECTS if defects is None else defects
        self.calls = 0

    def complete(self, prompt: str, request: GenerationRequest) -> str:
        self.calls += 1
        defect = self.defects.get((request.family_id, request.seed))
        if defect and request.revision > 0 and defect not in PERSISTENT_DEFECTS:
            defect = None  # a "repair" in response to feedback
        proposal = self._proposal(request.family_id, request.seed, defect)
        text = json.dumps(proposal, indent=1)
        if defect == "malformed_json":
            return "Sure! Here is the scenario you asked for:\n" + text[: len(text) // 2]
        return text

    def _proposal(self, family_id: str, seed: int, defect: Defect | None) -> dict:
        family = self.spec.family(family_id)
        if family is None:
            raise ValueError(f"fake generator has no shape for family {family_id!r}")
        rng = random.Random(f"{family_id}:{seed}")
        current, wanted, flags = _SHAPES[family_id][(seed - 1) % len(_SHAPES[family_id])]
        n = rng.randint(1000, 9999)
        cus, other_cus = f"CUS-{n}", f"CUS-{n + 1}"
        sub, sibling, other_sub = f"SUB-{n}-1", f"SUB-{n}-2", f"SUB-{n + 1}-1"
        ticket, other_ticket = f"TCK-{n}-1", f"TCK-{n + 1}-1"
        name, other_name = rng.sample(_NAMES, 2)
        spare = [p for p in self.spec.plan_names if p not in (current, wanted)]

        body = rng.choice(_BODIES).format(sub=sub, plan=wanted, name=name.split()[0])
        if defect == "unreachable_request":
            body = f"Hi, could you change my plan to {wanted}? Thanks, {name.split()[0]}"
        instruction = rng.choice(_INSTRUCTIONS).format(ticket=ticket)
        if defect == "leaky_instruction":
            instruction += f" Expected result: {family.outcome}."

        state = {
            "customers": [
                {"id": cus, "name": name, "email": f"{name.split()[0].lower()}@example.test"},
                {"id": other_cus, "name": other_name,
                 "email": f"{other_name.split()[0].lower()}@example.test"},
            ],
            "subscriptions": [
                {"id": sub, "customer_id": cus, "plan": current,
                 "status": "cancelled" if flags.get("cancelled") else "active"},
                {"id": sibling, "customer_id": cus, "plan": rng.choice(spare), "status": "active"},
                {"id": other_sub, "customer_id": other_cus, "plan": rng.choice(spare),
                 "status": "active"},
            ],
            "invoices": [
                {"id": f"INV-{n}-1", "subscription_id": sub,
                 "status": "unpaid" if flags.get("target_unpaid") else "paid",
                 "amount_cents": rng.randint(1, 50) * 1000},
                {"id": f"INV-{n}-2", "subscription_id": sibling,
                 "status": "unpaid" if flags.get("sibling_unpaid") else "paid",
                 "amount_cents": rng.randint(1, 50) * 1000},
                {"id": f"INV-{n + 1}-1", "subscription_id": other_sub, "status": "paid",
                 "amount_cents": rng.randint(1, 50) * 1000},
            ],
            "tickets": [
                {"id": ticket, "customer_id": "CUS-404" if defect == "dangling_reference" else cus,
                 "subject": "Plan change request", "body": body},
                {"id": other_ticket, "customer_id": other_cus, "subject": "Invoice copy",
                 "body": "Can you resend my last invoice?"},
            ],
        }

        claimed = family.outcome
        reads = [
            {"tool": "get_ticket", "args": {"ticket_id": ticket}},
            {"tool": "list_subscriptions", "args": {"customer_id": cus}},
            {"tool": "list_invoices", "args": {"subscription_id": sub}},
        ]
        if defect == "mislabeled":
            claimed = "plan_changed"
        if claimed == "escalated":
            muts = [{"tool": "escalate_ticket",
                     "args": {"ticket_id": ticket, "reason": f"{current}->{wanted} needs the "
                              "account team."}}]
        else:
            muts = []
            if claimed == "plan_changed":
                muts.append({"tool": "change_plan",
                             "args": {"subscription_id": sub, "new_plan": wanted}})
            muts.append({"tool": "resolve_ticket",
                         "args": {"ticket_id": ticket, "resolution_code": claimed,
                                  "note": f"Handled request for {wanted}."}})
        if defect == "broken_procedure":
            muts = muts[:-1]

        return {
            "family_id": family_id,
            "initial_state": state,
            "request": {"ticket_id": ticket, "subscription_id": sub, "requested_plan": wanted},
            "instruction": instruction,
            "claimed_outcome": claimed,
            "reference_procedure": reads + muts,
            "rationale": f"{family.description} ({current} -> {wanted}, flags={sorted(flags)})",
        }
