import pytest

from tg_helpers import fixture_task, spec
from taskgen_proto.policy import PlanChangeRequest, decide
from taskgen_proto.spec import SpecNotApproved, WorkloadSpec, require_approved


def _decide(s, task_id, **req):
    t = fixture_task(task_id)
    r = t.request.model_copy(update=req) if req else t.request
    return decide(s, t.initial_state, r).outcome


def test_each_branch():
    s = spec()
    assert _decide(s, "fx-sibling-unpaid-downgrade") == "plan_changed"
    assert _decide(s, "fx-enterprise-beats-unpaid") == "escalated"
    assert _decide(s, "fx-cancelled-same-plan") == "denied_inactive"
    assert _decide(s, "fx-already-on-plan") == "no_change_needed"
    # pro -> basic on SUB-J, which has an unpaid invoice
    assert _decide(s, "fx-already-on-plan", requested_plan="basic") == "denied_unpaid"
    # upgrades are not blocked by unpaid invoices
    assert _decide(s, "fx-already-on-plan", requested_plan="team") == "plan_changed"


def test_policies_are_configurable():
    s = spec()
    data = s.model_dump()
    # Disable A3: enterprise downgrade with unpaid invoice now hits A4.
    for p in data["policies"]:
        if p["id"] == "A3":
            p["enabled"] = False
    assert _decide(WorkloadSpec.model_validate(data), "fx-enterprise-beats-unpaid") == "denied_unpaid"
    # Reorder A1/A2: cancelled-but-same-plan becomes no_change_needed.
    data = s.model_dump()
    data["policies"][0], data["policies"][1] = data["policies"][1], data["policies"][0]
    assert _decide(WorkloadSpec.model_validate(data), "fx-cancelled-same-plan") == "no_change_needed"
    # Change parameters: escalate 'team' instead of 'enterprise'.
    data = s.model_dump()
    data["policies"][2]["params"] = {"plans": ["team"]}
    s2 = WorkloadSpec.model_validate(data)
    assert _decide(s2, "fx-sibling-unpaid-downgrade") == "escalated"
    assert "team" in " ".join(s2.solver_policy_text())


def test_all_policies_are_marked_as_assumptions():
    assert {p.provenance for p in spec().policies} == {"prototype_assumption"}


def test_unapproved_spec_blocks_generation():
    data = spec().model_dump()
    data["status"] = "draft"
    with pytest.raises(SpecNotApproved):
        require_approved(WorkloadSpec.model_validate(data))


def test_spec_rejects_unknown_fields_and_bad_params():
    data = spec().model_dump()
    data["policies"][2]["params"] = {"plans": ["platinum"]}
    with pytest.raises(ValueError):
        WorkloadSpec.model_validate(data)
    data = spec().model_dump()
    data["surprise"] = 1
    with pytest.raises(ValueError):
        WorkloadSpec.model_validate(data)
