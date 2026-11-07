"""The structured scenario an LLM proposes, and how its raw text is parsed."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .common import Model
from .env import ToolCall, WorldState
from .policy import PlanChangeRequest
from .spec import Outcome


class ScenarioProposal(Model):
    family_id: str
    initial_state: WorldState
    request: PlanChangeRequest
    instruction: str
    claimed_outcome: Outcome
    reference_procedure: list[ToolCall]
    rationale: str = ""


class ProposalParseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_proposal(raw: str) -> ScenarioProposal:
    text = raw.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProposalParseError("malformed_json", f"response is not JSON: {exc}") from exc
    try:
        return ScenarioProposal.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        raise ProposalParseError(
            "schema_invalid", f"{exc.error_count()} schema error(s); first at {loc}: {first['msg']}"
        ) from exc
