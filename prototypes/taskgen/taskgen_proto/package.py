"""Task package with a hard split between solver-visible and evaluator-only content."""

from __future__ import annotations

from typing import Literal

from .audit import AuditSummary
from .common import Model
from .env import ToolCall, ToolSpec, WorldState
from .grader import Assertion
from .metering import CostBreakdown
from .policy import PlanChangeRequest
from .spec import Outcome


class Provenance(Model):
    source: Literal["generator", "independent_fixture"]
    candidate_id: str
    parent_candidate_id: str | None
    revision: int
    generator: str | None
    model: str | None
    seed: int | None
    prompt_sha256: str | None
    response_sha256: str
    spec_id: str
    spec_version: int
    spec_sha256: str
    pipeline_version: str
    created_at: str
    # Live generation only: reported cost and unknown-billing exposure for this
    # candidate, and for it plus every rejected ancestor in its repair chain.
    generation_cost: CostBreakdown | None = None
    lineage_generation_cost: CostBreakdown | None = None


class SolverView(Model):
    """The ONLY content that may reach the agent under test."""

    task_id: str
    instruction: str
    policies: list[str]
    tools: list[ToolSpec]


class EvaluatorBundle(Model):
    """Evaluator-only. Never shown to the solver."""

    family_id: str
    expected_outcome: Outcome
    decision_trace: list[str]
    request: PlanChangeRequest
    required_outcomes: list[str]
    forbidden_effects: list[str]
    assertions: list[Assertion]
    reference_procedure: list[ToolCall]
    audit: AuditSummary
    provenance: Provenance


class TaskPackage(Model):
    task_id: str
    solver: SolverView
    initial_state: WorldState  # loaded into the environment, reached only through tools
    evaluator: EvaluatorBundle

    def solver_json(self) -> str:
        return self.solver.model_dump_json(indent=2)
