import json

import pytest

from tg_helpers import spec
from taskgen_proto.generator import FakeGeneratorClient, build_prompt, GenerationRequest
from taskgen_proto.grader import FieldEquals, compile_assertions
from taskgen_proto.pipeline import run_generation


@pytest.fixture(scope="module")
def run():
    return run_generation(spec(), FakeGeneratorClient(spec()))


def _rec(run, cid):
    return next(r for r in run.records if r.candidate_id == cid)


def test_every_family_gets_admitted_tasks(run):
    assert run.report.admitted_by_family == {
        "eligible_change": 2, "inactive_subscription": 1, "already_on_plan": 2,
        "enterprise_escalation": 2, "unpaid_downgrade": 2}
    assert run.report.unfilled_slots == ["inactive_subscription/seed2"]
    assert run.report.audit_false_accepts == 0 and run.report.audit_false_rejects == 0


@pytest.mark.parametrize("cid,code", [
    ("eligible_change-s1-r0", "request_not_solver_reachable"),
    ("eligible_change-s2-r0", "instruction_leaks_answer"),
    ("unpaid_downgrade-s2-r0", "label_disagrees_with_policy"),
    ("already_on_plan-s2-r0", "reference_replay_failed"),
    ("inactive_subscription-s2-r0", "state_integrity"),
    ("enterprise_escalation-s2-r0", "malformed_json"),
])
def test_defective_candidates_are_rejected_with_reason(run, cid, code):
    rec = _rec(run, cid)
    assert rec.status == "rejected"
    assert code in {i.code for i in rec.issues}
    assert rec.raw_response  # retained verbatim


def test_repairs_link_to_parent_and_record_provenance(run):
    rec = _rec(run, "unpaid_downgrade-s2-r1")
    assert rec.status == "admitted"
    p = rec.provenance
    assert p.parent_candidate_id == "unpaid_downgrade-s2-r0" and p.revision == 1
    assert p.generator == "fake-offline" and p.seed == 2 and len(p.prompt_sha256) == 64
    assert p.spec_sha256 == spec().digest()


def test_repair_prompt_carries_rejection_feedback():
    req = GenerationRequest(spec_id="x", family_id="eligible_change", seed=1, revision=1,
                            feedback=["[instruction_leaks_answer] ..."])
    assert "instruction_leaks_answer" in build_prompt(spec(), req)


def test_persistent_defect_exhausts_repairs(run):
    recs = [r for r in run.records if r.candidate_id.startswith("inactive_subscription-s2")]
    assert [r.status for r in recs] == ["rejected", "rejected"]


def test_admitted_tasks_carry_full_evaluator_bundle(run):
    for t in run.packages:
        ev = t.evaluator
        assert ev.required_outcomes and ev.forbidden_effects and ev.assertions
        assert ev.reference_procedure and ev.audit.outcomes and ev.decision_trace
        kinds = {o.kind for o in ev.audit.outcomes}
        assert {"valid_alternative", "incomplete", "wrong_target", "collateral"} <= kinds


def test_generation_is_reproducible():
    a = run_generation(spec(), FakeGeneratorClient(spec()))
    b = run_generation(spec(), FakeGeneratorClient(spec()))
    assert [t.task_id for t in a.packages] == [t.task_id for t in b.packages]


def test_audit_catches_a_lenient_grader():
    """A grader without the preservation check must be caught by the audit."""
    def lenient(req, outcome, state):
        return [a for a in compile_assertions(req, outcome, state)
                if a.kind != "preserve_unrelated"]
    run = run_generation(spec(), FakeGeneratorClient(spec(), defects={}),
                         plan=[("eligible_change", 1)], compiler=lenient)
    assert run.report.admitted == 0
    codes = {i.code for r in run.records for i in r.issues}
    assert "grader_false_accept" in codes


def test_audit_catches_an_over_strict_grader():
    """A grader that demands an incidental detail (a note) must be caught too."""
    def strict(req, outcome, state):
        out = compile_assertions(req, outcome, state)
        out.append(FieldEquals(id="note_text", ref={"table": "tickets",
                   "record_id": req.ticket_id, "field": "notes"},
                   value=["Handled request for " + req.requested_plan + "."]))
        return out
    run = run_generation(spec(), FakeGeneratorClient(spec(), defects={}),
                         plan=[("unpaid_downgrade", 1)], compiler=strict)
    assert run.report.admitted == 0
    codes = {i.code for r in run.records for i in r.issues}
    assert "grader_false_reject" in codes


def test_changed_policy_rejects_scenarios_that_no_longer_fit():
    """If A3 is disabled, the fake's escalation scenarios no longer exercise their family."""
    data = spec().model_dump()
    data["policies"][2]["enabled"] = False
    from taskgen_proto.spec import WorkloadSpec
    s = WorkloadSpec.model_validate(data)
    run = run_generation(s, FakeGeneratorClient(s, defects={}),
                         plan=[("enterprise_escalation", 1)])
    assert run.report.admitted == 0
    assert "family_branch_mismatch" in {i.code for r in run.records for i in r.issues}
