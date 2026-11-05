# M0 Handoff: contract and shared formats

Owner: Bilal  
Contract version: `0.1.0-draft`  
Status: **draft, pending team sign-off.** The formats are stable enough to build against. The rules are not final.

M0 defines what "correct" means for the pilot, and the formats every module exchanges. Build your module against the formats here, not against another module's internals. That keeps Phase 1 parallel.

## 1. What M0 provides

| File | Contents |
|---|---|
| `contracts/workload.yaml` | Entities (customer, order, refund, ticket), the 7 tools with access type, params, errors and effects, solver permissions, clock policy |
| `contracts/rules.yaml` | Refund rules R1–R5 (synthetic) and open questions Q1–Q4 |
| `contracts/families.yaml` | The 4 task families: expected behavior, required outcomes, forbidden effects, process constraints |
| `privatebench/schema/contract.py` | `load_contract(dir)`: loads and cross-checks the three YAML files, raising `ContractError` on bad references |
| `privatebench/schema/task.py` | `TaskPackage` = `TaskMeta` + `SolverBundle` + `EvaluationBundle`; `AdmissionStatus` and `can_transition` |
| `privatebench/schema/state.py` | `StateSnapshot`, `diff_snapshots` → `StateDiff`, and `Event` (the event log) |
| `privatebench/schema/run.py` | `RunRecord`, `TrialOutcome`, `Usage` |
| `privatebench/schema/hashing.py` | `content_hash(obj)`: SHA-256 of canonical JSON |

Import everything from `privatebench.schema`.

## 2. Frozen vs. pending

**Frozen:** you can build against these.
- Model and field names in `privatebench/schema/`.
- Tool names, params and access types in `workload.yaml`.
- The four family IDs and their expected behaviors.
- The assertion template names listed in section 4.

**Pending sign-off:** don't hard-code anything that depends on these.
- **R1–R5 wording.** In particular, the 30-day window (Q1) and what counts as ambiguous (Q2).
- **Whether `issue_refund` rejects duplicate refunds (Q3).** The draft says no.
- **Partial refunds (Q4).** The draft says full refunds only.

Read policy values from the contract or task data. Don't write constants like `30` into code.

## 3. The data flow between modules

```
contracts/ ──► generator (M6) / reference tasks (M4) ──► TaskPackage
                                                              │
                         admission (M7) ◄─────────────────────┤
                                                              ▼
 runner (M5) ── solver_json() ──► agent ── tool calls ──► gateway + env (M2)
      │                                                       │
      │                       StateSnapshot (before/after) + Event log
      ▼                                                       ▼
 RunRecord ◄──────────── scorer (M3): assertions → pass/fail per rule
      │
      ▼
 analysis (M9)
```

Boundary rules:
- **Agent ↔ everything else.** The agent receives only `SolverBundle`, through `TaskPackage.solver_json()`, plus tool results.
- **Environment → scorer.** The environment produces evidence as before/after `StateSnapshot`s and the `Event` log. The scorer reads only that evidence and the `EvaluationBundle`.
- **Agent claims are not evidence.** The scorer never reads what the agent said it did.

## 4. Assertion templates

Each family in `families.yaml` lists assertions by template name. Each assertion carries a `rule_id`, which must appear in that family's `rule_ids`. A task's `EvaluationBundle.bindings` fills in the `$placeholders`, for example `{"target_order": "O-12", "ticket": "T-3"}`.

| Template | Kind(s) | Evidence | Passes when |
|---|---|---|---|
| `refund_count(order, count)` | outcome | final snapshot | the `order` has exactly `count` refund rows |
| `new_refund_count(order, count)` | forbidden_effect | diff | exactly `count` refund rows were inserted for `order` (`any` = all orders) |
| `ticket_status(ticket, status)` | outcome | final snapshot | the ticket's `status` equals `status` |
| `ticket_note_present(ticket)` | outcome | final snapshot | the ticket's `resolution_note` is non-empty |
| `no_changes_outside(allowed)` | forbidden_effect | diff | every changed row matches an allowed entry. `refund:<order>` allows a refund insert for that order; `ticket:<id>` allows updates to that ticket |
| `call_before_writes(tool)` | process | event log | a successful `tool` call comes before the first successful write-access call, or there are no writes |

Primary success for a trial requires all three:
- every outcome assertion passes
- every process assertion passes
- every forbidden-effect assertion passes, meaning the effect is absent

Partial results are diagnostic only.

## 5. Per-module notes

### M2 Environment and gateway (Sam)
- **Tools:** implement the 7 tools in `workload.yaml` as in-process Python functions. All calls go through **one gateway class** that:
  - checks `permissions.solver` and records `status="denied"` for tools outside it
  - appends one `Event` per call (`seq` increasing from 0, `status` ok/error/denied, `error` set to one of the tool's declared errors)
  - is the only writer of the event log
- **State:**
  - `StateSnapshot.tables` uses the table names `customer`, `order`, `refund`, `ticket`, each keyed by its primary key as a string.
  - Datetimes are ISO-8601 UTC strings.
  - `now` comes from the snapshot. Never read the wall clock.
- **Reset:** reset into an isolated namespace per trial, and expose `snapshot()` before and after each run. IDs created during a run, such as `refund_id`, must be deterministic given the snapshot and the call order.
- **`issue_refund`** checks only that the order exists. It inserts a full-total refund with `created_at = now`. It must not enforce R1 or R2 (pending Q3).
- **`ask_user`** is answered by the scripted user (M8) from `EvaluationBundle.scripted_user`. The scripted user sits on the evaluator side, and only the reply text crosses to the agent.

### M3 Scorer and M4 reference tasks (Matt)
- **Scorer:**
  - Implement the templates in section 4 as pure functions of the following inputs:
    - the before/after `StateSnapshot`s
    - the `Event` list
    - the bindings
    - the assertion params
  - Return a result per assertion with its `rule_id`.
  - Don't require the reference tool-call sequence, and accept valid alternatives, such as extra read-only lookups.
- **Developing the scorer:** develop against hand-built snapshot/diff fixtures, so you don't wait for M2. Use only `audits/dev/`; `audits/withheld/` is off-limits to you and your agent.
- **Reference tasks (M4):** write 2–3 `TaskPackage`s per family in `tasks/reference/`, each with:
  - a reference procedure
  - at least one valid alternative
  - for `ambiguous_order`, `scripted_user` replies

  Keep task data that depends on Q1/Q2, such as delivery dates near the window, easy to adjust until sign-off.

### M5 Runner and M9 analysis (Nikhil)
- **Inspect adapter:**
  - The dataset is built from admitted `TaskPackage`s.
  - The solver input is `solver_json()` only.
  - Tools are the bundle's `tools`, routed through Sam's gateway.
  - The scorer calls Matt's scorer.
- **Ledger:**
  - Create a `RunRecord` with `outcome=planned` **before** dispatch, and update it afterwards.
  - Map timeouts to `task_failure`, missing evidence to `unassessable`, and runner faults to `infra_error`.
  - `configuration_digest = content_hash(config)`.
- **Recompute metrics from our records, not Inspect's reducers.** Inspect leaves unscored epochs out of the mean, so one success plus one missing epoch averages to 1.0.
- **Analysis (M9):** report coverage (counts of planned / scored / unscored / infra error) alongside every success rate.

### M1 Task package and ledger, M6 generator, M7 admission (Bilal)
- **Package storage:** store each package as `tasks/<source>/<task_id>/{meta,solver,evaluation}.json`. Fill `meta.content_hashes` from `compute_hashes()`.
- **SQLite ledger:** tracks candidates, status changes (validated with `can_transition`), rejection reasons and runs. Rejected candidates are never deleted.
- **Generator (M6):** outputs `TaskPackage` JSON that validates against the schema, with `meta.generator` set to `arm_a:<model>@<prompt_version>`.

## 6. Changing the contract or formats

1. Don't edit `contracts/` or `privatebench/schema/` inside a module PR.
2. Open a separate PR, prefixed `schema:`, that includes:
   - the change
   - updated tests
   - a `contract_version` bump in all three YAML files
   - a short note on which modules are affected
3. Bilal reviews and merges. Owners of affected modules are tagged.

## 7. Known limitations

- The workload and rules are synthetic, so the team's approval stands in for owner review. Pilot results say nothing about a real workload.
- `workflow_frequencies` is unknown. Report per family plus an equal-weight aggregate, labelled as such.
- Isolation is by convention (in-process gateway, separate files) until Sam's M8 probes test it.
