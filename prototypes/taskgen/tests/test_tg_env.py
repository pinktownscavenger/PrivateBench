from tg_helpers import calls, env_for, fixture_task


def test_reset_restores_exact_initial_state():
    t = fixture_task("fx-sibling-unpaid-downgrade")
    env = env_for(t.initial_state)
    h0 = env.state_hash()
    env.run(t.reference_procedure)
    assert env.state_hash() != h0
    env.reset()
    assert env.state_hash() == h0 and env.events == []


def test_environment_does_not_alias_caller_state():
    t = fixture_task("fx-sibling-unpaid-downgrade")
    env = env_for(t.initial_state)
    env.call("change_plan", {"subscription_id": "SUB-A", "new_plan": "basic"})
    assert t.initial_state.get("subscriptions", "SUB-A").plan == "team"
    data = env.call("get_ticket", {"ticket_id": "TCK-1"}).data
    data["status"] = "tampered"
    assert env.snapshot()["tickets"]["TCK-1"]["status"] == "open"


def test_tool_errors_are_logged_not_raised():
    env = env_for(fixture_task("fx-sibling-unpaid-downgrade").initial_state)
    results = env.run(calls(
        ("nope", {}),
        ("change_plan", {"subscription_id": "SUB-A", "new_plan": "platinum"}),
        ("get_ticket", {"ticket_id": "TCK-1", "extra": "x"}),
        ("resolve_ticket", {"ticket_id": "TCK-1", "resolution_code": "plan_changed"}),
        ("resolve_ticket", {"ticket_id": "TCK-1", "resolution_code": "plan_changed"}),
    ))
    assert [r.ok for r in results] == [False, False, False, True, False]
    assert "not open" in results[-1].error
    assert [e.seq for e in env.events] == [0, 1, 2, 3, 4]


def test_tools_do_not_enforce_policy():
    # Changing a cancelled subscription is allowed by the tool; the grader judges it.
    env = env_for(fixture_task("fx-cancelled-same-plan").initial_state)
    assert env.call("change_plan", {"subscription_id": "SUB-G", "new_plan": "pro"}).ok
