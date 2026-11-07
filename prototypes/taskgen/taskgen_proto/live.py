"""Live, budgeted generation behind the existing `GeneratorClient` interface.

Provider-neutral. A concrete provider is plugged in as a `Transport`; none
ships in this increment. Responsibilities are split deliberately:

Transport (provider-specific; knows the real request and the price list)
  * `estimate(call)`: maximum cost of the COMPLETE billable request it will
    send for `call` (prompt, system text, tool/response schemas, framing,
    output and reasoning limits), and whether that is a defensible upper bound.
  * `send(call)`: performs the request and reports billing as `reported`
    (with cost), `not_billable`, or `unknown`.

Adapter (this module; provider-neutral)
  * reserves the estimate before dispatch and refuses when the remaining
    budget cannot cover it;
  * in strict mode (default) refuses any call whose estimate is not declared
    an upper bound;
  * settles reported cost, records unknown billing as exposure at the reserved
    amount, and keeps outstanding reservations separate;
  * on a reported cost above its reservation: keeps the actual cost, records
    the overrun, and stops all further dispatch;
  * retries only errors marked retryable, each as its own reserved call;
  * passes the model id through unchanged; redacts credential values.

The cap is only as strong as the transport's declared bounds. The budget
summary says which guarantee, if any, held for the batch.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

import yaml
from pydantic import Field

from .common import Model
from .generator import GenerationRequest
from .metering import (
    UNKNOWN_BILLING, ZERO, Billing, BudgetExhausted, BudgetSummary, CallRecord,
    CostEstimate, DispatchStopped, ProviderFailure,
)

MTOK = Decimal(1_000_000)


# --------------------------------------------------------------------------
# Transport interface
# --------------------------------------------------------------------------


class GenerationCall(Model):
    """Provider-neutral description of one generation request."""

    model: str  # opaque; the transport must send it unchanged
    prompt: str
    max_output_tokens: int
    max_reasoning_tokens: int | None  # None = caller sets no reasoning limit
    timeout_s: float


class TransportResponse(Model):
    text: str
    billing: Billing
    stop_reason: str | None = None
    request_id: str | None = None


class TransportError(Exception):
    """Raised by `send`. Billing defaults to unknown."""

    def __init__(self, message: str, *, retryable: bool = False,
                 billing: Billing | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.billing = billing or UNKNOWN_BILLING


class Transport(Protocol):
    name: str
    # Names (not values) of env vars holding credentials. Used only to check
    # presence and to redact values from stored text.
    credential_env_vars: tuple[str, ...]

    def estimate(self, call: GenerationCall) -> CostEstimate:
        """Max cost of exactly the request `send(call)` would make."""
        ...

    def send(self, call: GenerationCall) -> TransportResponse: ...


# A transport factory receives the opaque model id and that model's pricing.
TransportFactory = Callable[..., Transport]


# --------------------------------------------------------------------------
# Pricing (explicit; never built in)
# --------------------------------------------------------------------------


class PricingMissing(KeyError):
    pass


class ModelPricing(Model):
    """USD per million tokens, by provider-specific token category
    (e.g. input, output, reasoning, cache_read). The transport decides which
    categories it needs and fails if any are missing."""

    model: str = Field(min_length=1)
    usd_per_million_tokens: dict[str, Decimal] = Field(min_length=1)
    source: str = Field(min_length=1)  # price-list URL and date checked

    def rate(self, category: str) -> Decimal:
        if category not in self.usd_per_million_tokens:
            raise PricingMissing(f"pricing for {self.model!r} has no {category!r} rate")
        rate = self.usd_per_million_tokens[category]
        if rate < 0:
            raise ValueError(f"negative rate for {category!r}")
        return rate

    def cost(self, tokens: Mapping[str, int]) -> Decimal:
        """Helper for transports: cost of a token count per category."""
        return sum((self.rate(k) * n for k, n in tokens.items()), ZERO) / MTOK


class PricingTable(Model):
    currency: Literal["USD"]
    models: list[ModelPricing]

    def for_model(self, model: str) -> ModelPricing:
        for p in self.models:
            if p.model == model:
                return p
        raise PricingMissing(f"no pricing entry for model {model!r}; add one to the pricing file")


def load_pricing(path: str | Path) -> PricingTable:
    with open(path, encoding="utf-8") as fh:
        return PricingTable.model_validate(yaml.safe_load(fh))


class LiveConfig(Model):
    model: str = Field(min_length=1)
    budget_usd: Decimal = Field(gt=0)
    max_output_tokens: int = Field(gt=0, le=32_000)
    max_reasoning_tokens: int | None = Field(default=None, ge=0)
    max_retries: int = Field(default=2, ge=0, le=5)
    timeout_s: float = Field(default=120.0, gt=0)
    backoff_s: float = Field(default=2.0, ge=0)
    strict_budget: bool = True  # refuse calls whose estimate is not a declared upper bound


# --------------------------------------------------------------------------
# Budget ledger
# --------------------------------------------------------------------------


class BudgetLedger:
    """Single-threaded. committed = reported + unknown exposure + outstanding."""

    def __init__(self, cap_usd: Decimal) -> None:
        self.cap = Decimal(cap_usd)
        self.reported = ZERO
        self.exposure = ZERO
        self.outstanding = ZERO
        self.refused = 0
        self.stopped_reason: str | None = None

    @property
    def committed(self) -> Decimal:
        return self.reported + self.exposure + self.outstanding

    @property
    def remaining(self) -> Decimal:
        return self.cap - self.committed

    def stop(self, reason: str) -> None:
        if self.stopped_reason is None:
            self.stopped_reason = reason

    def reserve(self, amount: Decimal) -> bool:
        if amount > self.remaining:
            self.refused += 1
            self.stop(f"remaining budget ${self.remaining:.6f} cannot cover the estimated "
                      f"maximum call cost ${amount:.6f}")
            return False
        self.outstanding += amount
        return True

    def settle(self, reserved: Decimal, billing: Billing) -> tuple[Decimal, Decimal | None]:
        """Returns (unknown exposure added, overrun amount or None)."""
        self.outstanding -= reserved
        if billing.status == "reported":
            cost = billing.cost_usd or ZERO
            self.reported += cost
            return ZERO, (cost - reserved) if cost > reserved else None
        if billing.status == "unknown":
            self.exposure += reserved
            return reserved, None
        return ZERO, None


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------


def _redactor(secrets: Sequence[str]) -> Callable[[str], str]:
    values = sorted({s for s in secrets if s and len(s) >= 4}, key=len, reverse=True)

    def redact(text: str) -> str:
        for v in values:
            text = text.replace(v, "[REDACTED]")
        return text
    return redact


class LiveGeneratorClient:
    """`GeneratorClient` + `MeteredClient` over an injected transport."""

    def __init__(self, transport: Transport, config: LiveConfig, *,
                 redact_values: Sequence[str] = (),
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.transport = transport
        self.config = config
        self.name = f"live:{transport.name}"
        self.model = config.model
        self.ledger = BudgetLedger(config.budget_usd)
        self._redact = _redactor(redact_values)
        self._sleep = sleep
        self._clock = clock
        self._pending: list[CallRecord] = []
        self._all: list[CallRecord] = []

    # --- GeneratorClient --------------------------------------------------
    def complete(self, prompt: str, request: GenerationRequest) -> str:
        cfg = self.config
        slot = f"{request.family_id}-s{request.seed}-r{request.revision}"
        call = GenerationCall(model=cfg.model, prompt=prompt,
                              max_output_tokens=cfg.max_output_tokens,
                              max_reasoning_tokens=cfg.max_reasoning_tokens,
                              timeout_s=cfg.timeout_s)
        for attempt in range(cfg.max_retries + 1):
            estimate = self._admit(call)
            t0 = self._clock()
            try:
                resp = self.transport.send(call)
            except TransportError as exc:
                retry = exc.retryable and attempt < cfg.max_retries
                self._record(slot, attempt, call, estimate, t0, exc.billing,
                             error=exc.message, retryable=exc.retryable)
                if retry and self.ledger.stopped_reason is None:
                    self._sleep(cfg.backoff_s * (2 ** attempt))
                    continue
                raise ProviderFailure(self._redact(
                    f"{exc.message} (after {attempt + 1} attempt(s))"))
            except Exception as exc:  # unknown failure: billing unknown
                self._record(slot, attempt, call, estimate, t0, UNKNOWN_BILLING,
                             error=f"{type(exc).__name__}: {exc}", retryable=False)
                raise ProviderFailure(self._redact(f"unexpected transport failure: {exc}"))
            self._record(slot, attempt, call, estimate, t0, resp.billing,
                         stop_reason=resp.stop_reason, request_id=resp.request_id)
            return self._redact(resp.text)
        raise AssertionError("unreachable")

    def _admit(self, call: GenerationCall) -> CostEstimate:
        """Gate one dispatch: stopped? estimate valid? bound guaranteed? budget?"""
        if self.ledger.stopped_reason is not None:
            self.ledger.refused += 1
            raise DispatchStopped(self.ledger.stopped_reason)
        try:
            estimate = self.transport.estimate(call)
            if not isinstance(estimate, CostEstimate):
                raise TypeError(f"estimate() returned {type(estimate).__name__}")
        except Exception as exc:
            self.ledger.stop(f"cost estimation failed: {self._redact(str(exc))}")
            raise DispatchStopped(self.ledger.stopped_reason, code="estimate_failed") from exc
        if self.config.strict_budget and not estimate.upper_bound:
            self.ledger.refused += 1
            self.ledger.stop("strict budget: transport did not declare its estimate an upper "
                             f"bound ({estimate.basis})")
            raise DispatchStopped(self.ledger.stopped_reason, code="estimate_not_upper_bound")
        if not self.ledger.reserve(estimate.max_cost_usd):
            raise BudgetExhausted(self.ledger.stopped_reason or "budget exhausted")
        return estimate

    # --- MeteredClient ----------------------------------------------------
    def drain_calls(self) -> list[CallRecord]:
        out, self._pending = self._pending, []
        return out

    def budget_summary(self) -> BudgetSummary:
        calls, led = self._all, self.ledger
        overruns = [c for c in calls if c.overrun_usd is not None]
        unbounded = [c for c in calls if not c.estimate.upper_bound]
        if not calls:
            guarantee, note = "no_calls", "No calls were dispatched."
        elif overruns:
            guarantee, note = "violated_by_overrun", (
                f"{len(overruns)} call(s) reported cost above their reserved estimate; the "
                "transport's bound was wrong. Dispatch was stopped at the first overrun.")
        elif unbounded:
            guarantee, note = "not_guaranteed_best_effort", (
                f"{len(unbounded)} call(s) ran without a declared upper bound "
                "(best-effort mode). The cap was checked against estimates only.")
        else:
            guarantee, note = "declared_upper_bounds_held", (
                "Every call had a transport-declared upper bound and no reported cost "
                "exceeded it. Billed cost is within the cap IF those declared bounds are "
                "correct; unknown-billing calls are counted at their bound.")
        return BudgetSummary(
            mode="strict" if self.config.strict_budget else "best_effort",
            cap_usd=led.cap, reported_cost_usd=led.reported,
            unknown_billing_exposure_usd=led.exposure,
            outstanding_reservations_usd=led.outstanding,
            committed_usd=led.committed, remaining_usd=led.remaining,
            calls_dispatched=len(calls),
            calls_failed=sum(1 for c in calls if c.status == "error"),
            calls_retried=sum(1 for c in calls if c.attempt > 0),
            unknown_billing_calls=sum(1 for c in calls if c.billing.status == "unknown"),
            calls_without_upper_bound=len(unbounded),
            overruns=len(overruns),
            overrun_total_usd=sum((c.overrun_usd or ZERO for c in overruns), ZERO),
            refused_dispatches=led.refused, stopped_reason=led.stopped_reason,
            guarantee=guarantee, guarantee_note=note)

    # --- internals --------------------------------------------------------
    def _record(self, slot: str, attempt: int, call: GenerationCall, estimate: CostEstimate,
                t0: float, billing: Billing, *, error: str | None = None,
                retryable: bool | None = None, stop_reason: str | None = None,
                request_id: str | None = None) -> None:
        reserved = estimate.max_cost_usd
        exposure, overrun = self.ledger.settle(reserved, billing)
        if overrun is not None:
            self.ledger.stop(f"reported cost exceeded its reservation by ${overrun:.6f} on "
                             f"{slot} attempt {attempt}; the cost bound is unreliable")
        rec = CallRecord(
            call_id=f"{slot}-a{attempt}", slot=slot, attempt=attempt,
            transport=self.transport.name, model=call.model,
            max_output_tokens=call.max_output_tokens,
            max_reasoning_tokens=call.max_reasoning_tokens, estimate=estimate,
            reserved_usd=reserved, billing=billing, unknown_exposure_usd=exposure,
            overrun_usd=overrun, status="error" if error else "ok",
            error=self._redact(error) if error else None, retryable=retryable,
            stop_reason=stop_reason, request_id=request_id,
            latency_s=round(self._clock() - t0, 3))
        self._pending.append(rec)
        self._all.append(rec)
