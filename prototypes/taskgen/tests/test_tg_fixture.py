"""The independently authored fixture checks the pipeline from outside the generator."""

from tg_helpers import spec
from taskgen_proto.fixture import load_fixture, run_fixture
from taskgen_proto.grader import compile_assertions


def test_pipeline_agrees_with_independent_fixture():
    rep = run_fixture(spec(), load_fixture())
    assert rep.all_agree, rep.disagreements
    assert len(rep.results) == 5
    n_pass = sum(1 for r in rep.results for s in r.solutions if s.expected == "pass")
    n_fail = sum(1 for r in rep.results for s in r.solutions if s.expected == "fail")
    assert n_pass >= 5 and n_fail >= 8


def test_fixture_broken_reference_is_rejected():
    rep = run_fixture(spec(), load_fixture())
    r = next(r for r in rep.results if r.id == "fx-broken-reference")
    assert r.admission_status == "rejected" and "reference_replay_failed" in r.rejection_codes


def test_fixture_detects_a_lenient_grader():
    def lenient(req, outcome, state):
        return [a for a in compile_assertions(req, outcome, state)
                if a.kind != "preserve_unrelated"]
    rep = run_fixture(spec(), load_fixture(), compiler=lenient)
    assert any("collateral-closes-other-ticket" in d for d in rep.disagreements)


def test_fixture_detects_a_wrong_policy_order():
    data = spec().model_dump()
    data["policies"][2], data["policies"][3] = data["policies"][3], data["policies"][2]
    from taskgen_proto.spec import WorkloadSpec
    rep = run_fixture(WorkloadSpec.model_validate(data), load_fixture())
    assert any(d.startswith("fx-enterprise-beats-unpaid: oracle") for d in rep.disagreements)
