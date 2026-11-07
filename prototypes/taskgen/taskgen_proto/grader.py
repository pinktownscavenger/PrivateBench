"""Outcome grader: assertions over trusted environment state.

Assertions are compiled from the policy oracle's outcome and the request
binding, NOT from the generator's reference procedure. A reference that
disagrees with them is therefore caught on replay.

`grade` sees only the initial and final environment tables. It never reads
the solver's messages, notes as claims, or the sequence of tool calls.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, Union

from pydantic import Field

from .common import Model
from .env import Tables, WorldState
from .policy import PlanChangeRequest
from .spec import Outcome


class FieldRef(Model):
    table: str
    record_id: str
    field: str

    def key(self) -> tuple[str, str, str]:
        return (self.table, self.record_id, self.field)

    def __str__(self) -> str:
        return f"{self.table}.{self.record_id}.{self.field}"


class FieldEquals(Model):
    kind: Literal["field_equals"] = "field_equals"
    category: Literal["required_outcome"] = "required_outcome"
    id: str
    ref: FieldRef
    value: Any


class FieldUnchanged(Model):
    kind: Literal["field_unchanged"] = "field_unchanged"
    category: Literal["forbidden_effect"] = "forbidden_effect"
    id: str
    ref: FieldRef


class PreserveUnrelated(Model):
    """Every change outside `allowed` (including created/deleted records) fails."""

    kind: Literal["preserve_unrelated"] = "preserve_unrelated"
    category: Literal["forbidden_effect"] = "forbidden_effect"
    id: str
    allowed: list[FieldRef]


Assertion = Annotated[Union[FieldEquals, FieldUnchanged, PreserveUnrelated],
                      Field(discriminator="kind")]
AssertionCompiler = Callable[[PlanChangeRequest, Outcome, WorldState], list[Assertion]]


class Change(Model):
    table: str
    record_id: str
    field: str
    before: Any = None
    after: Any = None


class AssertionResult(Model):
    id: str
    category: str
    passed: bool
    detail: str = ""


class GradeResult(Model):
    passed: bool
    results: list[AssertionResult]

    @property
    def failed_ids(self) -> list[str]:
        return [r.id for r in self.results if not r.passed]


def diff_tables(before: Tables, after: Tables) -> list[Change]:
    changes: list[Change] = []
    for table in sorted(set(before) | set(after)):
        b, a = before.get(table, {}), after.get(table, {})
        for rid in sorted(set(b) | set(a)):
            if rid not in a:
                changes.append(Change(table=table, record_id=rid, field="<deleted>"))
            elif rid not in b:
                changes.append(Change(table=table, record_id=rid, field="<created>"))
            else:
                for f in sorted(set(b[rid]) | set(a[rid])):
                    if b[rid].get(f) != a[rid].get(f):
                        changes.append(Change(table=table, record_id=rid, field=f,
                                              before=b[rid].get(f), after=a[rid].get(f)))
    return changes


def _value(tables: Tables, ref: FieldRef) -> tuple[bool, Any]:
    rec = tables.get(ref.table, {}).get(ref.record_id)
    if rec is None:
        return False, None
    return True, rec.get(ref.field)


def grade(initial: Tables, final: Tables, assertions: list[Assertion]) -> GradeResult:
    results: list[AssertionResult] = []
    for a in assertions:
        if isinstance(a, FieldEquals):
            exists, actual = _value(final, a.ref)
            ok = exists and actual == a.value
            detail = "" if ok else f"{a.ref} is {actual!r}, expected {a.value!r}"
        elif isinstance(a, FieldUnchanged):
            e0, v0 = _value(initial, a.ref)
            e1, v1 = _value(final, a.ref)
            ok = e0 and e1 and v0 == v1
            detail = "" if ok else f"{a.ref} changed {v0!r} -> {v1!r}"
        else:
            allowed = {r.key() for r in a.allowed}
            bad = [c for c in diff_tables(initial, final)
                   if (c.table, c.record_id, c.field) not in allowed]
            ok = not bad
            detail = "" if ok else "unexpected changes: " + "; ".join(
                f"{c.table}.{c.record_id}.{c.field}: {c.before!r} -> {c.after!r}" for c in bad[:5])
        results.append(AssertionResult(id=a.id, category=a.category, passed=ok, detail=detail))
    return GradeResult(passed=all(r.passed for r in results), results=results)


def compile_assertions(req: PlanChangeRequest, outcome: Outcome,
                       state: WorldState) -> list[Assertion]:
    """Required outcomes and forbidden effects for one policy branch."""
    del state  # the default compiler needs only the binding and outcome
    t = lambda f: FieldRef(table="tickets", record_id=req.ticket_id, field=f)  # noqa: E731
    plan = FieldRef(table="subscriptions", record_id=req.subscription_id, field="plan")
    out: list[Assertion] = []
    if outcome == "escalated":
        out.append(FieldEquals(id="ticket_escalated", ref=t("status"), value="escalated"))
        allowed = [t("status"), t("notes")]
    else:
        out.append(FieldEquals(id="ticket_resolved", ref=t("status"), value="resolved"))
        out.append(FieldEquals(id="resolution_code", ref=t("resolution_code"), value=outcome))
        allowed = [t("status"), t("resolution_code"), t("notes")]
    if outcome == "plan_changed":
        out.append(FieldEquals(id="plan_set", ref=plan, value=req.requested_plan))
        allowed.append(plan)
    else:
        out.append(FieldUnchanged(id="plan_not_changed", ref=plan))
    out.append(PreserveUnrelated(id="preserve_unrelated_state", allowed=allowed))
    return out


def describe(assertions: list[Assertion]) -> tuple[list[str], list[str]]:
    """Human-readable required outcomes and forbidden effects."""
    required, forbidden = [], []
    for a in assertions:
        if isinstance(a, FieldEquals):
            required.append(f"{a.ref} == {a.value!r}")
        elif isinstance(a, FieldUnchanged):
            forbidden.append(f"{a.ref} must not change")
        else:
            forbidden.append("no change to any other record or field (allowed: "
                             + ", ".join(str(r) for r in a.allowed) + ")")
    return required, forbidden
