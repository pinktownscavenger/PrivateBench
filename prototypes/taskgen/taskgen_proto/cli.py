"""CLI. Offline by default.

    python -m taskgen_proto demo      [--out DIR]   # offline: generate + admit, then fixture
    python -m taskgen_proto generate  [--out DIR]   # offline fake generator
    python -m taskgen_proto fixture

Live generation (spends money; every flag below is required unless noted):

    python -m taskgen_proto generate --live \\
        --transport MODULE:FACTORY      (or TASKGEN_TRANSPORT; factory(model=, pricing=))
        --model MODEL_ID                (or TASKGEN_MODEL; passed to the transport unchanged)
        --pricing PRICING.yaml          (explicit per-model rates; none are built in)
        --budget-usd BUDGET
        [--max-output-tokens N] [--max-reasoning-tokens N] [--max-slots N]
        [--max-retries N] [--best-effort-budget] [--out DIR]

Strict budget mode is the default: a call is refused unless the transport
declares its cost estimate an upper bound for the complete request.
--best-effort-budget allows unbounded estimates; the budget is then a target,
not a guarantee.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .fixture import DEFAULT_FIXTURE_PATH, FixtureReport, load_fixture, run_fixture
from .generator import FakeGeneratorClient, GeneratorClient
from .live import LiveConfig, LiveGeneratorClient, ModelPricing, PricingMissing, load_pricing
from .pipeline import default_plan, prepare_out_dir, run_generation, summary_json, write_run
from .spec import DEFAULT_SPEC_PATH, WorkloadSpec, load_spec

OUT_ROOT = Path(__file__).resolve().parent.parent / "out"
LIVE_ONLY = ("transport", "model", "pricing", "budget_usd", "max_output_tokens",
             "max_reasoning_tokens", "max_slots", "max_retries", "best_effort_budget")


class UsageError(Exception):
    pass


def _load_transport(ref: str, model: str, pricing: ModelPricing):
    mod_name, _, attr = ref.partition(":")
    if not mod_name or not attr:
        raise UsageError(f"--transport must look like 'module:factory', got {ref!r}")
    try:
        factory = getattr(importlib.import_module(mod_name), attr)
    except (ImportError, AttributeError) as exc:
        raise UsageError(f"cannot load transport {ref!r}: {exc}") from exc
    try:
        return factory(model=model, pricing=pricing)
    except Exception as exc:  # e.g. a rate category the transport needs is missing
        raise UsageError(f"transport {ref!r} rejected its configuration: {exc}") from exc


def _live_client(a: argparse.Namespace,
                 env: dict[str, str]) -> tuple[LiveGeneratorClient, ModelPricing]:
    transport_ref = a.transport or env.get("TASKGEN_TRANSPORT")
    model = a.model or env.get("TASKGEN_MODEL")
    missing = [n for n, v in [("--transport/TASKGEN_TRANSPORT", transport_ref),
                              ("--model/TASKGEN_MODEL", model), ("--pricing", a.pricing),
                              ("--budget-usd", a.budget_usd)] if not v]
    if missing:
        raise UsageError("live generation requires: " + ", ".join(missing))
    try:
        budget = Decimal(a.budget_usd)
    except InvalidOperation as exc:
        raise UsageError(f"--budget-usd must be a number, got {a.budget_usd!r}") from exc
    try:
        pricing = load_pricing(a.pricing).for_model(model)
    except PricingMissing as exc:
        raise UsageError(str(exc)) from exc
    except Exception as exc:
        raise UsageError(f"invalid pricing file {a.pricing}: {exc}") from exc
    transport = _load_transport(transport_ref, model, pricing)
    absent = [v for v in getattr(transport, "credential_env_vars", ()) if not env.get(v)]
    if absent:  # names only; values are never printed
        raise UsageError(f"transport {transport.name!r} needs env vars: {', '.join(absent)}")
    try:
        config = LiveConfig(model=model, budget_usd=budget,
                            max_output_tokens=a.max_output_tokens or 4000,
                            max_reasoning_tokens=a.max_reasoning_tokens,
                            max_retries=2 if a.max_retries is None else a.max_retries,
                            strict_budget=not a.best_effort_budget)
    except ValueError as exc:
        raise UsageError(f"invalid live settings: {exc}") from exc
    secrets = [env[v] for v in getattr(transport, "credential_env_vars", ())]
    return LiveGeneratorClient(transport, config, redact_values=secrets), pricing


def _plan(spec: WorkloadSpec, max_slots: int | None) -> list[tuple[str, int]]:
    # seed-major order so a small batch covers every family before repeating one
    plan = sorted(default_plan(spec), key=lambda slot: slot[1])
    return plan[:max_slots] if max_slots else plan


def _generate(a: argparse.Namespace, env: dict[str, str]) -> int:
    spec = load_spec(a.spec)
    client: GeneratorClient
    if a.live:
        client, pricing = _live_client(a, env)
        plan = _plan(spec, a.max_slots)
        cfg = client.config
        mode = "strict" if cfg.strict_budget else "BEST-EFFORT (not a guarantee)"
        print(f"LIVE generation via {client.name}, model {cfg.model!r}: {len(plan)} slot(s), "
              f"budget ${cfg.budget_usd} [{mode}], max_output_tokens "
              f"{cfg.max_output_tokens}, max_reasoning_tokens {cfg.max_reasoning_tokens}, "
              f"max_retries {cfg.max_retries}, pricing source: {pricing.source}")
    else:
        client, plan = FakeGeneratorClient(spec), None
    out = a.out or OUT_ROOT / ("live" if a.live else "demo")
    prepare_out_dir(out)
    run = run_generation(spec, client, plan)
    write_run(run, out)
    r = run.report
    print(f"== generation: {spec.spec_id} v{spec.version} with {r.generator} "
          f"({'live' if a.live else 'offline'}) ==")
    print(summary_json(r))
    for row in r.rows:
        mark = "ADMIT " if row.status == "admitted" else "REJECT"
        parent = f" (repair of {row.parent_candidate_id})" if row.parent_candidate_id else ""
        print(f"  {mark} {row.candidate_id:<30} {', '.join(row.issue_codes)}{parent}")
    print(f"wrote {out}/report.md, tasks/, candidates/")
    return 0


def _print_fixture(rep: FixtureReport) -> None:
    print(f"== independent fixture: {rep.fixture_id} ==")
    for t in rep.results:
        sols = ", ".join(f"{s.id}={s.actual}" for s in t.solutions)
        print(f"  {t.id:<28} oracle={t.oracle_outcome:<16} admission={t.admission_status:<8} "
              f"{'OK' if not t.disagreements else 'DISAGREE'}")
        print(f"    solutions: {sols}")
    print("fixture agrees with pipeline" if rep.all_agree
          else "DISAGREEMENTS:\n  " + "\n  ".join(rep.disagreements))


def _fixture(spec_path: Path, fixture_path: Path) -> int:
    rep = run_fixture(load_spec(spec_path), load_fixture(fixture_path))
    _print_fixture(rep)
    return 0 if rep.all_agree else 1


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    env = dict(os.environ) if env is None else env
    ap = argparse.ArgumentParser(prog="taskgen_proto", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["demo", "generate", "fixture"])
    ap.add_argument("--spec", type=Path, default=DEFAULT_SPEC_PATH)
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    ap.add_argument("--out", type=Path, default=None,
                    help="output dir (default out/demo, or out/live with --live)")
    live = ap.add_argument_group("live generation (opt-in; spends money)")
    live.add_argument("--live", action="store_true", help="explicitly opt in to live calls")
    live.add_argument("--transport", help="MODULE:FACTORY returning a Transport")
    live.add_argument("--model", help="model id passed unchanged to the transport")
    live.add_argument("--pricing", type=Path, help="pricing YAML with a rate for --model")
    live.add_argument("--budget-usd", help="batch budget; enforced against transport "
                      "estimates (a guarantee only if they are declared upper bounds)")
    live.add_argument("--max-output-tokens", type=int)
    live.add_argument("--max-reasoning-tokens", type=int)
    live.add_argument("--best-effort-budget", action="store_const", const=True, default=None,
                      help="allow calls whose estimate is not a declared upper bound")
    live.add_argument("--max-slots", type=int)
    live.add_argument("--max-retries", type=int)
    a = ap.parse_args(argv)
    try:
        used = [f"--{k.replace('_', '-')}" for k in LIVE_ONLY if getattr(a, k) is not None]
        if a.live and a.command != "generate":
            raise UsageError("--live is only accepted by the 'generate' command")
        if used and not a.live:
            raise UsageError(f"{', '.join(used)}: only allowed together with --live")
        if a.command == "generate":
            return _generate(a, env)
        if a.command == "fixture":
            return _fixture(a.spec, a.fixture)
        code = _generate(a, env)
        print()
        return code or _fixture(a.spec, a.fixture)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
