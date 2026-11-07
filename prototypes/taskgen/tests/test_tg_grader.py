"""The grader accepts valid alternatives and rejects wrong targets,
incomplete work and collateral changes. Uses the hand-authored fixture state."""

from tg_helpers import calls, env_for, fixture_task
from taskgen_proto.grader import compile_assertions, diff_tables, grade

TASK = "fx-sibling-unpaid-downgrade"


def _grade(procedure, task_id=TASK):
    t = fixture_task(task_id)
    env = env_for(t.initial_state)
    env.run(procedure)
    assertions = compile_assertions(t.request, t.expected_outcome, t.initial_state)
    return grade(env.initial_tables(), env.snapshot(), assertions)


def test_accepts_reference_and_valid_alternative():
    assert _grade(fixture_task(TASK).reference_procedure).passed
    alt = calls(
        ("add_note", {"ticket_id": "TCK-1", "text": "On it."}),
        ("resolve_ticket", {"ticket_id": "TCK-1", "resolution_code": "plan_changed"}),
        ("list_subscriptions", {"customer_id": "K-1"}),
        ("change_plan", {"subscription_id": "SUB-A", "new_plan": "pro"}),
    )
    assert _grade(alt).passed


def test_rejects_wrong_target():
    g = _grade(calls(
        ("change_plan", {"subscription_id": "SUB-B", "new_plan": "pro"}),
        ("resolve_ticket", {"ticket_id": "TCK-1", "resolution_code": "plan_changed"}),
    ))
    assert not g.passed
    assert {"plan_set", "preserve_unrelated_state"} <= set(g.failed_ids)


def test_rejects_incomplete_work():
    g = _grade(calls(("change_plan", {"subscription_id": "SUB-A", "new_plan": "pro"})))
    assert not g.passed and "ticket_resolved" in g.failed_ids
    assert not _grade([]).passed


def test_rejects_collateral_change():
    g = _grade(fixture_task(TASK).reference_procedure + calls(
        ("add_note", {"ticket_id": "TCK-2", "text": "fyi"})))
    assert not g.passed and g.failed_ids == ["preserve_unrelated_state"]


def test_rejects_completion_claim_without_action():
    g = _grade(calls(("add_note", {"ticket_id": "TCK-1", "text": "Done: plan changed, resolved."})))
    assert not g.passed


def test_denial_branch_forbids_plan_change():
    t = "fx-enterprise-beats-unpaid"
    g = _grade(calls(
        ("change_plan", {"subscription_id": "SUB-E", "new_plan": "team"}),
        ("escalate_ticket", {"ticket_id": "TCK-5", "reason": "x"}),
    ), t)
    assert not g.passed and "plan_not_changed" in g.failed_ids


def test_diff_reports_created_and_deleted_records():
    before = {"t": {"a": {"x": 1}, "b": {"x": 1}}}
    after = {"t": {"a": {"x": 2}, "c": {"x": 1}}}
    fields = {(c.record_id, c.field) for c in diff_tables(before, after)}
    assert fields == {("a", "x"), ("b", "<deleted>"), ("c", "<created>")}
