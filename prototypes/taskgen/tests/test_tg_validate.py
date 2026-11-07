import json

from tg_helpers import fixture_task, spec
from taskgen_proto.proposal import ProposalParseError, ScenarioProposal, parse_proposal
from taskgen_proto.validate import static_issues

import pytest


def _proposal(task_id="fx-sibling-unpaid-downgrade", **updates):
    t = fixture_task(task_id)
    p = ScenarioProposal(family_id=t.family_id, initial_state=t.initial_state,
                         request=t.request, instruction=t.instruction,
                         claimed_outcome=t.expected_outcome,
                         reference_procedure=t.reference_procedure)
    return p.model_copy(update=updates)


def _codes(p):
    return {i.code for i in static_issues(spec(), p)}


def test_clean_proposal_passes():
    assert _codes(_proposal()) == set()


def test_leaky_instruction():
    assert "instruction_leaks_answer" in _codes(
        _proposal(instruction="Work TCK-1; the downgrade is eligible."))


def test_instruction_must_name_ticket():
    assert "instruction_missing_ticket" in _codes(_proposal(instruction="Do the thing."))


def test_wrong_label():
    assert "label_disagrees_with_policy" in _codes(_proposal(claimed_outcome="denied_unpaid"))


def test_unknown_family_and_branch_mismatch():
    assert "unknown_family" in _codes(_proposal(family_id="made_up"))
    assert "family_branch_mismatch" in _codes(_proposal(family_id="unpaid_downgrade"))


def test_request_must_be_reachable_from_solver_visible_text():
    p = _proposal()
    s = p.initial_state.model_copy(deep=True)
    s.tickets[0].body = "Please change my plan."
    assert "request_not_solver_reachable" in _codes(p.model_copy(update={"initial_state": s}))


def test_preservation_needs_distractors():
    p = _proposal()
    s = p.initial_state.model_copy(deep=True)
    s.tickets = s.tickets[:1]
    assert "insufficient_distractors" in _codes(p.model_copy(update={"initial_state": s}))


def test_parse_handles_fences_and_rejects_bad_json_and_schema():
    raw = json.dumps(_proposal().model_dump(mode="json"))
    assert parse_proposal(f"```json\n{raw}\n```").family_id == "eligible_change"
    with pytest.raises(ProposalParseError) as e:
        parse_proposal("not json")
    assert e.value.code == "malformed_json"
    bad = json.loads(raw)
    bad["secret_answer"] = "x"
    with pytest.raises(ProposalParseError) as e:
        parse_proposal(json.dumps(bad))
    assert e.value.code == "schema_invalid"
