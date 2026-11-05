from privatebench.schema import ChangeKind, StateSnapshot, diff_snapshots


def snap(**tables):
    return StateSnapshot(snapshot_id="s", now="2026-11-05T00:00:00Z", tables=tables)


def test_diff_reports_inserts_updates_and_deletes():
    before = snap(
        ticket={"T-1": {"status": "open"}, "T-2": {"status": "open"}},
        refund={},
    )
    after = snap(
        ticket={"T-1": {"status": "resolved"}},
        refund={"F-1": {"order_id": "O-1"}},
    )
    changes = {(c.table, c.key): c for c in diff_snapshots(before, after).changes}
    assert changes[("ticket", "T-1")].kind is ChangeKind.update
    assert changes[("ticket", "T-2")].kind is ChangeKind.delete
    assert changes[("refund", "F-1")].kind is ChangeKind.insert
    assert changes[("refund", "F-1")].after == {"order_id": "O-1"}


def test_unchanged_state_has_empty_diff():
    s = snap(ticket={"T-1": {"status": "open"}})
    assert diff_snapshots(s, s).changes == []
