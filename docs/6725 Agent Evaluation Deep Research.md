# 6725 Agent Evaluation Deep Research

Research checked: **27 October 2026**  
Project: [[6725 Knowledge Hub]]  
Builds on: [[6725 Task Generation Research Review]] and [[6725 Environment Collaboration and Evaluation Research]]  
Status: research synthesis, repository inspection, and six isolated source-function probes; proposed evaluation protocol, not a validated benchmark or deployed agent.

## 1. Recommended strategy

Build a **workload-specific evaluation system that validates its own measurement process before using scores to construct an agent**. Use Inspect as the initial runner for the proposed API workload. Keep task admission, authoritative state grading, process constraints, audit cases, exposure records, and statistical analysis in project-owned components with explicit interfaces. Use Harbor instead if the selected workload primarily produces repository or file artifacts. Make that substitution through a small compatibility test, rather than adopting both runners.

The primary object we should select is a **deployable configuration**: model versions, prompts, tools, orchestration, memory policy, inference settings, and budget. A winning configuration is evidence for deploying that configuration on the evaluated workload. It is not a universal ranking of its constituent models.

The existing research direction survives this investigation, but it needs six additions:

1. Evaluate benchmark validity, agent performance, and operational reliability separately.
2. Audit every grading requirement against its source, including checks that wrongly reject legitimate alternatives.
3. Treat simulated users, evidence capture, infrastructure limits, and missing scores as experimental variables.
4. Measure whether the intended collaboration actually happened; retain failed or unused delegation in the team results.
5. Allocate evaluation effort according to the uncertainty limiting the decision, rather than multiplying task instances automatically.
6. Test the derived router against simple fixed policies and a development-calibrated random mixture, on additional sealed work.

This is the best-supported strategy from the reviewed evidence **for our stated objective**. Its empirical superiority, workload fit, and cost remain to be established. The workload and tools are still unselected, so this note finalizes the methodological recommendation and engineering gates, not a domain-specific success contract.

## 2. What was investigated and what was actually verified

This was a targeted investigation of failure mechanisms and implementation semantics, extending the previous reviews. Search families covered benchmark validity, grader auditing, judge calibration, simulator fidelity, harness effects, infrastructure noise, statistical uncertainty, collaboration controls, routing evaluation, and practical evaluation libraries. Technical conclusions below use primary papers, author repositories, or official documentation. Surveys and secondary summaries were discovery aids rather than evidence for individual technical claims.

For the most relevant papers, the review inspected selected methods, appendices, and limitations, not just abstracts. Depth varies and is recorded in the evidence register. Very recent preprints are treated as author-reported evidence. No finding below implies independent replication of a paper's headline result.

Four repositories were cloned for inspection. These are exact source snapshots, not claims about the latest published package:

| Repository | Inspected commit | Inspection focus |
|---|---|---|
| Inspect | `848975e870b189806109947e4f7b0246757ed6ee` | Scoring policy, epoch reduction, missing values, sandbox documentation |
| Harbor | `8bfb228d05ba23ceda72bf186c9b3586c61ee0ea` | Verifier-mode resolution, artifact transfer, pass@k aggregation |
| LangChain AgentEvals | `946ad15b9f2ce9bc9843edd2bb773bd07d78ca7e` | Strict, subset, and superset trajectory matchers |
| AgentSuite / COBA | `0f9eac1c1a376a411ad807bd974555055f08e6c5` | Task filters, score-dependent admission, auditing prompts |

Evidence and checkouts are in [6725 Agent Evals Research](/Users/nikhilpoluri/Documents/6725%20Agent%20Evals%20Research). The [manifest](/Users/nikhilpoluri/Documents/6725%20Agent%20Evals%20Research/evidence/repository-manifest.json) records origins, commits, and commit dates. [Probe code](/Users/nikhilpoluri/Documents/6725%20Agent%20Evals%20Research/evidence/probe_semantics.py) and [results](/Users/nikhilpoluri/Documents/6725%20Agent%20Evals%20Research/evidence/probe-results.json) preserve the local checks.

**Verification boundary:** the probes execute selected source functions extracted with Python's AST. They use documented stubs for unrelated loaders, message normalization, and result packaging. They establish those functions' behavior on the supplied cases. They do not establish full-package compatibility, environment fidelity, containment, model performance, or production reliability. No framework dependencies were installed, cloud resources deployed, or paid model evaluations run.

## 3. Findings that materially change our design

### 3.1 A model ranking and a system ranking answer different questions

*Agent Evaluation Reliability: More Tasks Won't (Always) Fix An Agent Leaderboard* models task, model, scaffold, and interaction effects. Its central distinction is directly relevant: model–scaffold compatibility is useful signal when choosing a system, but a confounder when claiming scaffold-independent model ability. Adding tasks does not eliminate uncertainty caused by limited scaffold coverage. The analysis is conditional on a sparse, selected competitor/scaffold population, uses latent-scale reliability, and does not establish workload validity. [Methods and limitations, September/October 2026 preprint](https://arxiv.org/html/2610.00651v1).

**Our decision:** use a common implementation for the initial single-versus-team comparison. Describe results as configuration performance. Add a small crossed model × scaffold sensitivity experiment only if we intend to make claims about model selection beyond that scaffold. A full multi-framework sweep is unnecessary for the first deployable-system decision.

This also changes how we interpret ties. If two configurations are indistinguishable at our resolution, select using cost, latency, simplicity, and severe-failure evidence; do not manufacture a precise leaderboard order.

### 3.2 Benchmark audits can themselves bias benchmark admission

AgentSuite's COBA method decomposes issues across user, environment, ground truth, and evaluation, combining rules and model judgments. The ICML publication record reports expert-alignment F1 between 0.791 and 0.874 across six benchmarks. This supports structured audits, not treating automatic flags as unquestionable ground truth. The paper's publication abstract and repository were inspected; its complete PDF methods were not reviewed in this pass. [Publication](https://proceedings.mlr.press/v306/suh26a.html).

The inspected τ² filter first identifies certain tasks without modifying reference actions, then drops those candidates only when observed mean model score exceeds 0.5. A separate communication heuristic flags criteria containing a space. These are benchmark-specific heuristics. Our isolated probe confirmed that changing a flagged candidate's supplied score from 0.4 to 0.6 changes retention to exclusion. This does not prove the resulting audited dataset is invalid; it establishes that this admission rule depends on evaluated performance. [Pinned filter source](https://github.com/Agent-Suite/AgentSuite/blob/0f9eac1c1a376a411ad807bd974555055f08e6c5/pipeline/src/benchmark_filters/tau2_bench_filter.py).

The corresponding judge prompt allows reconstruction of plausible omitted dialogue when auditing milestone trajectories. That assumption can be reasonable for incomplete reference traces, but cannot establish that an actual evaluated run obtained required consent. [Pinned audit prompt](https://github.com/Agent-Suite/AgentSuite/blob/0f9eac1c1a376a411ad807bd974555055f08e6c5/pipeline/src/prompts/tau2_bench_prompt.py).

**Our decision:** borrow COBA's decomposition and issue-report structure. Determine task validity from the workload contract and independent evidence, blind to candidate identity and comparative success where feasible. A difficult task is not invalid because agents fail; an easy task is not invalid because agents succeed. Some legitimate tasks require no mutation. Keep their answer, abstention, or clarification requirements explicit.

### 3.3 Trajectory similarity does not establish execution success

AgentEvals implements useful structural checks, but their meaning is narrower than task completion. In the pinned implementation, subset matching reverses the superset check; an empty actual trajectory passes against a nonempty reference. Superset matching accepts required calls plus additional calls. Our probes confirmed both behaviors. These are consequences of the chosen relations, not claims of package defects. [Subset source](https://github.com/langchain-ai/agentevals/blob/946ad15b9f2ce9bc9843edd2bb773bd07d78ca7e/python/agentevals/trajectory/subset.py), [superset source](https://github.com/langchain-ai/agentevals/blob/946ad15b9f2ce9bc9843edd2bb773bd07d78ca7e/python/agentevals/trajectory/superset.py).

A third probe preserved message roles and tool calls but replaced a successful tool response with a permission-denied response. The strict matcher still passed: its comparisons do not validate tool-result text. Message normalization was stubbed with already normalized dictionaries. [Strict matcher](https://github.com/langchain-ai/agentevals/blob/946ad15b9f2ce9bc9843edd2bb773bd07d78ca7e/python/agentevals/trajectory/strict.py).

**Our decision:** score effects in the authoritative environment. Use traces for actual process requirements and diagnostics. For example, require approval before a write if the business policy says so, without requiring the complete reference sequence. A legitimate alternative lookup should not fail merely because it differs from the reference.

This applies equally to “tool correctness,” “plan adherence,” and “step efficiency” metrics. Each may be useful, but a plan can be wrong, extra checking can be prudent, and a correct call can fail to change state.

### 3.4 Verifier audits need independent positive cases, not only attacks

VerifierBench's detailed cases show generated graders imposing restrictions unsupported by the task: allowed tools omitted from an allowlist, permitted representations rejected, and legitimate source locations excluded. Its targeted trace analysis also shows self-tests passing because they never vary the assumption that caused the restriction. These selected cases explain mechanisms; they do not estimate their population prevalence. [VerifierBench, sections 4 and appendix I](https://arxiv.org/html/2610.28679v1).

Weak-to-strong verifier hardening provides a complementary case: a repair passed eleven known solution replays but excluded a file needed by a fresh legitimate solution. The fresh-solver gate caught the regression. Its controlled cohort was selected for solvability and hackability, and finite replay coverage is not proof that all valid solutions remain possible. [Hardening paper, appendix E.1 and limitations](https://arxiv.org/html/2610.15924v1).

**Our decision:** every grader check needs a requirement ID and source. For each important requirement, create a violating case; for each nonessential implementation choice, create a valid variation. Use independent authors for at least part of the positive suite. Keep a blind audit set outside the grader writer's context. Reserve execution budget to finish auditing the final grader version.

Do not reject a candidate task merely because its reference replay was blocked by infrastructure. Record “feasibility unresolved” until the replay can be completed. Equally, do not admit it on the generator's statement that its tests would pass.

### 3.5 Grading isolation is an artifact contract

Harbor's inspected source resolves an unspecified verifier mode to shared execution. Its documentation says newly initialized tasks default to separate verification from v0.25, while existing tasks preserve their behavior. Separate mode creates a fresh environment and transfers declared artifacts; it does not inherit arbitrary solver filesystem changes. [Mode-resolution source](https://github.com/harbor-framework/harbor/blob/8bfb228d05ba23ceda72bf186c9b3586c61ee0ea/src/harbor/models/task/verifier_mode.py), [separate-verifier documentation](https://github.com/harbor-framework/harbor/blob/8bfb228d05ba23ceda72bf186c9b3586c61ee0ea/docs-mintlify/tasks/separate-verifier.mdx).

**Our decision:** set the mode explicitly. For API tasks, capture state from a runner-owned service or validated action replay. For file tasks, declare the permitted artifact surface and validate paths, types, sizes, and dependencies before clean regrading. Reject fabricated state reports as evidence. Preserve legitimate outputs sufficiently broadly that isolation does not quietly change the task.

Inspect's documentation also distinguishes container restrictions from host-side and provider-hosted tools, and warns that custom Compose configurations replace generated network settings. Its output-limit behavior can truncate command output. These details mean both access boundaries and evidence completeness require tests. [Sandbox documentation](https://inspect.aisi.org.uk/sandboxing.html).

SWE-Bench Pro V2 supports clean regrading and blind instruction-based reimplementation. Its authors explicitly distinguish blocked test-time retrieval from unresolved training-time exposure. [Methodology](https://arxiv.org/html/2610.24206v1). We retain that distinction rather than claiming that private instances or isolated graders make contamination impossible.

### 3.6 A simulated user is a second system under evaluation

UserProxyBench holds an agent fixed and reports a 15.2-point reward spread when changing the user proxy; 24.4% of successful episodes violate its user contract. Its appendices substantially qualify the result: one rollout per task/proxy, one fixed agent, limited nonblind human auditing, and the same model generating and grading rubrics. It measures instruction fidelity, not resemblance to actual humans. [Methods and appendices](https://arxiv.org/html/2609.38043v1).

**Our decision:** start with deterministic disclosure rules for controlled clarification tasks. Separately test a frozen LLM simulator when conversational variability matters. Record the simulator's adherence to its private contract independently of agent success: what it knew, what it disclosed, whether disclosure was requested, and whether it performed required actions.

A simulator violation is not automatically an agent failure, nor permission to silently remove a trial. Apply a predeclared measurement-failure policy, retain the original outcome, and report how often the simulator changed the task. If simulator failure depends on the agent's conversation style, removing those trials can introduce selection bias; include sensitivity analysis and investigate the interaction.

### 3.7 Strong judges still miss side effects and legitimate completions

AgentHorizon pairs closely related instructions with human-recorded computer-use trajectories. It reports 80.9% balanced accuracy for its best agentic judge on the hard subset, with substantial differences between accepting valid work and rejecting invalid work. Agentic tool access helps some model–harness combinations and hurts others; changing the harness prevents attributing all gains to one mechanism. This is evidence about its constructed computer-use distribution, not a universal judge error rate. [Methods, results, and limitations](https://arxiv.org/html/2610.11050v1).

A separate audit of 150 publicly available failure-scored computer-use traces reports 15.3% incorrect FAIL labels. Since sampling was conditional on an initial failure label, that percentage is not an estimate of the overall benchmark error rate or false acceptance. [Paper abstract; full methods not established in this pass](https://arxiv.org/abs/2607.28367).

**Our decision:** use model judges only for requirements that cannot be established reliably from state or executable artifacts. Provide the exact instruction and criterion-specific evidence. Calibrate on both valid and invalid cases, across system configurations and task families. Judge eloquence and agreement between two models are not substitutes for adjudicated labels.

### 3.8 Judge error changes estimates, not just individual labels

*How to Correctly Report LLM-as-a-Judge Evaluations* separates uncertainty in judge-labeled outcomes from uncertainty in calibration sensitivity and specificity. Its correction requires a human-defined binary target and calibration that represents the evaluated distribution. [Statistical formulation and implementation link](https://arxiv.org/html/2511.21140v1).

For interpretation, if sensitivity is Se, specificity is Sp, and the judge's positive rate is q, then the corrected population fraction is `(q + Sp - 1) / (Se + Sp - 1)`. This becomes unstable when the denominator is small. A toy q=0.80, Se=0.90, Sp=0.80 gives approximately 0.857, demonstrating that the raw judge fraction is not the same estimand. This is an illustration, not a correction we have validated for our project.

**Our decision:** in the small pilot, prefer human adjudication of ambiguous critical criteria to elaborate statistical correction on tiny calibration data. Later, if model judging is necessary at scale, propagate calibration uncertainty and test subgroup stability. Do not pool an accurate short-answer judge with a poor long-trajectory judge and report one reassuring agreement number.

### 3.9 Missing epochs and retries can silently improve the headline

Inspect distinguishes scored failures, scoring errors, unscored NaN values, and absent score entries. Unscored values are excluded from metric computation; a retry after an error can rerun solving, not just grading. [Pinned scoring policy](https://github.com/UKGovernmentBEIS/inspect_ai/blob/848975e870b189806109947e4f7b0246757ed6ee/docs/scoring-policy.qmd).

The inspected scalar reducer filters NaNs before computing its statistic. Our isolated probe confirmed that one successful epoch plus one unscored epoch reduces to a mean of 1.0. The pass@k and pass^k implementations return NaN when fewer than k scored epochs remain. These semantics are reasonable library behavior, but require explicit coverage reporting. [Reducer source](https://github.com/UKGovernmentBEIS/inspect_ai/blob/848975e870b189806109947e4f7b0246757ed6ee/src/inspect_ai/scorer/_reducer/reducer.py).

Harbor's inspected pass@k utility instead appends a zero for a trial with missing rewards and only aggregates a single binary reward. This illustrates why similarly named metrics from different runners cannot be assumed equivalent. [Aggregation source](https://github.com/harbor-framework/harbor/blob/8bfb228d05ba23ceda72bf186c9b3586c61ee0ea/src/harbor/utils/pass_at_k.py).

**Our decision:** maintain our own planned-trial ledger and recompute the declared estimands from raw records. Separate retrying a grader on frozen evidence from rerunning the agent. Never use retry-on-error as an undeclared opportunity for a new successful solve.

### 3.10 Infrastructure conditions belong in the experiment

Anthropic's infrastructure study reports that changing resource enforcement changes coding-evaluation outcomes. It recommends separating guaranteed resources from hard ceilings and calibrating headroom; its suggested multiplier is tied to the studied benchmark. Time-of-day effects are explicitly anecdotal rather than formally quantified. [Engineering study](https://www.anthropic.com/research/infrastructure-noise).

**Our decision:** pin and record CPU, memory, process limits, tool timeouts, concurrency, network policy, and worker identity. Randomize configuration execution order within task blocks and distribute blocks across time. Record throttling and outages. Do not give a team more tool-service capacity accidentally by running its arms under different infrastructure settings.

Two service objectives need different reports: model behavior under a controlled environment, and delivered service quality under actual provider outages and rate limits. The second may legitimately count those outages as operational noncompletion; it still should not misattribute them to reasoning ability.

### 3.11 Declared teams may not actually collaborate

OpenCollab explicitly audits configured versus realized organization. Its experiments serialize agents behind one lock, so they cannot establish parallel-execution benefits. It also makes the assumptions behind an adherence-adjusted causal estimate explicit; dividing a team effect by adherence is not automatically a causal correction. [Sections 3.5, appendix A, and limitations](https://arxiv.org/html/2609.38345v1).

**Our decision:** primary results include every assigned team run, including ones where delegation never happens or a critic's response is ignored. Record delegation, completed handoffs, evidence read, critique acted upon, and write ownership. Compare those diagnostics with outcomes, but do not publish success only among “properly collaborating” teams as the headline. That subset is selected after execution.

To test whether critique helps, run a controlled development ablation with critic feedback enabled versus suppressed under a specified budget. A readable trace suggesting that the critic rescued an error is useful evidence for a hypothesis; it is not by itself a causal estimate.

### 3.12 Failure diagnosis needs authoritative evidence and cautious attribution

Trial by Trace distinguishes evidence from the external service, the native harness, and model-facing messages. Its implemented “not exercised” harness criterion can resolve using the agent outcome, so its two score layers are not statistically independent. Activated failure links are explicitly not proven causal propagation. [Sections 3.3–3.5](https://arxiv.org/html/2610.32285v1).

AgentEval's DAG-based diagnosis reports useful gains on its evaluated workflows, but its taxonomy was derived from three workflow types and has incomplete out-of-domain coverage. Its expert agreement and root-cause results should not be assumed to transfer to arbitrary team topologies. [Methods and extended limitations](https://arxiv.org/html/2604.23581v1).

**Our decision:** retain separate task outcome, harness behavior, and measurement integrity fields. Build a dependency graph from observed tool and handoff events for diagnosis. Label causes as observed, hypothesized, or experimentally supported. Where useful, rerun a development case with one repaired upstream result to test an attribution; report that intervention separately from normal task success.

### 3.13 Robustness and security require their own denominators

AgentNoiseBench separates user noise and tool noise and proposes solvability-preserving perturbations. Its trajectory diagnostics are correlational and its stated scope does not establish behavior in all asynchronous architectures. [Construction and limitations](https://arxiv.org/html/2602.11348v1).

AgentDojo evaluates legitimate utility alongside attacker objectives in a stateful environment. This is a useful design reference for testing whether an agent can continue useful work while resisting instructions embedded in untrusted tool content. [Paper](https://arxiv.org/html/2406.13352v3), [repository](https://github.com/ethz-spylab/agentdojo).

**Our decision:** distinguish harmless variations, recoverable service faults, changed business requirements, and adversarial content. Only the first category should necessarily preserve the original correct outcome. A permanent outage may change the required behavior to truthful escalation. Report clean utility, attacked utility, attack success, and refusal/escalation separately. A system that refuses every task is not a successful assistant.

### 3.14 Routing must earn its complexity

*Dynamic LLM Routers are Often Misguided* finds its studied commercial routers fail to beat a matched-cost random mixture of two well-chosen models. It concerns single-turn benchmark traffic, uses one sampled outcome per query, and explicitly does not solve multi-turn routing. [Methods and limitations](https://arxiv.org/html/2610.02762v1).

Agent-as-a-Router offers a contrasting positive result using execution feedback and memory for coding. Its monetary estimates cannot fully observe cache effects; its agentic evaluation uses a reduced step limit. We should not assume that a budget change leaves relative performance invariant in our own workload. [Methods and limitations](https://arxiv.org/html/2606.22902v1).

**Our decision:** compare the learned policy with a fixed strong single agent, the best fixed team, simple task-type rules, and a random mixture whose probabilities were fixed on development costs. Charge routing, repeated context, fallback, and failed attempts. Evaluate the whole routed workflow from fresh initial state. Offline per-step labels do not establish end-to-end performance when earlier routing changes later observations.

The objective should reflect user value. If mistakes on difficult cases are costly, encode that explicitly instead of presuming unweighted average accuracy captures the preference. Neither sophisticated routing nor escalating every hard task is automatically optimal.

## 4. Framework choice after inspecting the semantics

These tools occupy different layers. The table records suitability for this project, not an empirical speed or quality ranking.

| Tool | Evidence inspected | Recommended role | What we still must supply |
|---|---|---|---|
| **Inspect** | Pinned reducer code, scoring/sandbox docs, multi-agent docs | Initial runner for controlled API and mixed model-team experiments | Workload semantics, independent graders, trial ledger, team-wide budget enforcement, statistical analysis |
| **Harbor** | Pinned verifier-mode, artifact, and aggregation code | Alternative when terminal/repository/file outputs dominate | Valid task contracts, trusted transfer/regrading, side-effect and process checks, aligned accounting |
| **AgentSuite / COBA** | Publication abstract, pinned filters and audit prompts | Audit taxonomy and diagnostic inspiration | Independent adjudication and admission rules without candidate-performance dependence |
| **LangChain AgentEvals** | Pinned matching code; isolated probes | Selected regression and process diagnostics | Backend success checks; justification for which ordering or call constraints are mandatory |
| **DeepEval** | Official task-completion and agent-evaluation docs | Optional semantic/component evaluation if useful to application development | Independently grounded task, calibrated judge, state evidence; its documented task extraction cannot define our ground truth |
| **Ragas** | Official agent-metric docs | Optional retrieval/answer-quality branch and tool diagnostics | Outcome semantics, error calibration, alternative-solution handling |
| **Phoenix** | Official experiments reference and repository overview | Optional trace inspection, annotation, and experiment UI | Environment resets, authoritative scoring, reproducibility manifest, sealed-cohort control |
| **Braintrust** | Official experiment documentation | Optional managed experiment records and review workflow | Same scientific contract; verify data handling and budget separately before adoption |
| **AgentDojo** | Primary paper and repository | Security challenge-suite patterns if tasks consume untrusted content | Adapted business tasks and representative attack exposure; not the main workload benchmark |

Sources for documentation-only rows: [DeepEval task completion](https://deepeval.com/docs/metrics-task-completion), [Ragas agent metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/agents/), [Phoenix experiments API](https://arize-phoenix.readthedocs.io/projects/client/api/experiments.html), [Phoenix repository](https://github.com/Arize-ai/phoenix), [Braintrust experiments](https://www.braintrust.dev/docs/evaluate/run-evaluations). These products were not installed or benchmarked.

Inspect documents explicit workflows, agents-as-tools, and handoffs, which fit controlled comparisons without a second orchestration dependency. [Multi-agent documentation](https://inspect.aisi.org.uk/multi-agent.html). This supports keeping the existing Inspect recommendation. It does not prove that its defaults implement our experimental protocol.

**Selection gate:** run the same handful of development contracts through the chosen stack, including successful, deliberately incorrect, interrupted, and unscoreable trials. Check reset, state access, accounting, and regrading. Change runners if a mandatory requirement cannot be met cleanly. Avoid choosing a platform by the number of metrics in its catalog.

## 5. The evaluation contract we should implement

The following is **our proposed protocol**, derived from the evidence and project constraints. Specific counts are engineering starting points, not literature-established optimal values or approved spending.

Represent the evaluation as three connected contracts:

| Contract | Questions it answers | Primary evidence |
|---|---|---|
| **Task contract** | Is this representative, sufficiently specified, feasible, and correctly graded? | Source rules, initial state, reference replay, independent alternatives, audit results |
| **Execution contract** | What exact configuration ran, what could it see, and what happened? | Frozen manifest, gateway ledger, tool outcomes, role/handoff events, resource and exposure records |
| **Decision contract** | What inference will justify choosing this configuration? | Prespecified estimand, comparisons, weights, uncertainty, cost limits, severe-failure thresholds |

For every task, extend the prior task schema with requirement-level provenance and evidence rules:

```yaml
task_contract:
  task_id: example_001
  family_id: independently_defined_workflow_family
  source_lineage_id: source_bundle_01
  split: development
  user_instruction: public/instruction.md
  initial_snapshot_digest: assigned_at_build
  tool_schema_digest: assigned_at_build
  requirements:
    - id: R1
      source: workload_contract#rule_1
      kind: outcome             # outcome | process | forbidden_effect | artifact
      evidence_authority: backend_state
      severity: critical
  allowed_variations: private/alternatives.json
  verifier_digest: assigned_after_audit
  audit_suite_digest: assigned_after_audit
  acceptance_status: unresolved
execution_contract:
  trial_id: assigned_before_dispatch
  configuration_digest: frozen_configuration
  snapshot_digest: verified_before_dispatch
  simulator_digest: none_or_frozen_configuration
  budget_policy_digest: frozen_whole_team_policy
  evidence_manifest: runner_owned
```

This is a conceptual schema, not a tested framework API. Solver-facing and evaluator-private fields must be serialized separately. A private path in a shared metadata object is not a security boundary. The model must receive all business rules needed to act correctly, while hidden checks implement those rules rather than introducing secret obligations.

For a valid and assessable trial, primary success requires **all required outcomes, all mandatory process conditions, and no forbidden effects**. Diagnostic partial completion is reported separately. Missing evidence produces an explicit unresolved measurement status unless the task contract itself requires the agent to produce that evidence and the trusted observer confirms it did not.

An illustrative example: “update the designated record after approval” requires the correct record to change, approval to precede the write, and unrelated records to remain intact. A final-state match alone misses a write followed by retroactive approval. A call trace alone misses a rejected write. A reference-path match may reject a different valid lookup. We therefore need both trusted state and the relevant event order.

## 6. Admission and grader-validation gates

Before using tasks to compare models:

1. **Ground the rules.** Map each requirement to user-provided or document-derived evidence. Mark assumptions explicitly. Obtain domain review of representative coverage and severe-error definitions.
2. **Demonstrate feasibility.** Replay the reference through solver-available tools and information. Start with repeated replay across at least two fresh worker processes; a proposed twenty-reset engineering check is a smoke test, not a reliability guarantee.
3. **Test legitimate variation.** Include an independently authored solution and, where applicable, at least two distinct legal variants. Vary irrelevant ordering, permitted formatting, optional defaults, additional read-only checks, and alternative valid tool paths.
4. **Test individual violations.** For each critical requirement, construct a case that violates it while satisfying the others. Add no-op, wrong-target, duplicate-write, partial-completion, fabricated-success, and unrelated-state-change cases where relevant.
5. **Test the measurement boundary.** Confirm that missing evidence, malformed artifacts, lost logs, grader exceptions, and a solver timeout receive their declared statuses. Confirm that regrading does not rerun the solver.
6. **Audit independence.** Hold back some audit cases from the grader author. Blind reviewers to generator condition and candidate identity where possible. Use at least two reviewers on disputed or high-consequence cases and record disagreement resolution.
7. **Freeze accepted versions.** Store hashes for instruction, rules, state, tools, scorer, and audit suite. If a test exposes a defect, repair and rerun affected checks before admission.

The engineering gate is zero known critical false acceptances and zero known false rejections on the required finite suite, with unresolved cases blocking admission. Report the actual number and diversity of audit cases; passing five closely related variants does not establish the same coverage as five independently constructed cases.

The common external audit applies to all four generator conditions from the existing plan. Condition D's internal audits remain part of its construction cost. Preserve both raw candidate yield and externally accepted yield. Otherwise the study would merely award D credit for having an audit stage while measuring its competitors differently.

Keep rejected candidates and reasons. Rejection analysis is important because the generator may systematically discard realistic but difficult procedures, ambiguous-but-resolvable requests, or lawful alternative solutions.

## 7. Cohorts, validity, and contamination

Use four separately governed collections:

| Collection | Permitted use | Exposure rule |
|---|---|---|
| Infrastructure fixtures and public benchmarks | Debug runner, adapters, and scoring | Public status recorded; no private-benchmark claim |
| Development families | Improve generator, environment, prompts, team protocol, and diagnostics | Full access; all feedback is development feedback |
| Selection families | Select a bounded set of frozen candidate configurations and route rules | Record accesses and comparisons; repeated use creates selection overfitting |
| Sealed confirmation and transfer cohorts | Test the selected configuration and derived routing policy | No tuning from results; reserve additional data for any subsequent revision |

Split by shared procedure, document lineage, template, and composition, not just by random seed. Maintain an independently authored transfer set as well as generated tasks. Distinguish new instances within known families from new families and new tool environments: these test different kinds of generalization.

Unknown workload frequencies are a real limitation. Initially report per-family performance and an explicitly labeled equal-family aggregate. Introduce workload prevalence weights only when user evidence supports them. Keep challenge cases separate from representative workload estimates.

The contamination protocol from the prior reviews remains: private source lineage and exposure logs; solver/answer separation; restricted retrieval; local duplicate checks; clean trial memories; no public-search queries containing sealed task text. Add the same controls to grader prompts, simulator prompts, trace viewers, caches, exported annotations, and routing memories. A sealed task leaked through an observability service is still exposed.

For evaluators that see the answers, store their logs under evaluator access rules. Clean regrading must use a frozen evidence package. It cannot rely on the evaluator browsing the current mutable application state after later trials have changed it.

## 8. Controlled comparison of individuals and teams

Preserve the six proposed configurations:

| Arm | Purpose |
|---|---|
| A alone | Single-model reference |
| B alone | Alternative model and complementary errors |
| Best development-selected single with extra inference/self-review | Controls for spending more compute |
| A executor + B critic | Tests heterogeneous critique |
| A executor + A critic | Separates role structure from model diversity |
| Coordinator + two specialists | Tests decomposition where independent subtasks actually exist |

Do not run the full matrix immediately. Screen a small subset, then spend confirmation budget on the comparisons that matter. Freeze model revisions, provider endpoints, inference settings, prompts, context compaction, tool permissions, termination, and budgets for each configuration.

Set a common **whole-configuration dollar cap and deadline** for the primary deployment comparison. Record realized spend, latency, and tokens separately; the same token count does not imply the same expense or information-processing budget across models. In later research, budget-response curves at several common caps are more informative than a single cap. Do not select cap values after seeing which one makes a team win.

Before each call, reserve estimated maximum billable cost against the shared budget. Reconcile measured usage after completion. Include concurrent reservations so multiple specialists cannot each spend the same remaining balance. Budget exhaustion is a recorded outcome, not permission to drop the trial. Preserve cost of model errors, failed tools, critic calls, simulator calls, retries, and fallback; report evaluation overhead separately from deployable-agent cost.

Each handoff should include trial ID, role, subgoal, evidence references, state version, tool permissions, remaining budget, expected output, and stopping condition. Record which evidence the recipient actually received. Use one write owner in executor–critic teams; serialize conflicting writes in specialist teams. Read-only concurrency and concurrent writes are different interventions and should not be bundled into one unexplained “multi-agent” condition.

Primary comparison: paired change in success of the selected team against the extra-inference single baseline, within the declared constraints. Secondary comparisons test diversity and decomposition. Team failures remain in the assigned arm even if the architecture was not followed. Do not retrospectively define a team as “really multi-agent” only when it succeeds.

## 9. Metrics and statistical decision rules

The experimental unit has several levels: source lineage → family → instance → configuration → repeated trial. Shared lineage can correlate even nominally different families. Choose the highest meaningful independent sampling unit and preserve paired observations when estimating uncertainty.

*Adding Error Bars to Evals* provides the foundation for paired differences, clustered uncertainty, and power analysis. Its methods require attention to the sampling design; they do not make a tiny convenience sample representative. [Paper](https://arxiv.org/abs/2411.00640), [authors' explanation](https://www.anthropic.com/research/statistical-approach-to-model-evals).

Our reporting contract:

| Quantity | Definition and interpretation |
|---|---|
| End-to-end success | All contract requirements satisfied, for valid assessable trials |
| Severe violation | Any predeclared severe forbidden event; report by category and configuration |
| Partial completion | Requirement-level diagnostic, never compensation for a critical violation |
| Task validity | Externally accepted / attempted candidates, plus rejection categories and audit uncertainty |
| Scorer validity | False acceptance among invalid audit cases; false rejection among valid cases; unresolved judgments separate |
| Repeatability | Task-level single-run success and pass^k where enough valid trials exist |
| Best-of-k potential | pass@k, explicitly distinct from a deployable retry-and-selection policy |
| Resource use | Dollars per attempted run; aggregate dollars / successes; median and p95 latency; usage by role |
| Coverage | Planned, dispatched, attempted, scored, failed, unassessable, invalidated, retried, and cancelled counts |
| Robustness | Paired changes under each validated perturbation class |
| Transfer | Frozen-policy performance on independently authored and held-out families, separately reported |
| Collaboration | Delegation realization, communication cost, ignored evidence, conflicting writes; diagnostic status |

For c successes among n independent, identically configured trials of one task:

```text
pass@k = 1 - choose(n-c, k) / choose(n, k)
pass^k = choose(c, k) / choose(n, k), for k <= n
```

Average at task/family level under declared weights. Three repeats do not support pass^20. Neither metric accounts for persistent side effects in a real retry policy; evaluate that policy as a complete workflow if we intend to deploy it.

For each family, calculate the paired difference between configurations after aggregating its instances and repeats. Estimate uncertainty by resampling independent family/source clusters while preserving the paired data, and examine sensitivity to individual families. With only 8–12 families, intervals are fragile. Do not fit a large interaction model and mistake its regularized estimates for information the experiment did not collect.

For larger studies, a hierarchical logistic model may estimate family, model, scaffold, and simulator interactions. Use connected comparisons and report model assumptions. The first pilot only needs enough analysis to identify whether the limiting uncertainty is measurement error, repeated-run variability, family coverage, or a scaffold interaction.

Predeclare a minimum worthwhile improvement, a maximum acceptable severe-failure rate, and resource limits. These require workload-specific judgment. Promote a team only when evidence supports the chosen improvement or a prespecified cost-saving/noninferiority objective. If the interval is too wide, report the result as inconclusive and retain the simpler eligible baseline; absence of a significant difference is not proof of equivalence.

For missing measurements, report both conditional performance and planned-trial coverage. Example: 100 valid planned trials yield 70 confirmed successes, 10 confirmed failures, and 20 unassessable outcomes. Scored-only success is 87.5%, confirmed success per planned trial is 70%, and assigning unknown outcomes either way gives a 70–90% sensitivity range. These describe different quantities. An operational noncompletion metric may classify unassessable runs conservatively, while capability analysis retains their uncertainty.

Zero observed severe failures does not establish a low population rate. Under independent Bernoulli sampling, the one-sided 95% upper bound after zero events is `1 - 0.05^(1/n)`: about 5.8% at n=50 and 1.0% at n=299. Correlated variants weaken the independent-sampling interpretation. This is why fifty accepted pilot tasks cannot certify safety or production reliability.

## 10. Efficient budget allocation and stopping

Keep the prior $200 allocation as a provisional funding constraint; credit eligibility is still unknown. Do not assume external API charges consume AWS credit. This review did not obtain current provider quotes or approve new spending.

A first solver-cost probe might use **12 development tasks × 3 configurations × 2 repeats = 72 trials**. At illustrative all-solver-call costs of $0.10 / $0.50 / $2 per trial, that is $7.20 / $36 / $144 before task construction, graders, simulators, human review, or environment costs. If simulator calls are included in a measured trial cost, do not add them again. This probe estimates feasibility; it is not enough to establish repeatability or a final winner.

Use the cost probe to select what to buy next:

| Observed limitation | Next investment |
|---|---|
| Many grader disputes | Independent labels and grader repairs |
| Poor reset/evidence reliability | Environment and logging fixes |
| Simulator disclosure violations | Simulator contract and calibration |
| Large variation across repeats | More repeats on a representative subset |
| Large variation across families | New independent families and expert tasks |
| Model rank changes across scaffolds | Small crossed scaffold experiment |
| Wide interval around team gain | More paired evidence on the primary comparison |
| Little room above a simple fixed policy | Defer complex routing |

The prior 50 accepted instances across 8–12 families remain an engineering target. The full six-arm, three-repeat matrix still means 900 trials. Scale only after measured cost and quality gates support it.

Adaptive selection is acceptable on development data. Freeze final sample size, primary comparisons, and handling rules before opening sealed results. If early stopping is desired for the final study, specify a statistically valid sequential procedure in advance; repeatedly checking ordinary confidence intervals until one looks favorable is not a valid substitute.

## 11. Constructing and confirming the customized agent

Use development and selection results to derive the simplest useful policy. Candidate features must be available before or during real execution: requested task type, visible tool scope, input size, explicit ambiguity, and observable tool failures. Do not use hidden grader results, future success, or evaluator-only family labels as routing features.

First test task-level routing between eligible configurations. Escalation should have a declared trigger, stopping rule, handoff, and cost cap. If the policy learns from cross-task memory, define its update schedule and evaluate it as a separate online-learning condition; never let later sealed outcomes influence earlier decisions.

Evaluate the derived policy on fresh tasks after its rules are fixed. If an earlier confirmation cohort informed routing choices, it is selection evidence for the router and cannot also serve as its untouched final test. Compare against the best fixed single agent, best fixed team, simple rule policy, and random mixture. Report realized performance by workload slice so savings on easy cases cannot hide unacceptable failures on consequential cases.

Do not assume a favorable generator comparison automatically produces a useful deployment benchmark. Test whether generated-task results predict the same configuration choices on independent human-authored work. If rankings or failure patterns disagree, inspect missing rules, unrealistic tools, sampler bias, and grading artifacts before scaling the generator.

## 12. Implementation order and concrete acceptance gates

| Stage | Deliverable | Gate to advance |
|---|---|---|
| 1. Workload definition | Source-backed contract, tool surface, representative/challenge split, error severity | Domain reviewer accepts semantics; unresolved correctness assumptions recorded |
| 2. Evaluation skeleton | Versioned package, resettable world, trusted state/event capture, Inspect adapter | Reference replay and deliberate bad cases behave as specified |
| 3. Measurement audit | Independent positive/negative cases, isolation/evidence checks, missing-score ledger | No known critical acceptance or valid-alternative rejection in required finite suite; no unresolved admission failures |
| 4. Generator study | A–D candidates evaluated under common external audit | Yield, fidelity, coverage, repairs, and cost reported; accepted sample supports engineering feasibility |
| 5. Solver screen | Bounded paired single/team comparisons, measured costs | Eligible configurations identified without hidden-test tuning; inconclusive results retained as such |
| 6. Confirmation | Frozen configuration and fresh sealed families | Prespecified quality/resource/severity decision supported at declared uncertainty |
| 7. Policy derivation and transfer | Simple router/escalation policy, additional untouched tasks | Whole policy beats an appropriate fixed/simple baseline under the chosen objective, or complexity is rejected |

If resources cannot support stage 6, the defensible project outcome is an audited evaluation prototype plus exploratory configuration results. It should not be presented as a reliable universal model selector. If teams do not help, constructing a single-model agent with evidence-based escalation still fulfills the project's core objective.

## 13. What this research settles, and what remains open

**Methodological recommendation:** keep executable task packages; select deployable configurations; prioritize trusted state and required process evidence; validate both graders and simulators; compare teams under whole-system budgets; report missingness and family-level uncertainty; confirm the resulting policy on fresh work.

**Framework recommendation:** Inspect first for the proposed API pilot, with Harbor as the artifact-heavy alternative. Use COBA, AgentEvals, Ragas, DeepEval, and observability products only for clearly identified supporting functions. None replaces the task contract or independently audited success semantics.

**Still requires user/domain input:** actual workload and tools, acceptable error consequences, workload frequencies, expert-review availability, minimum useful improvement, deployment deadline/cost constraints, and AWS-credit eligibility.

**Still requires experiments:** runner/environment compatibility, state resets, artifact boundaries, judge calibration, simulator fidelity, empirical costs, best models, useful team protocols, final sample size, and transfer. The six isolated probes validate narrow implementation semantics, not these properties.

The next concrete artifact should be the workload contract plus a small set of executable, independently audited development tasks. Further broad literature collection has lower immediate value than implementing and trying to falsify this evaluation design.
