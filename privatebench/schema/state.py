"""Environment state snapshots, diffs, and the append-only event log."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Row = dict[str, Any]


class StateSnapshot(_Model):
    snapshot_id: str
    now: str                                  # frozen clock for this snapshot
    tables: dict[str, dict[str, Row]]         # table -> primary key -> row


class ChangeKind(str, Enum):
    insert = "insert"
    update = "update"
    delete = "delete"


class RowChange(_Model):
    table: str
    key: str
    kind: ChangeKind
    before: Row | None = None
    after: Row | None = None


class StateDiff(_Model):
    changes: list[RowChange]


def diff_snapshots(before: StateSnapshot, after: StateSnapshot) -> StateDiff:
    changes: list[RowChange] = []
    for table in sorted(set(before.tables) | set(after.tables)):
        old, new = before.tables.get(table, {}), after.tables.get(table, {})
        for key in sorted(set(old) | set(new)):
            if key not in old:
                changes.append(RowChange(table=table, key=key, kind=ChangeKind.insert, after=new[key]))
            elif key not in new:
                changes.append(RowChange(table=table, key=key, kind=ChangeKind.delete, before=old[key]))
            elif old[key] != new[key]:
                changes.append(RowChange(table=table, key=key, kind=ChangeKind.update,
                                         before=old[key], after=new[key]))
    return StateDiff(changes=changes)


class Event(_Model):
    """One tool call, written by the gateway (never by the solver)."""
    trial_id: str
    seq: int
    tool: str
    args: dict[str, Any]
    status: Literal["ok", "error", "denied"]
    error: str | None = None
    result: Any = None
