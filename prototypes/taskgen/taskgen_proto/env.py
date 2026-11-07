"""Resettable local environment: world state, tools, and a trusted event log.

Tools enforce only interface-level constraints (records exist, enums are
valid, a ticket must be open to be closed). They do NOT enforce the workload
policies: applying the policies is the solver's job, and the grader checks it.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal

from pydantic import Field

from .common import Model, sha256_json

TABLES = ("customers", "subscriptions", "invoices", "tickets")
Tables = dict[str, dict[str, dict[str, Any]]]


class Customer(Model):
    id: str
    name: str
    email: str


class Subscription(Model):
    id: str
    customer_id: str
    plan: str
    status: Literal["active", "cancelled"]


class Invoice(Model):
    id: str
    subscription_id: str
    status: Literal["paid", "unpaid"]
    amount_cents: int = Field(ge=0)


class Ticket(Model):
    id: str
    customer_id: str
    subject: str
    body: str
    status: Literal["open", "resolved", "escalated"] = "open"
    resolution_code: str | None = None
    notes: list[str] = Field(default_factory=list)


class WorldState(Model):
    customers: list[Customer] = Field(default_factory=list)
    subscriptions: list[Subscription] = Field(default_factory=list)
    invoices: list[Invoice] = Field(default_factory=list)
    tickets: list[Ticket] = Field(default_factory=list)

    def tables(self) -> Tables:
        return {t: {r.id: r.model_dump(mode="json") for r in getattr(self, t)} for t in TABLES}

    def get(self, table: str, record_id: str) -> Any | None:
        return next((r for r in getattr(self, table) if r.id == record_id), None)


def integrity_issues(state: WorldState, plans: Sequence[str]) -> list[str]:
    problems: list[str] = []
    for t in TABLES:
        ids = [r.id for r in getattr(state, t)]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            problems.append(f"duplicate ids in {t}: {dupes}")
    customers = {c.id for c in state.customers}
    subs = {s.id for s in state.subscriptions}
    for s in state.subscriptions:
        if s.customer_id not in customers:
            problems.append(f"subscription {s.id} references missing customer {s.customer_id}")
        if s.plan not in plans:
            problems.append(f"subscription {s.id} has unknown plan {s.plan!r}")
    for i in state.invoices:
        if i.subscription_id not in subs:
            problems.append(f"invoice {i.id} references missing subscription {i.subscription_id}")
    for k in state.tickets:
        if k.customer_id not in customers:
            problems.append(f"ticket {k.id} references missing customer {k.customer_id}")
    return problems


# --------------------------------------------------------------------------
# Tool interface
# --------------------------------------------------------------------------


class ToolCall(Model):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(Model):
    """Solver-visible description of a tool."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolResult(Model):
    ok: bool
    data: Any = None
    error: str | None = None


class Event(Model):
    seq: int
    tool: str
    args: dict[str, Any]
    ok: bool
    error: str | None = None


MUTATING_TOOLS = frozenset({"change_plan", "add_note", "resolve_ticket", "escalate_ticket"})


def _schema(props: dict[str, dict[str, Any]], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def tool_specs(plans: Sequence[str], resolution_codes: Sequence[str]) -> list[ToolSpec]:
    s = {"type": "string"}
    return [
        ToolSpec(name="get_ticket", description="Read a support ticket.",
                 parameters=_schema({"ticket_id": s}, ["ticket_id"])),
        ToolSpec(name="get_customer", description="Read a customer record.",
                 parameters=_schema({"customer_id": s}, ["customer_id"])),
        ToolSpec(name="list_subscriptions", description="List a customer's subscriptions.",
                 parameters=_schema({"customer_id": s}, ["customer_id"])),
        ToolSpec(name="list_invoices", description="List invoices for a subscription.",
                 parameters=_schema({"subscription_id": s}, ["subscription_id"])),
        ToolSpec(name="change_plan", description="Set a subscription's plan.",
                 parameters=_schema({"subscription_id": s,
                                     "new_plan": {"type": "string", "enum": list(plans)}},
                                    ["subscription_id", "new_plan"])),
        ToolSpec(name="add_note", description="Append an internal note to a ticket.",
                 parameters=_schema({"ticket_id": s, "text": s}, ["ticket_id", "text"])),
        ToolSpec(name="resolve_ticket",
                 description="Close an open ticket with a resolution code and optional note.",
                 parameters=_schema({"ticket_id": s,
                                     "resolution_code": {"type": "string",
                                                         "enum": list(resolution_codes)},
                                     "note": s},
                                    ["ticket_id", "resolution_code"])),
        ToolSpec(name="escalate_ticket",
                 description="Hand an open ticket to the account team with a reason.",
                 parameters=_schema({"ticket_id": s, "reason": s}, ["ticket_id", "reason"])),
    ]


class ToolError(Exception):
    pass


def _check_args(spec: ToolSpec, args: dict[str, Any]) -> None:
    props = spec.parameters["properties"]
    unknown = sorted(set(args) - set(props))
    if unknown:
        raise ToolError(f"unknown arguments {unknown}")
    missing = [r for r in spec.parameters["required"] if r not in args]
    if missing:
        raise ToolError(f"missing arguments {missing}")
    for name, value in args.items():
        if not isinstance(value, str):
            raise ToolError(f"argument {name} must be a string")
        enum = props[name].get("enum")
        if enum is not None and value not in enum:
            raise ToolError(f"argument {name}={value!r} not in {enum}")


class Environment:
    """In-memory world. `reset()` restores the exact initial state."""

    def __init__(
        self, initial: WorldState, *, plans: Sequence[str], resolution_codes: Sequence[str]
    ) -> None:
        self._initial = initial.model_copy(deep=True)
        self.specs = {s.name: s for s in tool_specs(plans, resolution_codes)}
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "get_ticket": self._get_ticket,
            "get_customer": self._get_customer,
            "list_subscriptions": self._list_subscriptions,
            "list_invoices": self._list_invoices,
            "change_plan": self._change_plan,
            "add_note": self._add_note,
            "resolve_ticket": self._resolve_ticket,
            "escalate_ticket": self._escalate_ticket,
        }
        self.reset()

    # --- lifecycle --------------------------------------------------------
    def reset(self) -> None:
        self._tables: Tables = self._initial.tables()
        self.events: list[Event] = []

    def initial_tables(self) -> Tables:
        return self._initial.tables()

    def snapshot(self) -> Tables:
        return copy.deepcopy(self._tables)

    def state_hash(self) -> str:
        return sha256_json(self._tables)

    # --- calls ------------------------------------------------------------
    def call(self, tool: str, args: dict[str, Any] | None = None) -> ToolResult:
        args = dict(args or {})
        try:
            spec = self.specs.get(tool)
            if spec is None:
                raise ToolError(f"unknown tool {tool!r}")
            _check_args(spec, args)
            result = ToolResult(ok=True, data=copy.deepcopy(self._handlers[tool](args)))
        except ToolError as exc:
            result = ToolResult(ok=False, error=str(exc))
        self.events.append(
            Event(seq=len(self.events), tool=tool, args=args, ok=result.ok, error=result.error)
        )
        return result

    def run(self, procedure: Iterable[ToolCall]) -> list[ToolResult]:
        return [self.call(c.tool, c.args) for c in procedure]

    # --- handlers ---------------------------------------------------------
    def _record(self, table: str, record_id: str) -> dict[str, Any]:
        rec = self._tables[table].get(record_id)
        if rec is None:
            raise ToolError(f"{table[:-1]} {record_id!r} not found")
        return rec

    def _get_ticket(self, a: dict[str, Any]) -> Any:
        return self._record("tickets", a["ticket_id"])

    def _get_customer(self, a: dict[str, Any]) -> Any:
        return self._record("customers", a["customer_id"])

    def _list_subscriptions(self, a: dict[str, Any]) -> Any:
        self._record("customers", a["customer_id"])
        return [s for s in self._tables["subscriptions"].values()
                if s["customer_id"] == a["customer_id"]]

    def _list_invoices(self, a: dict[str, Any]) -> Any:
        self._record("subscriptions", a["subscription_id"])
        return [i for i in self._tables["invoices"].values()
                if i["subscription_id"] == a["subscription_id"]]

    def _change_plan(self, a: dict[str, Any]) -> Any:
        sub = self._record("subscriptions", a["subscription_id"])
        sub["plan"] = a["new_plan"]
        return sub

    def _add_note(self, a: dict[str, Any]) -> Any:
        ticket = self._record("tickets", a["ticket_id"])
        ticket["notes"].append(a["text"])
        return ticket

    def _open_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = self._record("tickets", ticket_id)
        if ticket["status"] != "open":
            raise ToolError(f"ticket {ticket_id!r} is {ticket['status']}, not open")
        return ticket

    def _resolve_ticket(self, a: dict[str, Any]) -> Any:
        ticket = self._open_ticket(a["ticket_id"])
        ticket["status"] = "resolved"
        ticket["resolution_code"] = a["resolution_code"]
        if a.get("note"):
            ticket["notes"].append(a["note"])
        return ticket

    def _escalate_ticket(self, a: dict[str, Any]) -> Any:
        ticket = self._open_ticket(a["ticket_id"])
        ticket["status"] = "escalated"
        ticket["notes"].append(f"Escalated: {a['reason']}")
        return ticket
