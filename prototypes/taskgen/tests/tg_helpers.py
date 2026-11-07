"""Shared test helpers (no network, no paid calls)."""

from taskgen_proto.env import Environment, ToolCall
from taskgen_proto.fixture import load_fixture
from taskgen_proto.spec import load_spec


def spec():
    return load_spec()


def fixture_task(task_id: str):
    return next(t for t in load_fixture().tasks if t.id == task_id)


def env_for(state, s=None):
    s = s or spec()
    return Environment(state, plans=s.plan_names, resolution_codes=s.resolution_codes)


def calls(*items):
    return [ToolCall(tool=t, args=a) for t, a in items]
