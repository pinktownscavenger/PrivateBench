"""Provider-neutral cost estimates, billing reports, call records and budget summaries.

Three money quantities are kept apart and never merged into one "spend":

* reported cost       - what the transport says the provider billed (from usage);
* unknown exposure    - calls whose billing is unknown, counted at their reserved
                        maximum (only a true bound if the estimate was an upper bound);
* outstanding         - reservations for calls that have not settled.

These are evaluator-side records. They never contain credentials or request
headers, and nothing here reaches the solver.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, model_validator

from .common import Model

ZERO = Decimal(0)
BillingStatus = Literal["reported", "not_billable", "unknown"]
Guarantee = Literal[
    "no_calls",                      # nothing dispatched
    "declared_upper_bounds_held",    # every call had a declared upper bound; none exceeded
    "not_guaranteed_best_effort",    # some call ran without a declared upper bound
    "violated_by_overrun",           # a reported cost exceeded its reservation
]


class CostEstimate(Model):
    """A transport's estimate of the maximum cost of ONE complete billable request.

    Must cover everything the provider bills for that request: prompt, system
    text, tool / response schemas, provider framing, and the output and
    reasoning limits actually sent. `upper_bound=True` is the transport's
    claim that the request cannot cost more than `max_cost_usd`.
    """

    max_cost_usd: Decimal = Field(ge=0)
    upper_bound: bool
    basis: str = Field(min_length=1)
    components: dict[str, Decimal] = Field(default_factory=dict)


class Billing(Model):
    """What the transport knows about what a call was billed."""

    status: BillingStatus
    cost_usd: Decimal | None = Field(default=None, ge=0)
    usage: dict[str, int] = Field(default_factory=dict)  # provider-specific token counts

    @model_validator(mode="after")
    def _consistent(self) -> "Billing":
        if self.status == "reported" and self.cost_usd is None:
            raise ValueError("reported billing needs cost_usd")
        if self.status != "reported" and self.cost_usd is not None:
            raise ValueError(f"{self.status} billing must not carry cost_usd")
        return self


UNKNOWN_BILLING = Billing(status="unknown")


class CostBreakdown(Model):
    reported_usd: Decimal = ZERO
    unknown_exposure_usd: Decimal = ZERO

    def __add__(self, other: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(reported_usd=self.reported_usd + other.reported_usd,
                             unknown_exposure_usd=self.unknown_exposure_usd
                             + other.unknown_exposure_usd)

    def divided(self, n: int) -> "CostBreakdown":
        return CostBreakdown(reported_usd=self.reported_usd / n,
                             unknown_exposure_usd=self.unknown_exposure_usd / n)

    @classmethod
    def of(cls, calls: Iterable["CallRecord"]) -> "CostBreakdown":
        out = cls()
        for c in calls:
            out = out + cls(reported_usd=c.billing.cost_usd or ZERO,
                            unknown_exposure_usd=c.unknown_exposure_usd)
        return out


class CallRecord(Model):
    """One dispatched provider call (including retries and failures)."""

    call_id: str
    slot: str  # e.g. "eligible_change-s1-r0"
    attempt: int
    transport: str
    model: str
    max_output_tokens: int
    max_reasoning_tokens: int | None
    estimate: CostEstimate
    reserved_usd: Decimal
    billing: Billing
    unknown_exposure_usd: Decimal  # == reserved_usd when billing is unknown, else 0
    overrun_usd: Decimal | None  # reported cost above the reservation, if any
    status: Literal["ok", "error"]
    error: str | None = None
    retryable: bool | None = None
    stop_reason: str | None = None
    request_id: str | None = None
    latency_s: float


class BudgetSummary(Model):
    mode: Literal["strict", "best_effort"]
    cap_usd: Decimal
    reported_cost_usd: Decimal
    unknown_billing_exposure_usd: Decimal
    outstanding_reservations_usd: Decimal
    committed_usd: Decimal  # reported + exposure + outstanding; what the cap is checked against
    remaining_usd: Decimal
    calls_dispatched: int
    calls_failed: int
    calls_retried: int
    unknown_billing_calls: int
    calls_without_upper_bound: int
    overruns: int
    overrun_total_usd: Decimal
    refused_dispatches: int
    stopped_reason: str | None
    guarantee: Guarantee
    guarantee_note: str


class GenerationUnavailable(Exception):
    """The generator could not produce a response for this request."""

    code = "generation_unavailable"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class ProviderFailure(GenerationUnavailable):
    code = "provider_error"


class DispatchStopped(GenerationUnavailable):
    """No further calls may be dispatched in this batch."""

    code = "dispatch_stopped"


class BudgetExhausted(DispatchStopped):
    code = "budget_exhausted"


@runtime_checkable
class MeteredClient(Protocol):
    def drain_calls(self) -> list[CallRecord]: ...

    def budget_summary(self) -> BudgetSummary: ...
