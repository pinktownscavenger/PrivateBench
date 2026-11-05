"""Run record: one planned trial of one configuration on one task."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrialOutcome(str, Enum):
    planned = "planned"                    # in the ledger, not yet dispatched
    success = "success"
    task_failure = "task_failure"          # includes solver timeouts
    budget_exhausted = "budget_exhausted"
    infra_error = "infra_error"
    invalid_task = "invalid_task"
    unassessable = "unassessable"          # evidence missing; never silently dropped


class Usage(_Model):
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class RunRecord(_Model):
    trial_id: str
    task_id: str
    task_hashes: dict[str, str]
    configuration_digest: str
    repeat_index: int
    outcome: TrialOutcome = TrialOutcome.planned
    failed_assertions: list[str] = []      # rule-tagged assertion ids
    usage: Usage = Usage()
    wall_seconds: float | None = None
    errors: list[str] = []
    scorer_version: str | None = None
    events_ref: str | None = None          # path to the gateway's event log
