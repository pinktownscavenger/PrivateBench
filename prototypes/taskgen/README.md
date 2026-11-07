# Task-generation prototype

An independent vertical slice of reliable, workload-specific task generation,
based on `docs/6725 Task Generation Research Review.md`.

> **Separate from the pilot.** This directory does not import or change
> `privatebench/`, `contracts/`, or any pilot module interface. The policies
> here (A1–A4) are **not** the pilot's R1–R5 rules.

## Run it (offline, no paid calls)

```bash
uv sync
cd prototypes/taskgen
uv run python -m taskgen_proto demo          # generate -> admit, then check the fixture
uv run python -m taskgen_proto demo --out /some/dir
uv run python -m taskgen_proto fixture       # fixture check only

# tests (from the repo root)
uv run pytest prototypes/taskgen/tests
```

`demo` writes to `prototypes/taskgen/out/demo/` (git-ignored). It only
overwrites a directory it created earlier, which it recognises by its `report.json`.

## Live generation (opt-in, budgeted, provider-neutral)

Offline is the default. Live generation runs only with `generate --live` and a
complete configuration. **No provider transport ships yet**: the provider
(e.g. Bedrock) is still being chosen, so you plug one in through
`--transport MODULE:FACTORY`. Nothing in the code holds a model id, a price or
a credential.

| Required | How | Notes |
|---|---|---|
| Opt-in | `--live` | Live flags without `--live` are refused |
| Transport | `--transport mod:factory` or `TASKGEN_TRANSPORT` | Called as `factory(model=..., pricing=...)` |
| Model | `--model` or `TASKGEN_MODEL` | No default. Passed to the transport unchanged |
| Pricing | `--pricing file.yaml` | Explicit USD per million tokens, per token category, plus a source; see `pricing.example.yaml` |
| Budget | `--budget-usd` | Checked against transport estimates before each call (see guarantees below) |
| Credentials | Env vars named by the transport's `credential_env_vars` | Presence checked. Values never stored, and redacted from records |
| Limits | `--max-output-tokens` (default 4000), `--max-reasoning-tokens` | Passed to the transport, which must include them in its estimate |
| Budget mode | strict (default) or `--best-effort-budget` | See below |

### Who estimates cost: the transport

Only the transport knows the complete billable request: system text,
tool/response schemas, provider framing, and the output and reasoning limits it
actually sends. So it implements `estimate(call) -> CostEstimate`:

- `max_cost_usd`: maximum cost of exactly the request `send(call)` would make.
- `upper_bound`: does the transport claim the request *cannot* cost more?
- `basis` and `components`: what was counted (recorded with each call).

`send(call)` returns or raises with a `Billing`:
- `reported`: a cost from provider usage;
- `not_billable`;
- `unknown`.

The adapter does no pricing arithmetic.

### What the adapter enforces (`live.py`)

1. **Strict mode (default).** A call whose estimate is not declared an upper
   bound is refused, and dispatch stops. For example, the test transport
   declares no bound when `--max-reasoning-tokens` is unset.
2. **Reserve.** Before dispatch, reserve the estimate. If it exceeds the
   remaining budget, don't dispatch and stop the batch.
3. **Settle.** Reported billing adds its actual cost. Unknown billing adds
   exposure equal to the reservation. Not-billable calls add nothing.
4. **Overrun.** If a reported cost exceeds its reservation, the actual cost is
   kept and the overrun recorded. All further dispatch stops, because the
   transport's bound has been shown wrong. The response already paid for is
   still evaluated.
5. **Retries.** Only errors marked `retryable` are retried, and each retry is
   estimated, reserved and settled as its own call. No retry happens after
   dispatch has stopped.

### Three quantities, reported separately

| Quantity | Meaning |
|---|---|
| Reported cost | Sum of transport-reported costs |
| Unknown-billing exposure | Calls with unknown billing, counted at their reservation |
| Outstanding reservations | Reserved for calls not yet settled (0 after a normal run) |
| Committed | Sum of the three; this is what the budget is checked against |

`report.md` / `report.json` give these totals, split into initial attempts
and repairs, plus a per-admitted-task breakdown. The per-task figure counts
every paid call: rejected candidates, repairs, retries and failed calls.

The report also gives call, failure, retry and overrun counts, the stop
reason, and `committed_exceeds_cap`. `budget.json` and each
`candidates/<id>.json` keep the per-call estimate, reservation, billing,
exposure and overrun.

### What the budget does and does not guarantee

The budget is a hard limit only if the transport's declared upper bounds are
correct. The adapter cannot verify that in advance; it can only detect a
violation afterwards. Every report states which case applied:

| `budget_guarantee` | Meaning |
|---|---|
| `declared_upper_bounds_held` | Every call had a declared upper bound and none was exceeded. Committed ≤ budget **if** those bounds are correct |
| `not_guaranteed_best_effort` | Some call ran without a declared bound (`--best-effort-budget`). The budget is a target, not a limit |
| `violated_by_overrun` | A reported cost exceeded its bound. Actual cost kept; dispatch stopped; `committed` may exceed the budget |
| `no_calls` | Nothing was dispatched |

### A small live batch

5 slots, one per family, $1.00 budget, strict mode. These commands work once a
transport module exists:

```bash
cd prototypes/taskgen
cp pricing.example.yaml pricing.local.yaml   # git-ignored; fill in real rates + source
export TASKGEN_MODEL='<exact model id>'
export TASKGEN_TRANSPORT='<your_module>:<factory>'
export <CREDENTIAL_ENV_VARS named by that transport>=...
uv run python -m taskgen_proto generate --live \
    --pricing pricing.local.yaml --budget-usd 1.00 \
    --max-slots 5 --max-output-tokens 4000 --max-reasoning-tokens 1024 --max-retries 1
# writes out/live/{report.md,report.json,budget.json,candidates/,tasks/}
```

## Pipeline

```
workload/plan_change.yaml   approved spec (status: approved required)
        │
        ▼
generator.py   build_prompt → GeneratorClient.complete() → raw JSON   (LLM proposes)
        │                                                    ▲ feedback on rejection
        ▼                                                    │ (max_repairs, new revision
proposal.py    parse + strict schema (extra=forbid)          │  linked by parent_candidate_id)
validate.py    integrity · distractors · solver-reachable request ·
               instruction leakage · policy oracle == claimed label · family branch
        │
        ▼
grader.py      assertions compiled from ORACLE outcome + request binding
               (required outcomes, forbidden effects, preserve-unrelated-state)
env.py         reference replayed through the solver's own tools, from a clean
               reset, twice (repeatability)
audit.py       grader audit: valid alternatives must pass; wrong target, incomplete,
               collateral, wrong outcome, claim-without-action must fail
        │
        ▼
pipeline.py    admit → tasks/<id>/{solver.json, environment.json, evaluator.json}
               every candidate → candidates/<id>.json (rejected ones keep raw response + reasons)
               report.json / report.md
fixture.py     hand-authored tasks checked against oracle, admission and grader
```

The LLM proposes. Deterministic code decides. The generator's own claims
(its label and its reference procedure) never feed the grader:

| Artifact | Comes from | Checked by |
|---|---|---|
| Expected outcome | Policy oracle (`policy.py`) run on the spec | Generator label must agree; fixture hand labels |
| Grading assertions | Oracle outcome + request binding | Reference replay; mutation audit; fixture verdicts |
| Reference procedure | Generator | Must reach a state that satisfies the assertions |

### Task package contents

| Required element | Where |
|---|---|
| User instruction | `solver.json` → `instruction` |
| Initial state | `environment.json`, loaded into `Environment`; the solver reaches it only through tools |
| Available tools | `solver.json` → `tools` (JSON schemas) |
| Required outcomes / forbidden side effects | `evaluator.json` → `required_outcomes`, `forbidden_effects`, `assertions` |
| Private reference and grading assertions | `evaluator.json` → `reference_procedure`, `assertions`, `audit` |
| Generation provenance | `evaluator.json` → `provenance` (generator, model, seed, prompt/response sha256, spec sha256, revision, parent) |

`TaskPackage.solver_json()` is the only solver-facing output. The tests check
that it contains only the whitelisted fields, and none of the following:
family id, policy ids, reference, assertions, target subscription, or invoice
records.

## The synthetic workflow and its assumptions

A support agent works a ticket that asks to change the plan of one
subscription. The world has four tables: customers, subscriptions, invoices
and tickets. There are 8 tools. The tools enforce only interface constraints
(the record exists, enum values are valid, a ticket must be open to close).
Applying policy is up to the agent.

**Prototype assumptions** (all in `workload/plan_change.yaml`; first match wins):

| id | Assumption | Outcome |
|---|---|---|
| A1 | Cancelled subscriptions cannot change plan | `denied_inactive` |
| A2 | Already on the requested plan | `no_change_needed` |
| A3 | Changes to or from `params.plans` (default: enterprise) are escalated | `escalated` |
| A4 | Downgrade blocked while *that* subscription has an unpaid invoice | `denied_unpaid` |
| — | Otherwise | `plan_changed` |

Each policy has `enabled`, an order and `params`, and all are marked
`provenance: prototype_assumption`. They are invented to exercise the
pipeline and are not real business rules. Changing them changes the oracle,
the solver-visible policy text and the grader. The tests check that reordering,
disabling or re-parameterizing a policy changes the expected outcomes.

## Design ideas borrowed (no stacks installed)

- **SOP-Bench**: an explicit procedure in the spec, one family per decision
  branch, and per-rule provenance.
- **TaskBench**: generate a structured task first, then verbalize the
  instruction. Score execution outcomes, not the tool sequence.
- **τ²-bench**: each scenario has initialization (initial state), a solution
  (reference) and assertions, and replays from a reset.
- **AppWorld / AutomationBench**: the task owns its world. Assertions are both
  positive and negative, plus a preservation check so "modify everything" fails.
- **VerifierBench**: audit the grader with valid alternatives as well as
  failures, and count false accepts and false rejects separately.
- **BenchAgents**: separate artifacts per stage. A rejection records a reason
  and triggers a revision rather than a silent patch.

## What this establishes about reliability

For **admitted** tasks, under the stated policies, it shows mechanically that:

1. **Well-formed.** The task is well formed, referentially consistent, and has
   unrelated records whose preservation is checked.
2. **Solvable from what the solver sees.** The request is identifiable from
   solver-visible text, and the instruction does not reveal the answer
   (lexical check).
3. **Labeled correctly.** The generator's outcome label matches the executable
   policy.
4. **Executable.** The task can be solved through the solver's tools from a
   clean reset, and the reference reproduces the same state twice.
5. **Grader is sound on the audit cases.** It accepts at least two or three
   valid alternative paths and rejects the following:
   - wrong target
   - incomplete work
   - collateral change
   - wrong branch
   - a completion claim without action

   Audit cases are derived automatically per task. In the demo that is 67 cases
   with 0 false accepts and 0 false rejects.
6. **Not self-confirming.** The grader is not checked only against the
   generator. A hand-written fixture of 5 tasks and 14 labeled solutions agrees
   with the oracle, admission and grader. The tests also show that a deliberately
   lenient grader, an over-strict grader, or a wrong policy order is caught by
   the audit, the fixture, or both.

## What still needs human review

- **Workload relevance.** Nothing here shows that plan-change tickets, these
  policies, or this branch mix resemble any real workload. The "approval" in
  the spec is a placeholder, not an owner review.
- **Policy fidelity.** The oracle executes the policy as written. If the
  written policy is wrong, the oracle, grader and generator agree with each
  other and are all wrong. Only a domain owner can catch that.
- **Instruction quality.** The leakage check is a substring list. Paraphrased
  hints, unnatural phrasing and ambiguity need human (or blind) review.
- **Representativeness and difficulty.** Family counts are configuration, not
  measured frequencies. Difficulty is not measured.
- **Fixture independence.** The fixture is independent of the generator, but
  it was written by the same author (an AI agent, in the same session) as the
  pipeline. A human-authored fixture is the real test.

## Limitations

- One workflow, five branches, one generation strategy, and no composition.
- No concrete provider transport yet, so the yield, cost and failure modes of a
  real model are unknown.
- The budget is only as strong as the transport's declared bounds. The adapter
  detects a wrong bound after the fact (overrun), not before.
- Unknown-billing exposure is counted at the reservation, which is a true
  bound only when the estimate was one.
- Calls run one at a time. The ledger is not thread-safe.
- The audit set is fixed and derived from the reference. It cannot discover
  failure classes it does not enumerate (e.g. partial-credit semantics, ordering
  constraints, clarification behavior).
- There are no clarification, abstention or missing-information tasks (ToolSandbox-style).
- No structural deduplication, split assignment, or contamination controls.
- No model-evaluation runner (deferred as requested).

## Next increment

1. **Concrete transport.** Once the provider is confirmed (e.g. whether
   Bedrock is covered by credit), add its transport with any dependency
   scoped to this prototype. Run a small live batch and compare yield,
   rejection mix and cost per admitted task with the fake baseline.
2. **Human fixture.** Have someone other than the pipeline author write 10–20
   tasks and solution verdicts. Store them in a withheld location.
3. **Blind instruction review.** Sample admitted and rejected tasks for review
   of naturalness, leakage and ambiguity, and record the decisions next to
   the candidates.
4. **New branch types.** Add clarification and missing-information branches
   with an explicit "ask / abstain" success type.
5. **Coverage and dedup.** Add structural dedup (state shape + branch +
   procedure signature) and family-level splits before scaling counts.
