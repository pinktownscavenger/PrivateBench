# Task Generation Research Review

Research checked: **25 October 2026**  
Project: [[6725 Knowledge Hub]]  
Scope: workload-specific task generation, validity, scoring, datasets, implementation frameworks, and contamination resistance.

## Main recommendation

Build a task-generation system that produces an **executable evaluation package**, including the instruction, starting state, tools, expected outcomes, verifier, and provenance. Use LLMs to interpret the workload and propose variations; use executable environments, validated procedures, and independent checks to establish whether the generated task is meaningful and scoreable.

My recommended starting combination is **BenchAgents/Benchmark Agent for requirements and generation structure; SOP-Bench and TaskBench for workload representation; τ²-bench and AppWorld for executable task construction; and VerifierBench for auditing the scorer**. AutomationBench is a particularly relevant source of cross-application workflow patterns. These are complementary design references, not a claim that the projects can be plugged together without adapter work.

The research does not establish that arbitrary human workload descriptions can already be converted into reliable benchmarks fully automatically. The gap between a short description and a sufficiently specified, representative workflow remains part of our research problem.

## How this review was conducted

I searched for foundational and recent work, followed references to related generation methods, and checked primary papers, author repositories, official documentation, and current release descriptions. The review includes 20 findings, with implementation recommendations explicitly separated from reported capabilities.

Evidence labels:

- **Published research:** a conference publication was verified where stated.
- **Preprint:** an author-reported research result; no independent replication is implied.
- **Implementation/documentation:** the project documents the feature; I have not installed or executed it.
- **Access limitation:** the relevant artifact could not be retrieved during this review.

This is a targeted technical review, not an exhaustive systematic review. Search coverage extends through the date above; “current” means observed in the retrieved sources, not a guarantee that no newer commit exists. No model rankings from different benchmark versions are treated as comparable. Repository availability is not evidence of production readiness.

## Findings and how we would use them

### 1. BenchAgents — structure the generation process

**Evidence:** 2024 paper and full-text methodology. It separates planning, data generation, verification, and evaluation into interacting agents, with developer feedback. Its demonstrations concern calendar planning and constrained text generation. [Paper](https://arxiv.org/abs/2410.22584), [full text](https://arxiv.org/html/2410.22584v1).

**Review:** This is a strong conceptual match for our generation pipeline because it treats data quality and scoring as explicit stages. Its demonstrations are narrower than arbitrary enterprise tool workflows. Separating agents also does not by itself make their judgments independent, especially when they share a base model.

**Our use:** Create separate artifacts for the workload specification, generation plan, task instance, and quality report. A verifier should reject or return a task for revision with a recorded reason. Human feedback should revise the specification or generation rules, rather than silently patching individual examples.

**Decision:** Adopt the process architecture; independently evaluate whether multiple generator agents justify their extra cost. Multiple agents constructing a benchmark is distinct from multiple models solving it.

### 2. Benchmark Agent — a recent natural-language entry point

**Evidence:** June 2026 preprint, *Benchmark Everything Everywhere All at Once*, and public code. The authors report generating 15 benchmarks across text, multimodal understanding, and domain reasoning. The repository documents requirement analysis, subtask design, grounding, transformation planning, realization, quality control, and intermediate caching. [Paper](https://arxiv.org/abs/2606.06462), [repository](https://github.com/Shiyun-x/Benchmark-Agent).

**Review:** One of the closest references to our “describe what you want to evaluate” interface. However, generating benchmark samples across modalities does not establish the ability to construct faithful, stateful replicas of arbitrary business tools. Treat autonomous-quality claims as author results, not guarantees.

**Our use:** Inspect its requirement-to-specification and caching interfaces as a prototype candidate. Test whether it can preserve explicit workload requirements while generating executable task packages through a custom backend.

**Decision:** High-priority implementation spike. Compare it against a simple structured-output baseline before adopting its entire orchestration stack. Code reuse terms and dependencies still need a dedicated check.

### 3. TaskBench — generate from a tool dependency graph

**Evidence:** NeurIPS 2024 work. TaskBench represents dependencies with a tool graph and uses back-instruction to generate natural-language requests from structured tasks. Evaluation separates decomposition, tool selection, and parameter prediction, with human verification in construction. [Paper](https://arxiv.org/abs/2311.18760), [publication record](https://www.microsoft.com/en-us/research/publication/taskbench-benchmarking-large-language-models-for-task-automation/), [code and data](https://github.com/microsoft/JARVIS/blob/main/taskbench/README.md).

**Review:** A useful answer to a central generation problem: start from a coherent computation and then express its intent in language. Matching a predicted graph or tool sequence is weaker evidence than demonstrating correct execution; a different graph may also be valid.

**Our use:** Construct a dependency graph from the user's tools and workflow. Sample feasible graphs, initialize the required data, and verbalize their goals. Retain the graph for generation and diagnosis, but score valid outcomes without requiring the solver to reproduce the reference path.

**Decision:** Adopt the representation and generation direction; extend it with executable semantics.

### 4. SOP-Bench — ground generation in actual procedures

**Evidence:** The current Amazon release describes over 2,000 tasks and 12 industrial domains, with expert-authored procedures, executable interfaces, and generated test cases. The extension format includes an SOP, tools, tool schemas, data, and metadata. The older arXiv abstract describes over 1,800 tasks and 10 domains. [Current release](https://www.amazon.science/blog/sop-bench-a-new-benchmark-for-evaluating-ai-agents-on-real-business-procedures), [repository](https://github.com/amazon-science/SOP-Bench), [older paper record](https://arxiv.org/abs/2506.08119).

**Review:** Particularly relevant to the gap between a vague workload description and real procedural requirements. Its expert-authored starting point matters: the framework does not demonstrate that unvalidated LLM-generated policies are adequate substitutes.

**Our use:** Translate user input into a draft SOP and collect missing business rules. Generate cases by decision branch, including exceptions and missing-information paths. Require explicit provenance for each rule: user supplied, document derived, or proposed assumption.

**Decision:** Primary workload-grounding reference. Pin the dataset release so older paper counts are not mixed with current results.

### 5. τ²-bench and the current τ-bench repository — compose executable scenarios

**Evidence:** The 2025 τ²-bench paper defines atomic scenarios using initialization, solution, and assertion functions, then composes them into telecom tasks. It couples the user simulator to environment state. The current repository advertises **τ-bench 2.0**, following τ³-bench, and explicitly says 2.0 English scores are not comparable with v1.x. [Paper](https://arxiv.org/html/2506.07982v1), [current repository](https://github.com/sierra-research/tau2-bench), [current release description](https://raw.githubusercontent.com/sierra-research/tau2-bench/main/README.md).

**Review:** One of the strongest references for task construction from executable primitives. The paper's correctness claims are bounded by its modeled environment; they do not establish realism or simulator perfection. Dual control means user and agent act in a shared environment, not that it already benchmarks arbitrary LLM teams.

**Our use:** Give each primitive preconditions, setup, a reference solution, and assertions. Compose compatible primitives and test the complete composition after resetting the environment. Use a constrained user simulator only when clarification is part of the workload.

**Decision:** Primary compositional-generation reference. Freeze a specific version rather than using a moving default branch.

### 6. AppWorld — generate complete task worlds and test side effects

**Evidence:** ACL 2024 resource with 750 tasks, application APIs, and state-based evaluation. The current repository includes guides for new task generators, database generation, and MCP integration. [Repository](https://github.com/StonyBrookNLP/appworld), [task-generator guide](https://github.com/StonyBrookNLP/appworld/blob/main/guides/developing_new_task_generators.md).

**Review:** Useful when a task crosses multiple applications and changes records. It provides a concrete engineering reference for making generated tasks executable. The available app universe is a constraint, and building a faithful new app requires work. The repository distinguishes ordinary public code from protected bundles with additional redistribution conditions; check the applicable components before reuse.

**Our use:** Borrow the task-world boundary: each instance owns initial data, goal, solution metadata, and tests. Check preservation of unrelated state as well as requested changes. Use existing development tasks to validate our harness, then generate private workload-specific instances.

**Decision:** Strong candidate for a prototype environment and task packaging reference.

### 7. AutomationBench — realistic cross-application business workflows

**Evidence:** April 2026 paper and Zapier repository. Current public data includes 600 scored tasks across six business domains, plus a separate 200-task simple set. It uses simulated SaaS state and assertions. Official scores use a separate private set. [Paper](https://arxiv.org/html/2604.18934v1), [repository](https://github.com/zapier/AutomationBench), [official methodology](https://zapier.com/benchmarks).

**Review:** Very close to our business-workload use case. Its generation process uses customer workflow patterns and hardens scenarios with distractors, hidden information, and policy rules. That helps create challenging tests but can distort the normal workload distribution. An open issue reports data-quality problems affecting 108 cases; this is a contributor report, not an independently verified count of defective tasks. [Issue](https://github.com/zapier/AutomationBench/issues/28).

**Our use:** Reuse workflow categories and the initial-state/action/assertion design. Maintain positive and negative assertions, so an agent cannot pass by modifying every record. Audit individual imported tasks and separate representative workload evaluation from deliberately hard cases.

**Decision:** High-value dataset and environment candidate, conditional on task-level audits.

### 8. WorkArena / WorkArena++ — controlled workflow composition

**Evidence:** ICML 2024 WorkArena and NeurIPS 2024 WorkArena++. The current repository describes 33 atomic task types, 19,912 L1 instances, and 682 compositional tasks with many configurations. Running them requires access to ServiceNow instances. [Repository](https://github.com/ServiceNow/WorkArena), [WorkArena++ paper](https://arxiv.org/abs/2407.05291).

**Review:** A strong example of expanding coverage through combinations of meaningful operations. Browser operation and the ServiceNow environment introduce costs that may be irrelevant to an API-only prototype. Numerous instances do not necessarily imply numerous independent workflow structures.

**Our use:** Adopt a catalog of atomic skills and a controlled composition curriculum. Vary reasoning dependencies and policy branches separately from interface difficulty. Split datasets by workflow family, not only random instance seeds.

**Decision:** Design inspiration now; integrate when browser-based enterprise work becomes a target domain.

### 9. AgentSynth — generate tasks from successful execution

**Evidence:** 2025 preprint and repository labeled ICLR 2026. A proposer produces persona-guided subtasks, an execution agent performs them, and another agent summarizes sequences into composite tasks. The authors report more than 6,000 tasks. [Paper](https://arxiv.org/abs/2506.14205), [repository](https://github.com/sunblaze-ucb/AgentSynth).

**Review:** Execution provides stronger evidence of feasibility than a model's assertion that a task is solvable. However, accepting only tasks that a particular generator can execute biases the dataset toward that generator's capabilities. A successful trajectory also does not guarantee a complete verifier.

**Our use:** Add a trajectory-grounded generation branch: execute validated subtasks, compose them, and produce a fresh instruction for the resulting goal. Replay from a clean initial state. Track candidates rejected because of solver failure separately from those proven invalid.

**Decision:** Useful expansion strategy after reliable primitives and resettable environments exist.

### 10. AutoBencher — optimize benchmark coverage and informativeness

**Evidence:** ICLR 2025, *AutoBencher: Towards Declarative Benchmark Construction*. It searches over dataset descriptions using explicit objectives such as salience, difficulty, and novel performance patterns; privileged source information supports generation. [Published paper](https://openreview.net/pdf?id=ymt4crbbXh), [repository](https://github.com/XiangLi1999/AutoBencher).

**Review:** Useful for choosing what to generate next. Its notion of novelty concerns performance patterns and should not be confused with proof that test content was absent from training. Adaptively choosing tasks against candidate models can also skew comparisons.

**Our use:** Define generation objectives including workload relevance, branch coverage, task validity, and information gained about model differences. Use adaptive search only in development; freeze an independently generated final evaluation set.

**Decision:** Adopt the optimization framing, with workload relevance taking precedence over simply making all models fail.

### 11. BenchMaker — evaluate the generator itself

**Evidence:** *LLM-Powered Benchmark Factory*, ACL 2026; earlier preprint in 2025. The published version defines an evaluation framework with four dimensions and ten criteria and reports agreement with human-authored benchmarks across 21 LLMs, including a 0.969 Pearson correlation for MMLU-Pro. The older abstract reports different figures. [Published version](https://aclanthology.org/2026.acl-long.1661/), [earlier record](https://arxiv.org/abs/2502.01683).

**Review:** A valuable reminder that the generator is a system requiring evaluation. Agreement with an existing benchmark's rankings is useful evidence in that setting; it does not establish workload fidelity, contamination resistance, or correct stateful environments.

**Our use:** Build a separate generator evaluation set containing workload briefs and expert-reviewed tasks. Measure whether generated tasks satisfy the briefs, have valid answers, cover intended branches, and preserve useful distinctions between solvers.

**Decision:** Methodology reference for our generator ablation study, rather than the core environment layer.

### 12. AutoSciBench — recent concept-to-recipe generation and refinement

**Evidence:** 4 October 2026 preprint. It separates high-level task concepts from construction recipes and uses solver traces and judge feedback to revise them across three scientific domains. Its reported task-quality assessment uses two LLM judges. I did not verify a usable code release. [Full paper](https://arxiv.org/html/2610.05140v1).

**Review:** Directly relevant to our need for a structured specification before realization. The results are recent and domain-specific. Higher model-judged quality and lower solver accuracy are not sufficient evidence of expert validity or real-world usefulness.

**Our use:** Store both a concept (“what ability this task measures”) and a recipe (“how inputs, environment, and expected results are constructed”). Revise recipes when pilot traces reveal shortcuts, while preserving a fixed workload specification.

**Decision:** Adopt the representation as a research hypothesis; evaluate independently. Watchlist for code and external replication.

### 13. VerifierBench — audit generated scoring code

**Evidence:** 19 October 2026 preprint with 222 tasks and 4,993 test cases. It tests acceptance of valid alternatives as well as rejection of errors and attacks. Its audit includes replay, repeatability, and mutation testing. Authors report frequent false rejection by generated verifiers. [Paper](https://arxiv.org/html/2610.28679v1), [dataset](https://huggingface.co/datasets/Catherine1213/VerifierBench).

**Review:** Especially important for this project: executable scoring is only useful if the code implements the intended requirements. A verifier that rejects everything can appear strong when tested mostly on incorrect solutions. This is very recent evidence, so reported aggregate results need reproduction.

**Our use:** For every generated verifier, test a reference solution, valid alternative solutions, ordinary failures, boundary cases, and attempts to satisfy checks without completing the task. Record false acceptance and false rejection separately. Keep hidden audit examples outside the scorer author's development context.

**Decision:** Mandatory design influence. Prototype an audit gate before scaling generation.

### 14. ToolSandbox — state dependencies and missing information

**Evidence:** Apple’s 2024 research and public framework. It provides stateful tools, a user simulator, and intermediate/final milestone evaluation. The paper explicitly examines state dependencies, canonicalization, and insufficient information. [Paper](https://arxiv.org/abs/2408.04682), [repository](https://github.com/apple-aiml-research/ToolSandbox).

**Review:** Useful for tasks where success depends on asking a question or satisfying a prerequisite. Milestone-based scoring can become too prescriptive if valid alternative trajectories are excluded.

**Our use:** Generate paired cases: enough information to act, information that requires clarification, and a genuinely unavailable prerequisite. Score necessary dependencies or prohibited actions only where the workload requires them; otherwise allow different execution paths.

**Decision:** Adopt its scenario taxonomy and state-dependency ideas. Use it as a challenge set, not our entire workload distribution.

### 15. TraceDance — turn deployment failures into targeted tests

**Evidence:** September 2026 preprint. It constructs behavior-specific benchmarks from deployment traces and evaluates next-turn continuations at selected decision points without environment replay. Authors report 107 benchmarks and 4,125 instances; both human annotators confirmed the requested behavior in 84% of sampled instances. [Paper](https://arxiv.org/abs/2609.33295).

**Review:** A promising way to refresh tasks from observed problems. The unit of evaluation is a decision-point continuation, so it cannot substitute for demonstrating full workflow completion. The human confirmation result also shows that automated selection remains imperfect.

**Our use:** After collecting consented, appropriately handled user traces, mine clarification failures, premature completion claims, and bad tool choices. Convert selected cases into diagnostic tests; reconstruct the environment separately when an end-to-end task is required.

**Decision:** Phase-two feedback loop. It does not solve initial generation when no deployment traces exist.

### 16. Bloom — behavioral scenario generation

**Evidence:** Anthropic’s December 2025 open-source release. Bloom turns behavior descriptions into evaluations through understanding, ideation, rollout, and judgment, with seed configuration and configurable models. [Official release](https://www.anthropic.com/research/bloom), [technical discussion](https://alignment.anthropic.com/2025/bloom-auto-evals/).

**Review:** Useful for behavioral qualities that final-state assertions miss, such as whether an agent truthfully reports completion. Simulated tool responses and model judges introduce additional validity questions. Behavioral elicitation frequency is not the same quantity as ordinary workload success.

**Our use:** Generate supplemental scenarios around specific failure modes discovered in our tasks. Validate judges against human annotations and keep behavior scores separate from task-completion scores.

**Decision:** Optional behavioral extension, after the main executable benchmark works.

### 17. Ragas and DeepEval Synthesizer — practical document-grounded generation

**Evidence:** Ragas documents knowledge-graph transformations and scenario/query generation from documents. DeepEval supports generating evaluation “goldens” from documents, contexts, existing examples, or scratch; current documentation also describes conversational goldens and a separate conversation simulator. [Ragas concepts](https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/), [Ragas API](https://docs.ragas.io/en/stable/references/generate/), [DeepEval documentation](https://deepeval.com/docs/golden-synthesizer).

**Review:** Accessible components for retrieval and document-answering tasks. Generated expected answers still need checking. Neither cited generation interface alone establishes a complete, validated stateful task environment. Some Ragas conceptual documentation is older than its API reference; pin the implementation version.

**Our use:** Use one of these for the document/RAG branch: ingest user knowledge sources, generate grounded queries, retain supporting passages, and audit answerability. Compare a small sample from each before selecting a dependency.

**Decision:** Integrate only for relevant task types. Do not force every workflow into a question-and-answer format.

### 18. Inspect, Harbor, and Prime Intellect Verifiers — execution infrastructure

**Evidence:** Inspect separates datasets, solvers, and scorers, with sandboxes, repeated epochs, metadata, and named model roles. Harbor packages instructions, environments, tests, and optional solutions; its current task documentation includes separate verifier environments. Prime Intellect Verifiers supports environments for evaluation and training. [Inspect tasks](https://inspect.aisi.org.uk/tasks.html), [Inspect scoring](https://inspect.aisi.org.uk/scoring.html), [Harbor current format](https://github.com/harbor-framework/harbor/blob/main/docs/content/docs/tasks/index.mdx), [Verifiers](https://github.com/PrimeIntellect-ai/verifiers).

**Review:** These run and score tasks; they do not establish that generated tasks represent user needs. They are alternative foundations with different strengths, not three dependencies we must adopt simultaneously.

**Our use:** Prefer Inspect for an evaluation-first prototype with custom solvers and scoring. Prefer Harbor if containerized terminal/file tasks dominate. Consider Verifiers when reusing AutomationBench or when training integration becomes a near-term requirement. Place our task schema above the chosen backend.

**Decision:** Select one primary runner through a small compatibility experiment. Keep hidden solutions and graders outside solver access.

### 19. ThinkingBox — MCP-based stateful environments

**Evidence:** Microsoft’s August 2026 article describes 507 tasks across five business domains and final-state assertions. The runtime repository supports mocked MCP tools, isolated environments, and simulated users. Its README says it targets Linux. The separate linked data repository returned a 404 during this review. [Official article](https://commandline.microsoft.com/thinkingbox-bench-agent-benchmarking/), [runtime](https://github.com/microsoft/thinkingbox), [data link with access failure](https://github.com/microsoft/thinkingbox-data).

**Review:** Architecturally relevant if the user's tools arrive as MCP servers. The runtime can be inspected, but I cannot currently treat the reported full dataset as a verified downloadable dependency. A simulated server must also preserve the real tool's relevant behavior.

**Our use:** Inspect the isolation and tool-proxy design. Build a small mock for one real workflow and compare its behavior with recorded tool fixtures.

**Decision:** Conditional candidate; resolve data access and reproduce a scenario before choosing it as the foundation.

### 20. LiveBench — benchmark refresh as an operational practice

**Evidence:** LiveBench describes regularly renewed questions, objective answers, and delayed release to reduce contamination. The older project page lists January 2026 as latest, while the current v1 site points to a June v1 release and an October 14, 2026 LiveBench 2.0 release. The new landing page required JavaScript, so I did not verify the new generation methodology. [Older methodology](https://livebench.github.io/), [current release navigation](https://livebench.ai/v1/).

**Review:** Useful for lifecycle design, but the “contamination-free” label should not become an unconditional claim about our own benchmark. A fresh release date cannot establish what proprietary models have seen, and refreshing content changes the measurement instrument.

**Our use:** Maintain a frozen comparison cohort plus a rotating private cohort. Record when tasks were created, exposed, and retired. Compare models on the same release, and retain anchor tasks for understanding drift.

**Decision:** Adopt the refresh discipline; do not adopt an unverified zero-contamination claim.

## Dataset selection

Public datasets should initially test our infrastructure and inspire task families. They should not be relabeled as private, contamination-resistant evaluations.

| Resource | Appropriate role | Main boundary |
|---|---|---|
| SOP-Bench | Procedure-to-task examples and branching patterns | Expert SOPs must be adapted to the actual user |
| TaskBench | Dependency graphs and instruction-generation examples | Plan correctness does not prove execution |
| τ-bench | Interactive policy/tool scenarios and compositional generation | Version-dependent tasks, simulator, and scoring |
| AppWorld | Multi-app task worlds and generator implementation | App coverage and component-specific reuse conditions |
| AutomationBench | Business workflow instances and final-state assertions | Public/private scores differ; audit imported cases |
| WorkArena++ | Browser workflows and controlled compositions | ServiceNow access and UI execution overhead |
| AgentSynth | Executed computer-use trajectories and composite tasks | Generator capability bias and environment replay |
| ToolSandbox | Prerequisites, clarification, and state-dependency cases | Scenario coverage is narrower than general workloads |
| VerifierBench | Tests for our verifier-generation subsystem | Audits scorer behavior, not workload relevance |
| TraceDance | Decision-point diagnostics from traces | No end-to-end environment replay |
| ThinkingBox-Bench | Potential MCP business-task dataset | Full data access not verified |

## Proposed methodology for our system

The following is my design synthesis, not a method already validated by one of the papers.

### A. Establish a workload contract

Convert the user's description into:

- Desired outcomes and example requests.
- Tool schemas, relevant data structures, and permitted operations.
- Business rules, exceptions, and priorities.
- Whether clarification, abstention, or escalation is acceptable.
- Estimated frequencies of workflow types, with uncertainty.
- Observable evidence of success and unacceptable side effects.

Ask targeted questions when missing information changes what counts as correct. Do not silently invent a refund policy, escalation threshold, or available tool. Preserve inferred assumptions for user validation.

A broad description can justify candidate task families. It cannot by itself justify precise claims about the user's true workload distribution.

### B. Create a structured task specification

A proposed minimal schema:

```yaml
task_id: support_refund_0042
family_id: refund_with_duplicate_order
spec_version: 1
source_refs: [workload_brief_v1, refund_policy_v3]
goal: Resolve the eligible refund request and record the outcome
interaction_mode: clarification_allowed
tool_schema_version: support_mock_v2
environment_snapshot: snapshot_0042
seed: 42
preconditions: [customer_exists, payment_settled]
required_outcomes: [eligible_order_refunded_once, ticket_updated]
forbidden_effects: [other_order_changed, duplicate_refund]
unknowns: [order_identifier_to_elicit]
reference_solution: private/solution_0042
verifier: private/verifier_0042
audit_suite: private/audit_0042
split_group: refund_policy_branch_b
difficulty_factors: [ambiguous_identifier, cross_tool_dependency]
generation_provenance: private/generation_manifest_0042
```

This is an illustrative schema, not an implementation API from the reviewed frameworks. References to private artifacts are evaluator metadata and must not be exposed to the solver. Open-ended writing tasks need a rubric and evidence package instead of pretending every outcome is a deterministic state predicate.

### C. Use three generation routes

| Route | Best fit | Construction |
|---|---|---|
| Procedure/graph-driven | Structured business workflows | Instantiate validated branches and compose executable primitives |
| Document-grounded | Search, RAG, analysis | Select evidence first, then generate answerable questions and verify answers |
| Execution/trace-grounded | Complex tool or computer workflows | Reconstruct an executable scenario from a validated trajectory |

Mixing these routes is a proposed design, not a reason to adopt every framework above.

### D. Validate feasibility and the scorer independently

Before admitting an ordinary solvable task:

1. Validate schema, tool availability, data references, and preconditions.
2. Execute a reference solution from a clean state through the tools the solver will actually receive.
3. Verify success and repeat the run to detect uncontrolled randomness or state leakage.
4. Exercise valid alternative solutions so the scorer does not enforce incidental choices.
5. Mutate outputs or states to test incomplete work, wrong targets, duplicate actions, and collateral changes.
6. Try shortcuts against the scorer and ensure it cannot be modified or read by the solver.
7. Audit the language instruction against the executable contract.
8. Sample accepted and rejected tasks for independent human review.

For tasks intentionally requiring abstention or clarification, validate that behavior as the correct outcome. “No evaluated model solved it” is not proof of invalidity. Conversely, a hidden solution using unavailable information is not evidence of solver-facing feasibility.

### E. Measure coverage and difficulty separately

Cover workflow types, policy branches, tool combinations, information gaps, input sizes, and failure consequences. Difficulty should be measured from solver outcomes and task structure, not only assigned by the generator.

Maintain two separately reported suites:

- **Representative suite:** approximates normal user work, retaining easy but frequent tasks.
- **Challenge suite:** stresses exceptions, ambiguity, longer dependencies, and robustness.

Do not increase the headline difficulty by silently replacing ordinary tasks with adversarial ones.

### F. Design for contamination resistance

Define separate threats and controls:

| Threat | Proposed control | Remaining limitation |
|---|---|---|
| Public benchmark memorization | Fresh private instances and private source material | Familiar templates and procedures may still be known |
| Near-duplicates across splits | Group by procedure, source, template, and composition; deduplicate text and structure | Semantic equivalence is imperfect to detect |
| Generator/solver coupling | Track generator identity and use crossed generator–solver experiments | Different models can share training and biases |
| Answer leakage during execution | Separate grader environment; restrict filesystem/network access to answers | Isolation must be tested |
| Exposure through tuning | Separate development, agent-selection, and sealed final-test sets | Repeated test inspection makes the set development data |
| Provider exposure | Track API calls and data handling arrangements for private tasks | Proprietary training provenance may remain unknown |
| Benchmark staleness | Versioned refreshes with frozen comparison cohorts | New cohorts measure a changed task distribution |

Synthetic generation, private seeds, and model diversity are useful controls. None independently proves absence of contamination.

### G. Preserve fairness for multi-model agents

Generate tasks independently of the architecture we hope will win. Give single-model and multi-model systems the same task information and relevant tool permissions. Charge communication, planning, critique, retries, and model switching to the team's budget.

Include at least a strong single-model agent, a single-model agent allowed extra inference, and multi-model configurations under matched resource budgets. Record task-level outcomes and cost/latency distributions. A task dependency graph can later inform routing, but do not force every solver into that graph.

Keep benchmark construction, model selection, and final agent testing as separate stages. Otherwise, the system may demonstrate adaptation to its own benchmark rather than usefulness on new work.

## Proposed first experiment

Start with one domain containing explicit procedures and observable outcomes, such as support-ticket resolution across a small CRM, inbox, and ticketing environment. This is a proposed tractable research setting, not an assumption about the user's eventual domain.

Compare four generation systems against the same workload briefs:

| Condition | What it tests |
|---|---|
| A: Direct LLM generation | Baseline quality and cost |
| B: Structured specification plus review | Value of separating planning from generation |
| C: Executable primitives plus reference replay | Value of environment-grounded construction |
| D: C plus independent verifier audits and controlled composition | Value of the full robustness process |

Use the same workload requirements and comparable generation budgets. Report both quality per attempted task and cost per accepted task; a system that rejects most candidates should not hide that cost.

For an initial engineering pilot, target approximately 50 accepted instances spanning 8–12 task families, with a smaller expert-authored comparison set. These numbers are proposed for debugging and feasibility, not a statistically powered final model-ranking study. Size the later study using observed variance and the minimum performance difference we care about.

Measure:

- Workload relevance and rule fidelity under blind human review.
- Valid-task yield and rejection reasons.
- Reference replay success and reproducibility.
- Verifier false acceptance and false rejection on independent audits.
- Workflow/branch coverage and structural duplicate rate.
- Generation cost, repair cost, and human review time.
- Stability across generator models and seeds.
- Whether synthetic-task performance predicts performance on independently authored workload tasks.

For correlated task variants, compute uncertainty at the task-family level rather than counting every paraphrase as an independent example. Determine acceptance thresholds before comparing systems. Independent expert review and grader audit are required to evaluate the generator; its own confidence score is insufficient.

## Integration order and unresolved questions

1. Define the workload contract and task schema.
2. Implement one resettable environment with a few validated task primitives.
3. Compare direct prompting with a structured BenchAgents/Benchmark Agent-inspired pipeline.
4. Add reference replay and a VerifierBench-inspired audit gate.
5. Generate private variants and split by task family.
6. Evaluate single-model baselines before optimizing multi-model routing.
7. Add document-grounded and deployment-trace generation when the workload requires them.

Outstanding evidence gaps: no frameworks were executed in this review; no cross-project compatibility was tested; complete component/data licenses were not audited; newer preprints were not independently replicated; ThinkingBox's full data repository was inaccessible; AutoSciBench code availability was not established. These affect dependency selection, not the value of the documented design ideas.

The next concrete research artifact should be a **task-generation specification and evaluation protocol** that selects one pilot workload, defines its success semantics, and commits to the generator comparisons above.

