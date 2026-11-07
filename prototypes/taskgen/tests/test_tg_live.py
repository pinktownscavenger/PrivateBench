"""Live adapter with mocked provider responses. No network, no paid calls."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from tg_fake_transport import SECRET_ENV, TEST_RATES, ScriptedTransport, error
from tg_helpers import spec
from taskgen_proto.cli import main
from taskgen_proto.live import (
    LiveConfig, LiveGeneratorClient, ModelPricing, PricingMissing, PricingTable, load_pricing,
)
from taskgen_proto.metering import Billing
from taskgen_proto.pipeline import render_report_md, run_generation, write_run

MODEL = "opaque/model-id:v1@test"  # arbitrary; must pass through unchanged
PRICING = ModelPricing(model=MODEL, usd_per_million_tokens=TEST_RATES,
                       source="test fixture rates, not real prices")
ONE_PER_FAMILY = [(f.id, 1) for f in spec().families]
SECRET = "sk-test-SECRET-123"


def transport(**kw):
    return ScriptedTransport(model=MODEL, pricing=PRICING, **kw)


def client(t, budget="10", **cfg):
    cfg.setdefault("max_reasoning_tokens", 1000)
    config = LiveConfig(model=MODEL, budget_usd=Decimal(budget),
                        max_output_tokens=cfg.pop("max_output_tokens", 4000), **cfg)
    return LiveGeneratorClient(t, config, redact_values=[SECRET], sleep=lambda s: None)


# --- success and separated accounting --------------------------------------------

def test_successful_batch_reports_costs_separately():
    t = transport()
    c = client(t)
    run = run_generation(spec(), c, ONE_PER_FAMILY)
    r = run.report
    assert (r.attempted, r.admitted, r.rejected) == (5, 5, 0)
    assert r.cost_total.reported_usd > 0 and r.cost_total.unknown_exposure_usd == 0
    assert r.outstanding_reservations_usd == 0
    assert r.committed_usd == r.cost_total.reported_usd
    assert r.cost_per_admitted_task.reported_usd == r.cost_total.reported_usd / 5
    assert r.budget_mode == "strict" and r.budget_guarantee == "declared_upper_bounds_held"
    for rec in run.records:
        (call,) = rec.generation_calls
        assert call.billing.status == "reported" and call.overrun_usd is None
        assert rec.provenance.lineage_generation_cost.reported_usd == call.billing.cost_usd


def test_unknown_billing_is_exposure_not_reported_cost():
    t = transport(script=["ok", "unknown_billing"])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY[:2])
    known, unknown = (r.generation_calls[0] for r in run.records)
    assert unknown.billing.status == "unknown"
    assert unknown.unknown_exposure_usd == unknown.reserved_usd
    r = run.report
    assert r.cost_total.reported_usd == known.billing.cost_usd
    assert r.cost_total.unknown_exposure_usd == unknown.reserved_usd
    assert r.unknown_billing_calls == 1
    assert r.committed_usd == r.cost_total.reported_usd + r.cost_total.unknown_exposure_usd


def test_outstanding_reservation_is_separate_while_in_flight():
    seen = []
    c = None
    t = transport(on_send=lambda: seen.append(
        (c.ledger.outstanding, c.ledger.reported, c.ledger.exposure)))
    c = client(t)
    run_generation(spec(), c, ONE_PER_FAMILY[:2])
    (o1, rep1, _), (o2, rep2, _) = seen
    assert o1 > 0 and rep1 == 0          # first call: only reserved
    assert o2 > 0 and rep2 > 0           # second call: first settled, second reserved
    assert c.ledger.outstanding == 0     # all settled afterwards


def test_not_billable_failure_adds_no_cost_or_exposure():
    t = transport(script=[error("rejected before processing",
                                billing=Billing(status="not_billable"))])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY[:1])
    call = run.records[0].generation_calls[0]
    assert run.records[0].issues[0].code == "provider_error"
    assert call.billing.status == "not_billable" and call.unknown_exposure_usd == 0
    assert run.report.committed_usd == 0


# --- estimation is the transport's job and covers the whole request ----------------

def test_estimate_covers_complete_request_and_holds():
    t = transport()
    run = run_generation(spec(), client(t, max_reasoning_tokens=500), ONE_PER_FAMILY)
    assert len(t.estimated) == len(t.sent) == 5
    for est_call, sent_call in zip(t.estimated, t.sent):
        assert est_call == sent_call  # estimated exactly what was sent
        assert sent_call.model == MODEL and sent_call.max_reasoning_tokens == 500
    for rec in run.records:
        call = rec.generation_calls[0]
        assert set(call.estimate.components) == {"input", "output", "reasoning"}
        # bound includes schema + system text, not just the prompt
        assert call.billing.usage["input"] * TEST_RATES["input"] / 1_000_000 \
            <= call.estimate.components["input"]
        assert call.billing.cost_usd <= call.reserved_usd


def test_estimate_failure_stops_dispatch():
    t = transport(estimate_error=RuntimeError(f"tokenizer unavailable {SECRET}"))
    run = run_generation(spec(), client(t), ONE_PER_FAMILY)
    assert t.sent == [] and run.records == []
    assert "cost estimation failed" in run.report.stopped_reason
    assert SECRET not in run.report.stopped_reason
    assert run.report.slots_filled == 0


# --- strict vs best-effort --------------------------------------------------------

def test_strict_mode_refuses_estimate_without_upper_bound():
    t = transport(declare_upper_bound=False)
    run = run_generation(spec(), client(t), ONE_PER_FAMILY)
    assert t.sent == [] and run.records == []
    assert run.report.stopped_reason.startswith("strict budget")
    assert run.report.budget_guarantee == "no_calls"


def test_strict_mode_refuses_unbounded_reasoning():
    t = transport()
    run = run_generation(spec(), client(t, max_reasoning_tokens=None), ONE_PER_FAMILY[:1])
    assert t.sent == [] and "reasoning tokens unbounded" in run.report.stopped_reason


def test_best_effort_mode_dispatches_but_reports_no_guarantee():
    t = transport(declare_upper_bound=False)
    run = run_generation(spec(), client(t, strict_budget=False), ONE_PER_FAMILY[:2])
    r = run.report
    assert len(t.sent) == 2 and r.admitted == 2
    assert r.budget_mode == "best_effort"
    assert r.budget_guarantee == "not_guaranteed_best_effort"
    assert r.calls_without_upper_bound == 2


def test_report_never_claims_a_hard_cap():
    for strict, declared in [(True, True), (False, False)]:
        t = transport(declare_upper_bound=declared)
        run = run_generation(spec(), client(t, strict_budget=strict), ONE_PER_FAMILY[:1])
        md = render_report_md(run.report).lower()
        assert "hard cap" not in md and "guarantee" in md
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text().lower()
    assert "hard cap" not in readme


# --- overrun ----------------------------------------------------------------------

def test_overrun_keeps_actual_cost_records_it_and_stops_dispatch():
    t = transport(script=["overrun"])
    run = run_generation(spec(), client(t, budget="10"), ONE_PER_FAMILY)
    (rec,) = run.records
    call = rec.generation_calls[0]
    assert call.billing.cost_usd == Decimal("5")          # actual cost retained
    assert call.overrun_usd == Decimal("5") - call.reserved_usd
    assert rec.status == "admitted"                       # paid-for response still evaluated
    r = run.report
    assert len(t.sent) == 1 and len(r.unfilled_slots) == 4
    assert r.overruns == 1 and r.budget_guarantee == "violated_by_overrun"
    assert r.cost_total.reported_usd == Decimal("5")
    assert "exceeded its reservation" in r.stopped_reason


def test_overrun_beyond_budget_is_flagged():
    t = transport(script=["overrun"])
    run = run_generation(spec(), client(t, budget="1"), ONE_PER_FAMILY[:2])
    assert run.report.committed_exceeds_cap and run.report.committed_usd == Decimal("5")


def test_underestimating_transport_is_caught_by_overrun():
    """A transport that forgets the schema in its estimate is detected and halted."""
    t = transport(count_schema=False)
    # tight output/reasoning limits leave no slack to hide the missing input cost
    run = run_generation(spec(), client(t, max_output_tokens=200, max_reasoning_tokens=40),
                         ONE_PER_FAMILY)
    assert len(t.sent) == 1 and run.report.overruns == 1
    assert run.report.budget_guarantee == "violated_by_overrun"


def test_overrun_on_retryable_error_is_not_retried():
    over = error("503", retryable=True,
                 billing=Billing(status="reported", cost_usd=Decimal("5")))
    t = transport(script=[over])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY)
    assert len(t.sent) == 1 and run.report.overruns == 1


# --- malformed output, provider errors, retries ------------------------------------

def test_malformed_output_then_repair_counts_both_costs():
    t = transport(script=["malformed", "ok"])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY[:1])
    first, second = run.records
    assert first.issues[0].code == "malformed_json" and first.raw_response.startswith("I think")
    assert second.status == "admitted"
    r = run.report
    assert r.cost_repairs.reported_usd == second.generation_calls[0].billing.cost_usd
    assert r.cost_per_admitted_task.reported_usd == r.cost_total.reported_usd
    assert second.provenance.lineage_generation_cost == r.cost_total


def test_retryable_error_is_retried_and_billed():
    t = transport(script=[error("503", retryable=True, billing=Billing(
        status="reported", cost_usd=Decimal("0.0001"))), "ok"])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY[:1])
    failed, ok = run.records[0].generation_calls
    assert run.records[0].status == "admitted" and (failed.attempt, ok.attempt) == (0, 1)
    assert run.report.calls_retried == 1 and run.report.calls_failed == 1
    assert run.report.cost_total.reported_usd == Decimal("0.0001") + ok.billing.cost_usd


def test_retries_exhausted_and_unexpected_errors_are_unknown_exposure():
    t = transport(script=[error("503", retryable=True)] * 3 + [RuntimeError("socket")])
    run = run_generation(spec(), client(t, max_retries=2), ONE_PER_FAMILY[:2])
    a, b = run.records
    assert [i.code for i in a.issues] == ["provider_error"] and len(a.generation_calls) == 3
    assert b.issues[0].code == "provider_error"
    calls = a.generation_calls + b.generation_calls
    assert all(c.billing.status == "unknown" for c in calls)
    assert run.report.cost_total.unknown_exposure_usd == sum(c.reserved_usd for c in calls)
    assert run.report.cost_total.reported_usd == 0


# --- budget exhaustion -------------------------------------------------------------

def _bound():
    """Largest reservation for one call (estimates are near-identical across families)."""
    c = client(transport())
    run = run_generation(spec(), c, ONE_PER_FAMILY)
    return max(call.reserved_usd for r in run.records for call in r.generation_calls)


def test_reconciliation_releases_unused_reservation():
    b = _bound()
    run = run_generation(spec(), client(transport(), budget=str(b * Decimal("2.5"))),
                         ONE_PER_FAMILY)
    assert run.report.admitted == 5 and run.report.stopped_reason is None


def test_budget_exhaustion_stops_dispatch():
    b = _bound()
    t = transport(script=["unknown_billing"] * 5)  # exposure counted at full reservation
    c = client(t, budget=str(b * Decimal("2.5")))
    run = run_generation(spec(), c, ONE_PER_FAMILY)
    r = run.report
    assert len(t.sent) == r.calls_dispatched == 2 and r.admitted == 2
    assert "cannot cover" in r.stopped_reason
    assert r.committed_usd <= r.budget_cap_usd and not r.committed_exceeds_cap
    assert c.ledger.refused == 1


def test_budget_below_one_call_dispatches_nothing():
    t = transport()
    run = run_generation(spec(), client(t, budget="0.000001"), ONE_PER_FAMILY)
    assert t.sent == [] and run.records == []
    assert run.report.cost_per_admitted_task is None and run.report.committed_usd == 0


def test_budget_exhaustion_mid_retry_keeps_the_paid_attempt():
    b = _bound()
    t = transport(script=[error("503", retryable=True)])
    run = run_generation(spec(), client(t, budget=str(b * Decimal("1.5"))), ONE_PER_FAMILY)
    (rec,) = run.records
    assert rec.issues[0].code == "budget_exhausted" and len(rec.generation_calls) == 1
    assert run.report.cost_total.unknown_exposure_usd == rec.generation_calls[0].reserved_usd


# --- credentials, pricing, CLI opt-in ----------------------------------------------

def test_credentials_are_redacted_from_stored_artifacts(tmp_path):
    t = transport(script=[error(f"auth failed for key {SECRET}",
                                billing=Billing(status="not_billable"))])
    run = run_generation(spec(), client(t), ONE_PER_FAMILY[:2])
    write_run(run, tmp_path)
    blob = "".join(p.read_text() for p in tmp_path.rglob("*.json"))
    assert SECRET not in blob and "[REDACTED]" in blob


def test_pricing_must_be_explicit():
    with pytest.raises(PricingMissing):
        PricingTable(currency="USD", models=[PRICING]).for_model("other")
    partial = ModelPricing(model=MODEL, usd_per_million_tokens={"input": Decimal(1)},
                           source="x")
    with pytest.raises(PricingMissing):  # transport needs output + reasoning rates
        ScriptedTransport(model=MODEL, pricing=partial)
    example = Path(__file__).resolve().parent.parent / "pricing.example.yaml"
    with pytest.raises(Exception):
        load_pricing(example)  # placeholders deliberately invalid


def test_live_config_requires_bounds():
    for bad in [dict(budget_usd=Decimal(0), max_output_tokens=10),
                dict(budget_usd=Decimal(1), max_output_tokens=0),
                dict(budget_usd=Decimal(1), max_output_tokens=10, max_reasoning_tokens=-1)]:
        with pytest.raises(ValueError):
            LiveConfig(model=MODEL, **bad)


@pytest.fixture
def pricing_file(tmp_path):
    p = tmp_path / "pricing.yaml"
    p.write_text(json.dumps({"currency": "USD", "models": [PRICING.model_dump(mode="json")]}))
    return p


def _live_args(pricing_file, out, *extra):
    return ["generate", "--live", "--transport", "tg_fake_transport:make", "--model", MODEL,
            "--pricing", str(pricing_file), "--budget-usd", "1", "--out", str(out), *extra]


def test_cli_live_requires_opt_in_and_config(pricing_file, tmp_path, capsys):
    env = {SECRET_ENV: SECRET}
    out = tmp_path / "o"
    assert main(["generate", "--model", MODEL, "--out", str(out)], env=env) == 2
    assert main(["generate", "--best-effort-budget", "--out", str(out)], env=env) == 2
    assert main(["generate", "--live", "--out", str(out)], env=env) == 2
    err = capsys.readouterr().err
    assert "--model/TASKGEN_MODEL" in err and "--budget-usd" in err and "--pricing" in err
    assert main(_live_args(pricing_file, out), env={}) == 2  # missing credential
    assert SECRET_ENV in capsys.readouterr().err
    args = _live_args(pricing_file, out)
    args[args.index(MODEL)] = "unpriced"
    assert main(args, env=env) == 2
    assert not out.exists()


def test_cli_strict_default_refuses_unbounded_reasoning(pricing_file, tmp_path, capsys):
    out = tmp_path / "live"
    assert main(_live_args(pricing_file, out, "--max-slots", "2"),
                env={SECRET_ENV: SECRET}) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["calls_dispatched"] == 0 and report["budget_mode"] == "strict"
    assert "reasoning tokens unbounded" in report["stopped_reason"]


def test_cli_live_end_to_end_with_mock_transport(pricing_file, tmp_path, capsys):
    env = {SECRET_ENV: SECRET, "TASKGEN_MODEL": MODEL,
           "TASKGEN_TRANSPORT": "tg_fake_transport:make"}
    out = tmp_path / "live"
    assert main(["generate", "--live", "--pricing", str(pricing_file), "--budget-usd", "1",
                 "--max-slots", "3", "--max-output-tokens", "2000",
                 "--max-reasoning-tokens", "500", "--out", str(out)], env=env) == 0
    assert SECRET not in capsys.readouterr().out
    report = json.loads((out / "report.json").read_text())
    assert report["admitted"] == 3 and report["budget_guarantee"] == "declared_upper_bounds_held"
    assert {r["family_id"] for r in report["rows"]} == {f.id for f in spec().families[:3]}
    budget = json.loads((out / "budget.json").read_text())
    assert budget["calls_dispatched"] == 3 and Decimal(budget["outstanding_reservations_usd"]) == 0
    assert SECRET not in "".join(p.read_text() for p in out.rglob("*") if p.is_file())


def test_cli_best_effort_requires_explicit_flag(pricing_file, tmp_path):
    env = {SECRET_ENV: SECRET}
    args = _live_args(pricing_file, tmp_path / "a", "--max-slots", "1",
                      "--max-reasoning-tokens", "100")
    args[args.index("tg_fake_transport:make")] = "tg_fake_transport:make_unbounded"
    assert main(args, env=env) == 0
    strict = json.loads((tmp_path / "a" / "report.json").read_text())
    assert strict["calls_dispatched"] == 0
    args[args.index(str(tmp_path / "a"))] = str(tmp_path / "b")
    assert main(args + ["--best-effort-budget"], env=env) == 0
    best = json.loads((tmp_path / "b" / "report.json").read_text())
    assert best["calls_dispatched"] == 1
    assert best["budget_guarantee"] == "not_guaranteed_best_effort"


def test_offline_demo_needs_no_live_configuration(tmp_path):
    assert main(["demo", "--out", str(tmp_path / "d")], env={}) == 0
    report = json.loads((tmp_path / "d" / "report.json").read_text())
    assert report["metered"] is False and report["cost_total"] is None
