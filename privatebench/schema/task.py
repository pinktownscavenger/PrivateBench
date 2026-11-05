"""Task package: solver bundle + evaluation bundle + metadata.

Only `TaskPackage.solver_json()` may cross into the solver's environment.
Metadata (family, rules, lineage) and the evaluation bundle are evaluator-only.
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .contract import ExpectedBehavior
from .hashing import content_hash


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdmissionStatus(str, Enum):
    draft = "draft"
    blocked_spec = "blocked_spec"
    ready = "ready"
    validation_failed = "validation_failed"
    review_pending = "review_pending"
    admitted = "admitted"
    quarantined = "quarantined"
    retired = "retired"


# Failed candidates are terminal: a repair creates a new revision linked via
# parent_candidate_id rather than reopening the old one.
_TRANSITIONS: dict[AdmissionStatus, set[AdmissionStatus]] = {
    AdmissionStatus.draft: {AdmissionStatus.blocked_spec, AdmissionStatus.ready},
    AdmissionStatus.blocked_spec: {AdmissionStatus.ready},
    AdmissionStatus.ready: {AdmissionStatus.validation_failed, AdmissionStatus.review_pending},
    AdmissionStatus.review_pending: {AdmissionStatus.admitted, AdmissionStatus.validation_failed},
    AdmissionStatus.admitted: {AdmissionStatus.quarantined, AdmissionStatus.retired},
    AdmissionStatus.quarantined: {AdmissionStatus.retired},
    AdmissionStatus.validation_failed: set(),
    AdmissionStatus.retired: set(),
}


def can_transition(src: AdmissionStatus, dst: AdmissionStatus) -> bool:
    return dst in _TRANSITIONS[src]


class ExposureEvent(_Model):
    at: str
    kind: Literal["created", "provider_call", "solver_run", "reviewer_view", "tuning_use", "released", "retired"]
    detail: str = ""


class TaskMeta(_Model):
    task_id: str
    family_id: str
    contract_version: str
    expected_behavior: ExpectedBehavior
    rule_ids: list[str]
    split_group: str
    recipe_id: str | None = None
    parent_candidate_id: str | None = None
    generator: str = "hand_authored"     # e.g. "arm_a:<model>@<prompt_version>"
    admission_status: AdmissionStatus = AdmissionStatus.draft
    content_hashes: dict[str, str] = {}
    exposure_events: list[ExposureEvent] = []


class SolverBundle(_Model):
    """Everything the solver may see."""
    instruction: str
    context: dict[str, str] = {}        # e.g. the policy text the agent must follow
    tools: list[str]
    inputs: dict[str, Any] = {}


class Assertion(_Model):
    kind: Literal["outcome", "forbidden_effect", "process"]
    template: str
    params: dict[str, Any] = {}
    rule_id: str
    evidence_authority: Literal["backend_state", "event_log"] = "backend_state"
    severity: Literal["critical", "major", "minor"] = "critical"


class ScriptedReply(_Model):
    """Disclosure rule for the scripted user (ask_user)."""
    when_asked_about: str
    reply: str


class EvaluationBundle(_Model):
    """Evaluator-only: never mounted or sent to the solver."""
    bindings: dict[str, str]                 # $placeholder -> concrete id
    reference_procedure: list[dict[str, Any]]
    assertions: list[Assertion]
    environment_snapshot: str
    scripted_user: list[ScriptedReply] = []
    audit_suite: str | None = None


class TaskPackage(_Model):
    meta: TaskMeta
    solver: SolverBundle
    evaluation: EvaluationBundle

    def solver_json(self) -> str:
        return self.solver.model_dump_json()

    def compute_hashes(self) -> dict[str, str]:
        return {"solver": content_hash(self.solver), "evaluation": content_hash(self.evaluation)}
