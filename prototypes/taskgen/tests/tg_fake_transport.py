"""Scripted provider stand-in for tests. Makes no network calls.

It models a provider request with billable parts beyond the prompt: system
text, a response schema (like a tool/structured-output schema), fixed framing
overhead, an output limit and a reasoning limit. Its `estimate()` bounds all
of them; `send()` reports cost from simulated usage that never exceeds those
limits unless a script step says otherwise.

It answers with a valid proposal (built from the offline fake's scenario code)
for the family and seed named in the prompt.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from taskgen_proto.generator import FakeGeneratorClient
from taskgen_proto.live import GenerationCall, ModelPricing, TransportError, TransportResponse
from taskgen_proto.metering import Billing, CostEstimate
from taskgen_proto.proposal import ScenarioProposal
from taskgen_proto.spec import load_spec

SECRET_ENV = "TG_FAKE_PROVIDER_KEY"
# Test-only rates. NOT real provider prices.
TEST_RATES = {"input": Decimal("1"), "output": Decimal("2"), "reasoning": Decimal("2")}
SYSTEM_TEXT = "You are a scenario generator. Reply with JSON only."
RESPONSE_SCHEMA = json.dumps(ScenarioProposal.model_json_schema())
FRAMING_TOKENS = 64
SIMULATED_REASONING = 40


def tok(text: str) -> int:
    return max(1, len(text) // 4)


class ScriptedTransport:
    name = "scripted"
    credential_env_vars = (SECRET_ENV,)
    rate_categories = ("input", "output", "reasoning")

    def __init__(self, *, model: str, pricing: ModelPricing, script=None, on_send=None,
                 declare_upper_bound: bool = True, count_schema: bool = True,
                 estimate_error: Exception | None = None):
        if pricing.model != model:
            raise ValueError("pricing is for a different model")
        for c in self.rate_categories:
            pricing.rate(c)  # raises PricingMissing if absent
        self.model, self.pricing = model, pricing
        self.script = list(script or [])
        self.on_send = on_send
        self.declare_upper_bound = declare_upper_bound
        self.count_schema = count_schema  # False: buggy estimate (no schema/framing, avg)
        self.estimate_error = estimate_error
        self.estimated: list[GenerationCall] = []
        self.sent: list[GenerationCall] = []
        self._fake = FakeGeneratorClient(load_spec(), defects={})

    # what the provider would actually receive and bill as input
    def _billable_input(self, call: GenerationCall) -> str:
        return f"{SYSTEM_TEXT}\n{RESPONSE_SCHEMA}\n{call.prompt}"

    def estimate(self, call: GenerationCall) -> CostEstimate:
        if self.estimate_error:
            raise self.estimate_error
        self.estimated.append(call)
        if self.count_schema:  # <= 1 token per byte, over the full billable input
            input_bound = len(self._billable_input(call).encode("utf-8")) + FRAMING_TOKENS
        else:  # buggy: average chars-per-token guess over the prompt only
            input_bound = tok(call.prompt)
        reasoning_bound = call.max_reasoning_tokens
        bounded = reasoning_bound is not None
        tokens = {"input": input_bound, "output": call.max_output_tokens,
                  "reasoning": reasoning_bound or 0}
        components = {k: self.pricing.cost({k: n}) for k, n in tokens.items()}
        return CostEstimate(
            max_cost_usd=sum(components.values(), Decimal(0)),
            upper_bound=self.declare_upper_bound and bounded,
            basis=("system+schema+prompt bytes + framing; output limit; reasoning limit"
                   if bounded else "reasoning tokens unbounded (no max_reasoning_tokens)"),
            components=components)

    def _valid(self, prompt: str) -> str:
        family = re.search(r"## Target family: (\S+)", prompt).group(1)
        seed = int(re.search(r"## Variation seed\n(\d+)", prompt).group(1))
        return json.dumps(self._fake._proposal(family, seed, None))

    def _billing(self, call: GenerationCall, text: str) -> Billing:
        usage = {"input": tok(self._billable_input(call)) + FRAMING_TOKENS,
                 "output": min(tok(text), call.max_output_tokens),
                 "reasoning": min(SIMULATED_REASONING, call.max_reasoning_tokens or 10**6)}
        return Billing(status="reported", cost_usd=self.pricing.cost(usage), usage=usage)

    def send(self, call: GenerationCall) -> TransportResponse:
        self.sent.append(call)
        if self.on_send:
            self.on_send()
        step = self.script.pop(0) if self.script else "ok"
        if isinstance(step, Exception):
            raise step
        if step == "ok":
            text = self._valid(call.prompt)
            return TransportResponse(text=text, billing=self._billing(call, text),
                                     stop_reason="end", request_id=f"req-{len(self.sent)}")
        if step == "malformed":
            text = "I think the scenario is: {not json"
            return TransportResponse(text=text, billing=self._billing(call, text))
        if step == "unknown_billing":
            return TransportResponse(text=self._valid(call.prompt),
                                     billing=Billing(status="unknown"))
        if step == "overrun":
            return TransportResponse(text=self._valid(call.prompt),
                                     billing=Billing(status="reported", cost_usd=Decimal("5"),
                                                     usage={"input": 5_000_000}))
        raise ValueError(step)


def make(*, model: str, pricing: ModelPricing) -> ScriptedTransport:
    """Factory used by the CLI tests via --transport tg_fake_transport:make."""
    return ScriptedTransport(model=model, pricing=pricing)


def make_unbounded(*, model: str, pricing: ModelPricing) -> ScriptedTransport:
    return ScriptedTransport(model=model, pricing=pricing, declare_upper_bound=False)


def error(msg="boom", **kw) -> TransportError:
    return TransportError(msg, **kw)
