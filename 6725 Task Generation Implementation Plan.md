# 6725 Task Generation Implementation Plan

Created: 3 November 2026  
Basis: [[6725 Task Generation Research Review]] and [[6725 Knowledge Hub]]  
Status: Proposed; no implementation or experiments completed.

**Build an auditable task factory:** each output must reflect the workload, be executable through the solver's interface, and have a validated scorer. First prove one task end to end, then compare generators, then evaluate model teams.

Research claims below come from the review and have not been independently reproduced. Numerical gates, sample sizes, and effort estimates are proposed engineering choices.

## 1. Findings → implementation decisions

| Review findings | Decision |
|---|---|
| 1–2: BenchAgents / Benchmark Agent | Separate requirements, generation, and verification; persist stages and revisions; compare against direct generation |
| 3–4: TaskBench / SOP-Bench | Ground dependency graphs and scored rules in attributed workload requirements |
| 5–6: τ²-bench / AppWorld | Build resettable worlds from executable primitives; replay through solver-visible tools |
| 7–8: AutomationBench / WorkArena | Separate representative and challenge suites; audit coverage and split by structural family |
| 9: AgentSynth | Add execution-grounded generation later; distinguish reference-solver failure from task invalidity |
| 10–12: AutoBencher / BenchMaker / AutoSciBench | Store concepts and recipes; evaluate generators using blind review and independent tasks |
| 13: VerifierBench | Audit valid alternatives, failures, and exploits; measure false acceptance and rejection separately |
| 14: ToolSandbox | Treat clarification, abstention, and escalation as explicit success types |
| 18, 20: Runners and refresh practices | Keep schemas runner-independent; track lineage/exposure and maintain frozen and rotating cohorts |

Start with Python, typed contracts, JSON artifacts, SQLite state, and an Inspect adapter candidate. Inspect documents dataset/solver/scorer separation and sandboxing; compatibility still needs testing. [Tasks](https://inspect.aisi.org.uk/tasks.html), [sandboxing](https://inspect.aisi.org.uk/sandboxing.html).

Use AppWorld as a packaging reference; adopt its runtime only if workload fit justifies it. Check licenses for every reused component and dataset, including protected bundles. [Repository](https://github.com/StonyBrookNLP/appworld).

Select one runner. Compare Benchmark Agent with the structured baseline before adopting its orchestration; consider Harbor if terminal/file tasks dominate.

## 2. Pilot contract

Use customer/order/ticket resolution as a **provisional synthetic fixture**, not a claim about the user's workload. Real workload fidelity requires owner-validated procedures and examples.

Start with four families: eligible request, ineligible request, ambiguous target requiring clarification, and already-completed action requiring idempotent handling. After validation, expand to 8–12 families, potentially including missing prerequisites, escalation, conflicting records, and cross-tool workflows.

Produce `workload.yaml`, `rules.yaml`, `coverage_plan.yaml`, and an owner review record containing:

- Outcomes, example requests, required changes, and forbidden effects.
- Tool schemas, observable data, permissions, errors, and transaction behavior.
- Rules, exceptions, priorities, and clarification/escalation semantics.
- Workflow frequencies, explicitly marking unknowns.
- Rule provenance: user supplied, document derived, or assumed; source versions, confidence, unresolved questions, and review status.

Missing correctness rules block the affected family. Missing frequencies block representative weighted claims, not engineering work. Label assumed policies as synthetic. Prepare independent comparison tasks before their authors see generated examples; another LLM does not replace domain review.

## 3. Packages, state, and isolation

`brief → contract → concept/recipe → candidate → validation report → release → evaluation`

| Artifact | Contents and access |
|---|---|
| Contract / recipe | Attributed rules; family, ability, branch, dependencies, sampling constraints. Generation/reviewer access; relevant policy also goes to solver |
| Solver bundle | Instruction, permitted context, tool descriptions, task-local inputs |
| Environment | Initial state, tool version, clock/randomness controls; accessed through permitted tools |
| Evaluation bundle | Reference procedure, assertions, audits, provenance; evaluator only |
| Release manifest | Hashes, lineage, split, exposure, acceptance reports |
| Run record | Configuration, outcome, trace, cost, timing, errors, scorer version |

Extend the review's schema with `contract_version`, `recipe_id`, `parent_candidate_id`, `expected_behavior`, `rule_ids`, `content_hashes`, `exposure_events`, and `admission_status`.

Lifecycle: `draft → blocked_spec/ready → validation_failed/review_pending → admitted → quarantined/retired`. Retain rejected attempts; repairs create linked revisions. Cache keys include source, prompt, schema, model configuration, environment, and recipe versions.

Separate evaluator mounts, process access, and credentials. Export solver bundles through an allowlist and probe for leaked answers, grader paths, metadata, and audit material. Trusted runtime state/events establish completion; solver-submitted snapshots do not.

Each primitive defines types, preconditions, effects, errors, and a reference procedure, including duplicate, missing-record, and partial-failure behavior. The environment must reset into isolated run namespaces, control time/randomness, capture before/after state and append-only events, enforce permissions, and clean up after failures. Retain artifacts, source snapshots, dependencies, model IDs, prompts, and runtime configuration; seeds alone cannot reproduce runs.

Check composition dependencies, conflicting writes, and forbidden effects; replay the whole composition. Generate instructions from executable intent and verify information sufficiency. Accept alternative action orders unless policy requires an order.

Start clarification cases with scripted users and disclosure rules; test that needed information is obtainable without premature leakage. Validate any later LLM simulator separately. For abstention/escalation, check both required behavior and absence of prohibited mutations.

## 4. Admission gates and scorer audits

| Gate | Pilot requirement |
|---|---|
| Contract | Valid schema, tools, sources, attributed rules; no unresolved correctness requirement |
| Feasibility | Reference succeeds on three fresh resets using permitted tools and observable information |
| Isolation | No observed grader leak, scorer modification, or cross-run contamination in designed probes |
| Scorer | All applicable curated audit checks pass; failures quarantine the task |
| Alignment / fidelity | Every pilot release task receives independent human review for instruction/contract agreement and workflow relevance |
| Release | Complete hashes, lineage, grouping, exposure records; no detected cross-split duplicates |

Start with reviewed assertion templates parameterized by tasks. Restrict and audit any custom grader code.

Audit the reference plus at least two meaningful valid alternatives where available; unchanged/partial states; wrong targets, duplicates, collateral or over-broad changes; boundaries, missing records, and exceptions; false completion claims, forged evidence, grader access/modification; and correctness-preserving paraphrases, ID permutations, and distractors. Record why a category is inapplicable. Use single-rule violations to diagnose missing checks and event history to detect forbidden transient actions.

Derive audit labels from the contract and independent review. Keep development and withheld audit examples separate; replace withheld examples exposed during repair.

Report false acceptance = accepted invalid / invalid tested, and false rejection = rejected valid / valid tested, with counts and uncertainty by family and defect type. Passing a small audit is an admission gate, not proof of a low population error rate.

## 5. Generator experiment

Use identical output schemas and frozen briefs:

| Arm | Construction method |
|---|---|
| A | Direct task-package generation |
| B | Explicit specification, concept/recipe, and review |
| C | B + validated primitives and reference replay feedback |
| D | C + scorer-audit feedback and controlled composition |

Give every arm the same independent final evaluation. D's construction feedback must exclude withheld audit examples. D bundles two changes; if it improves, compare C-plus-audits and C-plus-composition before attributing gains.

Run 10 debugging attempts per arm; fix shared infrastructure, freeze the protocol, then target 50 attempts per arm across the same 8–12 families. Aim for about 50 admitted instances overall without hiding rejected attempts or sampling arms until acceptance quotas are met.

Predeclare candidate, token, monetary, wall-clock, and repair caps; start with at most two repairs per attempt across arms. Report actual generation, repair, replay, audit, infrastructure, and human costs.

Blind reviewers to arm, randomize order, double-review a subset, adjudicate disagreements, and retain raw labels. Without human review, report engineering diagnostics and leave fidelity unvalidated.

Measure:

- Valid-task yield per attempt and rejection reasons by gate.
- Workload/rule fidelity under a preregistered rubric.
- Withheld-audit false acceptance/rejection.
- Cost per accepted task, including failed attempts and human minutes.
- Branch coverage, duplicates, replay stability, and family-level acceptance differences.
- Secondary: latency, scorer exploits, generator-model/seed sensitivity, and agreement with independently authored tasks across solver configurations.

Use paired brief/family comparisons and family-clustered uncertainty. With 8–12 families, report per-family results and exploratory rankings; the pilot cannot establish predictive validity. Size the later study using observed variance, clustering, and a predefined meaningful effect.

## 6. Splits and contamination controls

Maintain development, agent-selection, and sealed final-test sets. Group by procedure, source, template, composition, and connected lineage **before** generating variants; keep each group within one split. Detect duplicates with hashes, normalized text similarity, and canonical graph signatures, with human review of borderline cases and documented limitations.

Treat the roughly 50-instance pilot as development data. Reserve additional sources/families for later evaluation. Report unseen instances within familiar families separately from unseen-family generalization; seeds and paraphrases do not establish independence.

Log creation, provider calls, solver/reviewer exposure, tuning use, release, and retirement. Record provider data handling; private generation does not prove no exposure. Once final results inform redesign, retain that cohort as historical and create a fresh sealed cohort. Public benchmarks validate infrastructure and inspire designs; they are not private contamination-resistant evidence.

## 7. Delivery and budget

Sequential milestones; estimates assume one engineer and timely domain review, excluding provider delays, novel tool replication, and unresolved workload decisions. Independent comparison-task authoring can proceed once the contract is stable.

| Milestone | Effort | Deliverable and exit gate |
|---|---|---|
| M0: Contract | 2–3 days | Attributed contract and draft protocol; four families have explicit success semantics |
| M1: End-to-end task | 4–6 days | Environment, bundles, ledger; replay, valid alternatives, wrong-target rejection, and isolation pass |
| M2: Primitives | 4–6 days | Four families, composition checks, assertion templates, audit harness; all admission gates pass |
| M3: Generators | 5–8 days | A–D implementations and ledger; 10-attempt smoke study per arm, then protocol freeze |
| M4: Pilot release | 5–8 days | Expand to 8–12 families; fixed-attempt study, reviewed release, independent report, full costs/rejections |
| M5: Solver readiness | 3–5 days | Single-model baselines, repetitions, accounting; no unresolved systematic execution/scoring defects |

At M1, test runner reset, tools, isolation, traces, repetitions, timeouts, and exceptions. Record the adoption decision, pinned versions, licenses, and gaps; keep the schema independent of the adapter.

Run locally first; price batches from measured smoke-run usage:

`total = generation + repair + audit-model calls + solver runs + compute/storage + human review`

Set batch ceilings and stop at them. Track model/API spend separately from the $200 AWS credit; do not assume it covers unrelated providers.

## 8. Model-team evaluation and failure handling

After M5, compare a strong single model, that model with extra inference, and two-/three-model configurations on identical releases, information, and tool permissions. Charge planning, communication, critique, retries, and switching. Declare a primary resource constraint, such as cost plus latency ceiling, and report quality/cost/latency tradeoffs; provider token counts are not interchangeable budgets.

Separate success, task failure, budget exhaustion, infrastructure error, and invalid task. Declare rerun rules, retain error counts, and apply invalid-task exclusions consistently across configurations. Fit routing/escalation on development and selection data, then test the frozen agent on sealed tasks. Retain a single-model policy when teams do not improve the objective.

| Failure | Response |
|---|---|
| Poor fidelity | Revise owner-validated contract; regenerate affected families |
| Reference failure | Diagnose information, environment, specification, and solver limitations before rejecting |
| Scorer defect | Quarantine every affected task/template; repair, re-audit, and version results |
| Low yield | Report concentration/cost; simplify recipes before raising budgets |
| Difficulty imbalance | Preserve representative suite; adjust separately labeled challenge coverage |
| Runner mismatch | Replace adapter while preserving workload semantics |

Defer document generation until retrieval/analysis is needed, retaining source evidence and answerability audits; trajectory generation until reset/replay works; trace mining until suitable deployment traces exist; behavioral judging until rubrics and human labels validate it. Browser environments and unconstrained simulation require workload justification.

**Completion:** another engineer can reproduce an admitted task and audit, trace every scored rule to its source, inspect failed attempts, and rerun the frozen generator comparison. Broader fidelity, contamination resistance, and useful team routing remain empirical questions.
