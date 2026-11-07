"""Approved workload specification: plans, policies (prototype assumptions), families."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator

from .common import Model, sha256_json

Outcome = Literal[
    "plan_changed", "no_change_needed", "denied_unpaid", "denied_inactive", "escalated"
]
PolicyKind = Literal[
    "inactive_blocks_change", "already_on_plan_noop", "escalate_plans", "unpaid_blocks_downgrade"
]

DEFAULT_SPEC_PATH = Path(__file__).resolve().parent.parent / "workload" / "plan_change.yaml"


class SpecNotApproved(RuntimeError):
    pass


class Approval(Model):
    approved_by: str
    approved_on: str
    note: str = ""


class Plan(Model):
    name: str
    rank: int


class Policy(Model):
    id: str
    kind: PolicyKind
    enabled: bool = True
    provenance: Literal["prototype_assumption"] = "prototype_assumption"
    params: dict[str, Any] = Field(default_factory=dict)
    statement: str

    def rendered(self) -> str:
        values = {k: ", ".join(v) if isinstance(v, list) else v for k, v in self.params.items()}
        return " ".join(self.statement.format(**values).split())


class DefaultOutcome(Model):
    statement: str


class Family(Model):
    id: str
    outcome: Outcome
    target_count: int = Field(ge=0)
    description: str


class GenerationSettings(Model):
    max_repairs: int = Field(default=1, ge=0)
    min_distractor_subscriptions: int = Field(default=1, ge=0)
    min_distractor_tickets: int = Field(default=1, ge=0)
    instruction_max_chars: int = Field(default=600, gt=0)


class WorkloadSpec(Model):
    spec_id: str
    version: int
    status: Literal["draft", "approved"]
    approval: Approval | None = None
    description: str
    disclaimer: str
    plans: list[Plan]
    resolution_codes: list[str]
    policies: list[Policy]
    default_outcome: DefaultOutcome
    families: list[Family]
    instruction_forbidden_terms: list[str]
    generation: GenerationSettings = Field(default_factory=GenerationSettings)

    @model_validator(mode="after")
    def _consistent(self) -> "WorkloadSpec":
        names = [p.name for p in self.plans]
        if len(set(names)) != len(names) or len({p.rank for p in self.plans}) != len(names):
            raise ValueError("plan names and ranks must be unique")
        for label, ids in (
            ("policy", [p.id for p in self.policies]),
            ("family", [f.id for f in self.families]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate {label} ids")
        needed = {"plan_changed", "no_change_needed", "denied_unpaid", "denied_inactive"}
        if not needed <= set(self.resolution_codes):
            raise ValueError(f"resolution_codes must include {sorted(needed)}")
        for p in self.policies:
            if p.kind == "escalate_plans":
                plans = p.params.get("plans")
                if not isinstance(plans, list) or not set(plans) <= set(names):
                    raise ValueError(f"policy {p.id}: params.plans must list known plans")
        if self.status == "approved" and self.approval is None:
            raise ValueError("an approved spec needs an approval record")
        return self

    # --- convenience -----------------------------------------------------
    @property
    def plan_names(self) -> list[str]:
        return [p.name for p in sorted(self.plans, key=lambda p: p.rank)]

    def rank(self, plan: str) -> int:
        for p in self.plans:
            if p.name == plan:
                return p.rank
        raise KeyError(plan)

    def family(self, family_id: str) -> Family | None:
        return next((f for f in self.families if f.id == family_id), None)

    def solver_policy_text(self) -> list[str]:
        """Policy statements the solver is allowed to see (no ids, no kinds)."""
        lines = [p.rendered() for p in self.policies if p.enabled]
        lines.append(" ".join(self.default_outcome.statement.split()))
        return lines

    def digest(self) -> str:
        return sha256_json(self)


def load_spec(path: str | Path = DEFAULT_SPEC_PATH) -> WorkloadSpec:
    with open(path, encoding="utf-8") as fh:
        return WorkloadSpec.model_validate(yaml.safe_load(fh))


def require_approved(spec: WorkloadSpec) -> None:
    if spec.status != "approved":
        raise SpecNotApproved(
            f"spec {spec.spec_id} v{spec.version} has status {spec.status!r}; "
            "generation only runs from an approved specification"
        )
