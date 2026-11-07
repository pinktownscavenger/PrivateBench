"""Solver-visible content must not contain answers or grading material."""

import json

import pytest

from tg_helpers import spec
from taskgen_proto.generator import FakeGeneratorClient
from taskgen_proto.pipeline import run_generation, write_run


@pytest.fixture(scope="module")
def run():
    return run_generation(spec(), FakeGeneratorClient(spec()))


def test_solver_view_has_only_whitelisted_fields(run):
    for t in run.packages:
        assert set(json.loads(t.solver_json())) == {"task_id", "instruction", "policies", "tools"}


def test_solver_view_leaks_no_evaluator_material(run):
    for t in run.packages:
        text = t.solver_json()
        ev = t.evaluator
        for secret in [ev.family_id, "reference_procedure", "assertion", "claimed_outcome",
                       "expected_outcome", "decision_trace", "provenance", "A1", "A3",
                       "prototype_assumption", ev.request.subscription_id]:
            assert secret not in text, (t.task_id, secret)
        # the expected outcome may appear only as a tool enum / policy text, never in the instruction
        assert ev.expected_outcome not in t.solver.instruction
        # initial state is reached through tools, not handed over
        assert "initial_state" not in text and "INV-" not in text


def test_written_layout_separates_solver_and_evaluator(run, tmp_path):
    write_run(run, tmp_path)
    for t in run.packages:
        d = tmp_path / "tasks" / t.task_id
        assert json.loads((d / "solver.json").read_text()) == json.loads(t.solver_json())
        assert "reference_procedure" in (d / "evaluator.json").read_text()
    rejected = [p for p in (tmp_path / "candidates").glob("*.json")
                if json.loads(p.read_text())["status"] == "rejected"]
    assert len(rejected) == run.report.rejected == 7
    for p in rejected:
        assert json.loads(p.read_text())["issues"]
