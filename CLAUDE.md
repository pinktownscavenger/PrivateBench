# PrivateBench

PrivateBench generates private, workload-specific agent benchmarks. Each task is an executable package with:
- an instruction
- an initial state
- tools
- a verifier
- audit cases
- provenance

The benchmarks are then used to choose a deployable model configuration on cost, quality and latency.

The current work is the **pilot**: a synthetic customer/order/ticket refund workload. Four people own modules:
- Bilal: M0, M1, M6, M7
- Sam: M2, M8
- Matt: M3, M4
- Nikhil: M5, M9

## Read first
- `docs/M0 Handoff.md`: what the shared formats are, what's frozen, and what each module must produce. **Read the section for your module before writing code.**
- `docs/6725 Pilot Work Breakdown.md`: modules, owners and phases.
- The other files in `docs/` are background research. Consult them for rationale, not as instructions.

## Commands
```bash
uv sync            # install (Python >= 3.11)
uv run pytest      # all tests must pass before committing
```

## Layout
```
contracts/              workload.yaml, rules.yaml, families.yaml  (the M0 contract)
privatebench/schema/    shared Pydantic formats (M0)
privatebench/<module>/  env, scorer, generator, admission, runner, analysis  (planned)
tasks/reference/        hand-authored reference tasks (Matt)
tasks/generated/        generator output (never hand-edited)
audits/dev/             audit cases the scorer author may see
audits/withheld/        audit cases the scorer author must NOT see
runs/                   run records and event logs
tests/                  pytest
```

## Hard rules
1. **Shared formats are owned by Bilal.** Don't change `privatebench/schema/` or `contracts/` as a side effect of other work. If your module needs a change, stop and propose it (see the handoff doc).
2. **Solver/evaluator separation.**
   - The only thing that may reach the agent under test is `TaskPackage.solver_json()`.
   - Never put any of the following into the solver bundle, tool outputs, prompts or logs the solver can read: bindings, reference procedures, assertions, family IDs, rule IDs or audit material.
3. **Completion is judged from trusted evidence:** state captured by the environment and the gateway's event log. Never accept a state or completion claim that the solver itself reports.
4. **Score outcomes, not paths.** Don't require the solver to reproduce the reference sequence of tool calls. Enforce ordering only where a family's `process_constraints` require it.
5. **Never hand-edit generated tasks.** Fix the contract or the generator and regenerate. Failed candidates are kept; a repair creates a new revision linked through `parent_candidate_id`.
6. **Independence:**
   - Agents working for Matt must not read `audits/withheld/`.
   - Agents working for Bilal must not author reference tasks in `tasks/reference/`.
7. **Never drop trials.** Missing scores, infrastructure errors and timeouts are recorded as outcomes (see `TrialOutcome`), not removed.
8. **No paid model calls** in tests. Anything that calls a paid API needs an explicit spend cap.
9. **The rules are synthetic.** R1–R5 are assumed, pilot-only policies. Don't present them as real business rules, and don't invent new rules. Ask instead.

## Style
- Python 3.11+, type hints, Pydantic v2 models with `extra="forbid"` for anything that crosses a module boundary.
- Keep modules importable without network access. Write tests alongside code.
