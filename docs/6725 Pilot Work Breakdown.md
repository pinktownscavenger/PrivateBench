# 6725 Pilot Work Breakdown

Created: 3 November 2026  
Basis: [[6725 Task Generation Implementation Plan]]  
Team: Bilal, Sam, Matt, Nikhil  
Status: Proposed; owners and dates to be confirmed at kickoff.

## Pilot scope: the simplest baseline

The pilot is the smallest system that produces one honest number end to end: **how many directly generated tasks survive admission, and how a single model performs on them.** Everything else in the implementation plan is added on top of this baseline later.

| In the pilot | Deferred until after the baseline |
|---|---|
| Customer/order/ticket mock API (synthetic fixture) | Real user workload and owner validation |
| 4 families: eligible, ineligible, ambiguous (clarification), already-completed (idempotent) | Expansion to 8–12 families |
| Generator arm **A** (direct LLM generation) only | Arms B–D, composition, repair loops |
| Hand-authored reference tasks (2–3 per family) | Large independent comparison set |
| Scripted user with fixed disclosure rules | LLM user simulator |
| Templated state assertions + small audit suite | Custom grader code, mutation testing at scale |
| Inspect runner, **one model, single agent**, 3 repeats | Teams, extra-inference baselines, routing |
| Local runs (Docker/SQLite) | AWS workers |

**Decisions (5 Nov 2026):**

- **Workload:** the pilot uses the API business workflow. Coding/file tasks are a possible later branch, which would mean Harbor instead of Inspect.
- **Shared formats:** Pydantic v2.
- **Tools:** in-process Python functions behind a single gateway class that checks permissions and writes the event log. The gateway is the one seam, so it can be swapped for an HTTP client later without touching tools or the scorer.
- **Expected-behavior types:** act, deny, clarify and no-op are all in the formats from day one.
- **Draft rules:** R1–R5 in `contracts/rules.yaml` are assumed, synthetic proposals awaiting team approval at kickoff, along with open questions Q1–Q4.

**Pilot outputs:**
- About 20 directly generated candidates per family (~80 total)
- An admission report giving yield and rejection reasons by gate
- Single-model results per family, with cost per trial and pass^3

## Modules

| ID | Module | Contents | Owner |
|---|---|---|---|
| M0 | Contract and interfaces | `workload.yaml`, `rules.yaml` (rule IDs + provenance, marked synthetic), family definitions with explicit success semantics; Python typed models for task package, tool schema, state snapshot/diff, event log, run record | **Bilal** (all review) |
| M1 | Task package and ledger | Solver bundle vs evaluation bundle split; content hashes; lifecycle status (`draft → ready → validation_failed / admitted`); SQLite ledger of candidates, rejections, runs | **Bilal** |
| M2 | Environment | Mock CRM/orders/tickets API on SQLite; typed tools with preconditions, effects, errors (duplicate, missing record); reset into isolated namespace; frozen clock/seed; before/after snapshots; append-only event log | **Sam** |
| M3 | Scorer and audit harness | Assertion templates (required outcome, forbidden effect, event-order where policy requires it); state-diff scorer; audit runner reporting false acceptance / false rejection separately | **Matt** |
| M4 | Reference tasks | 2–3 hand-authored tasks per family with reference procedures and at least one valid alternative each; scripted-user disclosure rules for the ambiguous family | **Matt** (written before seeing generated tasks) |
| M5 | Runner and baseline solver | Inspect adapter (dataset/solver/scorer), tool gateway exposing only solver-visible tools, single-model ReAct solver, repeats, timeouts, token/cost accounting, our own planned-trial ledger | **Nikhil** |
| M6 | Generator arm A | Prompt + structured output producing task packages from the frozen brief; caching keyed by prompt/model/schema version; spend cap | **Bilal** |
| M7 | Admission pipeline | Gates in order: schema/contract → reference replay on 3 fresh resets → isolation probe → audit suite; records rejection reason per gate | **Bilal** (gates call M2/M3) |
| M8 | Isolation probes and withheld audits | Probes for answer/grader leakage into the solver bundle and cross-run contamination; **withheld** audit cases (wrong target, duplicate, no-op, false completion claim, valid alternatives) kept away from Matt | **Sam** |
| M9 | Analysis and report | Recompute metrics from raw records: yield by gate, per-family success, pass^3, cost per trial and per accepted task, coverage counts (planned / scored / unscored / infra error) | **Nikhil** |

Why these owners: Nikhil did the agent-evaluation research (runner semantics, stats), so he takes runner + analysis. Bilal owns the interfaces, so he integrates the generator and admission pipeline that touch everything. Independence rules from the research: **the generator author (Bilal) does not write reference tasks, and the scorer author (Matt) does not see the withheld audits (Sam).**

## Schedule: what runs in parallel and what is sequential

```
Phase 0  SEQUENTIAL   M0 contract + interfaces ............ all four, Bilal leads
            │
Phase 1  PARALLEL     M1 package+ledger (Bilal)
            │         M2 environment     (Sam)
            │         M3 scorer          (Matt)   + M4 reference tasks (Matt)
            │         M5 runner adapter  (Nikhil, against a stub env)
            │
Phase 2  SEQUENTIAL   First end-to-end task ............... all four
            │
Phase 3  PARALLEL     M6 generator + M7 admission (Bilal)
            │         M8 isolation + withheld audits (Sam)
            │         M3 audit harness + remaining families' templates (Matt)
            │         M5 baseline solver + M9 analysis (Nikhil)
            │
Phase 4  SEQUENTIAL   Generate → admit → run baseline → report
```

### Phase 0 — Contract and interfaces (sequential, ~2–3 days)

Blocks everything. Every Phase 1 module codes against these interfaces, so freeze them before splitting up:

- Task package schema (solver-visible vs evaluator-only fields)
- Tool schema and error types
- State snapshot and diff format
- Event-log record
- Run record

Also decide coding vs API workload here. **Exit:** four families with written success semantics; interfaces merged to `main`; changes after this go through Bilal.

### Phase 1 — Build the parts (parallel, ~4–6 days)

The four tracks are independent because each one codes against the Phase 0 interfaces, using stubs or fixtures rather than the other modules:

- **Sam (M2):** environment, reset, snapshots, event log.
- **Matt (M3, M4):** scorer tested on hand-made snapshot/diff fixtures; reference tasks written in the package format.
- **Nikhil (M5):** Inspect adapter run against a stub tool server returning canned responses.
- **Bilal (M1):** package serialization, hashing, ledger; start drafting the generator prompt.

**Coordination point:** Matt's reference tasks need Sam's tool names. Agree on these in Phase 0 so this isn't a blocker.

### Phase 2 — First end-to-end task (sequential, ~2 days)

Wire one hand-authored task through the real environment, runner and scorer:

- Reference replay passes on 3 fresh resets.
- A valid alternative is accepted.
- A wrong-target action is rejected.
- A deliberately failing run and a timeout get the right statuses.

This is the implementation plan's M1 gate. Pair-debug as a group; nothing in Phase 3 starts until this passes.

### Phase 3 — Fill out the pilot (parallel, ~4–6 days)

- **Bilal (M6, M7):** generator arm A, plus admission pipeline that calls the working env/scorer.
- **Sam (M8):** isolation probes and withheld audit cases; scripted user for the ambiguous family.
- **Matt (M3):** audit harness, and assertion templates for all four families; all reference tasks admitted.
- **Nikhil (M5, M9):** single-model baseline solver with repeats and cost ledger; analysis scripts run against Phase 2 records.

**Dependencies inside this phase:**
- M7's audit gate needs Matt's harness and Sam's withheld cases. Bilal builds the earlier gates first.
- M9 only needs the run-record format, which is already frozen.

### Phase 4 — Baseline run (sequential, ~2–3 days)

In order:

1. Smoke test: 10 generator attempts, fix shared bugs, then **freeze** the prompt, model and caps.
2. Generate ~80 candidates.
3. Admit them; keep the rejects.
4. Run the single-model solver × 3 repeats on admitted tasks and reference tasks.
5. Nikhil produces the report; everyone reviews admitted tasks blind for instruction/contract agreement.

**Exit:** the baseline numbers, which every later improvement (arms B–D, teams, routing) is compared against.

## Shared conventions

- **Repo layout:** `contracts/`, `privatebench/{schema,env,scorer,generator,admission,runner,analysis}/`, `tasks/{reference,generated}/`, `audits/{dev,withheld}/` (withheld kept out of Matt's working context), `runs/`.
- **One PR per module task.** Bilal reviews interface changes; everyone else reviews across tracks.
- **Budget:** set a model-spend cap per phase before running anything paid. Track API spend separately from the AWS credit.
- **Never edit generated tasks by hand.** Fix the contract or the generator, then regenerate.
