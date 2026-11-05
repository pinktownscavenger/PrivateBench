import pytest

from privatebench.schema import (
    AdmissionStatus,
    Assertion,
    EvaluationBundle,
    ExpectedBehavior,
    SolverBundle,
    TaskMeta,
    TaskPackage,
    can_transition,
    content_hash,
)


def make_package():
    return TaskPackage(
        meta=TaskMeta(
            task_id="eligible_refund_0001",
            family_id="eligible_refund",
            contract_version="0.1.0-draft",
            expected_behavior=ExpectedBehavior.act,
            rule_ids=["R1", "R2", "R5"],
            split_group="eligible_refund/hand_authored",
        ),
        solver=SolverBundle(
            instruction="Resolve ticket T-100.",
            context={"policy": "Orders delivered within 30 days are refundable once."},
            tools=["get_ticket", "get_order", "issue_refund", "update_ticket"],
            inputs={"ticket_id": "T-100"},
        ),
        evaluation=EvaluationBundle(
            bindings={"target_order": "O-SECRET-7", "ticket": "T-100"},
            reference_procedure=[{"tool": "issue_refund", "args": {"order_id": "O-SECRET-7"}}],
            assertions=[
                Assertion(kind="outcome", template="refund_count",
                          params={"order": "$target_order", "count": 1}, rule_id="R1"),
            ],
            environment_snapshot="snapshot_0001",
        ),
    )


def test_solver_export_contains_no_evaluator_material():
    pkg = make_package()
    exported = pkg.solver_json()
    assert "O-SECRET-7" not in exported
    assert "reference_procedure" not in exported
    assert "eligible_refund" not in exported  # family labels are evaluator-only
    assert "Resolve ticket T-100." in exported


def test_content_hash_ignores_key_order_and_tracks_content():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_package_hashes_cover_each_bundle():
    pkg = make_package()
    hashes = pkg.compute_hashes()
    assert set(hashes) == {"solver", "evaluation"}
    pkg.solver.instruction = "Something else."
    assert pkg.compute_hashes()["solver"] != hashes["solver"]
    assert pkg.compute_hashes()["evaluation"] == hashes["evaluation"]


def test_new_package_starts_as_draft():
    assert make_package().meta.admission_status is AdmissionStatus.draft


@pytest.mark.parametrize("src,dst,ok", [
    ("draft", "ready", True),
    ("draft", "blocked_spec", True),
    ("ready", "review_pending", True),
    ("ready", "validation_failed", True),
    ("review_pending", "admitted", True),
    ("admitted", "quarantined", True),
    ("quarantined", "retired", True),
    ("draft", "admitted", False),
    ("validation_failed", "admitted", False),  # repairs create a new revision
    ("retired", "admitted", False),
])
def test_lifecycle_transitions(src, dst, ok):
    assert can_transition(AdmissionStatus(src), AdmissionStatus(dst)) is ok
