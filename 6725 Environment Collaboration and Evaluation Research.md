# 6725 Environment, Collaboration, and Evaluation Research

Research checked: **26 October 2026**  
Project: [[6725 Knowledge Hub]]  
Builds on: [[6725 Task Generation Research Review]]  
Status: research and proposed plan; no installation, deployment, paid model calls, or experiments performed.

## Decision summary

**Recommendation:** Start with a small, resettable, API-based business environment, independently graded from its actual state, and use **Inspect as the initial evaluation harness**. Compare an AppWorld-based implementation with a minimal custom environment before committing. Use AutomationBench for business-workflow references and τ-bench for interaction and reliability methods. Evaluate two- and three-model teams against strong single-model systems under comparable resource budgets.

This extends the completed task-generation review. The generated evaluation package remains the central artifact: instruction, initial state, available tools, expected outcomes, verifier, audit cases, and provenance. This review addresses where that package runs, how teams act within it, and what evidence makes its scores trustworthy.

The $200 AWS credit is enough to justify a **bounded feasibility pilot**, subject to credit eligibility and measured inference costs. It is not yet a defensible budget for a statistically conclusive study. Spend first on validating the environment and grader, then on independent task families and repeated trials. Avoid committing to a GPU deployment or several orchestration frameworks before measuring the workload.

These are recommendations, not approved architecture decisions. The pilot workload and actual tool surface remain unselected.

## Evidence standard and coverage

This is a targeted technical review, not a systematic review or independent replication. Searches covered environments, isolation, contamination prevention and detection, collaboration, reliability, evaluation methodology, and cloud products. Evidence comes from primary papers, selected full-text methods and limitations, official repositories, and official documentation/pricing pages. Search summaries were used for discovery; secondary commentary and leaderboard aggregators were not used to establish technical conclusions.

Labels used below:

- **Research:** paper-supported methods or author-reported results; publication or preprint status is specified where verified.
- **Documentation:** a capability described by maintainers, not tested here.
- **Assessment:** our interpretation of applicability and limitations.
- **Recommendation:** a proposed choice or experiment, requiring validation.

“Current” means retrieved on the date above. Moving repository branches and pricing pages are not reproducibility pins. Before implementation, record commits, package locks, image digests, model versions, region, and pricing date. The latest retrieved revisions are used where checked; older publicity can describe materially different studies.

## 1. Choose the environment independently of the agent framework

Four layers must remain distinct:

| Layer | Purpose | Initial candidate |
|---|---|---|
| Task world | Implements records, policies, tools, time, and state transitions | AppWorld extension or minimal custom API environment |
| Isolation and hosting | Runs the world and contains solver execution | Local Docker for development; disposable AWS Linux worker for pilot |
| Evaluation harness | Schedules trials, invokes solvers, records traces, aggregates scores | Inspect |
| Solver orchestration | Controls which model acts, communicates, or delegates | Explicit Inspect workflows initially; LangGraph if additional durable control is needed |

MCP is a tool interface, not proof of faithful simulation or isolation. A cloud sandbox supplies compute and containment, not a realistic workload or a correct grader. An orchestration framework supplies control flow, not evidence that collaboration improves outcomes.

### 1.1 AppWorld: strongest initial reference for executable task packages

**Documentation:** Its generator guide defines setup, a validation solution using available APIs, and evaluation tests comparing initial and final database states. It explicitly checks expected changes and the absence of unexpected changes. [Generator guide](https://github.com/StonyBrookNLP/appworld/blob/main/guides/developing_new_task_generators.md).

**Assessment:** This closely matches our existing schema and makes it a useful candidate for reusable task construction. Its app universe may not fit the eventual workload; adding faithful business semantics can be more work than writing a small environment.

**Recommendation:** Implement the same two or three development tasks in AppWorld and a minimal custom backend. Compare reset reliability, verifier independence, adapter effort, reference replay, and state inspection. Select AppWorld only if reuse actually reduces work without distorting the workload.

**Reuse boundary:** AppWorld distributes sensitive benchmark components in encrypted bundles, adds redistribution conditions, and includes a canary for filtering. These reduce accidental exposure; they do not establish that no model trained on the material. Inspect the relevant component license before redistribution. [Official README](https://github.com/StonyBrookNLP/appworld/blob/main/README.md).

### 1.2 AutomationBench: business workflow fit, with task-level quality checks

**Documentation:** The public repository provides a 600-task business benchmark spanning six domains. Its stateful business workflows make it relevant to work across several applications. [Repository](https://github.com/zapier/AutomationBench), [paper](https://arxiv.org/abs/2604.18934).

**Assessment:** Strong source of realistic workflow categories. It should not become an unquestioned source of ground truth. The previous review's contributor-reported quality concerns remain unresolved by this review; no individual imported task has been reproduced here.

**Recommendation:** Borrow workflow patterns and evaluate a small audited subset as a harness check. Keep public benchmark scores separate from scores on newly authored private tasks. Importing its environment may favor its native runner; measure that integration cost before wrapping everything in Inspect.

### 1.3 τ-bench: user interaction and policy-sensitive tasks

**Documentation:** The current repository calls its release τ-bench 2.0, adds multilingual/voice evaluation, and explicitly warns that English 2.0 results are not comparable with v1.x. Changes include task replacements, prompts, simulator behavior, and judges. [Current repository and version notes](https://github.com/sierra-research/tau2-bench).

**Assessment:** A good reference when clarification and policy adherence matter. A simulated user is an additional experimental component whose behavior can alter difficulty. Dual control refers to agent and user acting in the environment; it does not establish a benchmark for collaborating solver models.

**Recommendation:** Start with text-only interaction. Use scripted replies for controlled cases and a pinned simulated user for a separate realism condition. Keep simulator configuration common across solver conditions, and audit what information it discloses.

### 1.4 ThinkingBox: attractive MCP architecture, unresolved dataset access

**Research:** The October 1 revision describes isolated MCP-compatible sessions, terminal-state evaluation, and 507 policy-conditioned workflows. It emphasizes reliable completion across repeated attempts and checking collateral effects. [Paper v4](https://arxiv.org/abs/2608.19741v4).

**Access limitation:** The linked [data repository](https://github.com/microsoft/thinkingbox-data) again returned 404 during this review, while the [runtime repository](https://github.com/microsoft/thinkingbox) was discoverable. This does not establish why access failed.

**Recommendation:** Keep it as a conditional candidate for MCP-heavy workloads, not a committed dataset dependency. Reproduce a runtime scenario and resolve data availability before investing in an adapter.

### 1.5 BrowserGym and OSWorld 2.0: use when the interface is part of the work

**Documentation:** BrowserGym unifies browser-task environments and benchmark integration. It is a more relevant starting point than a general API simulator when UI navigation is itself a required capability. [Repository](https://github.com/ServiceNow/BrowserGym).

**Research:** OSWorld 2.0, released in June 2026, describes 108 long-horizon computer-use workflows with a median human completion time around 1.6 hours. Its evaluation includes binary completion and partial scores. [Paper](https://arxiv.org/abs/2606.29537), [official release navigation](https://os-world.github.io/).

**Assessment:** These expose interface, timing, rendering, and desktop-state failures an API benchmark misses. They also make environment setup, task replay, and repeated evaluation more expensive. Difficulty does not by itself make a benchmark representative.

**Recommendation:** Defer the desktop branch unless the selected workload requires GUI-only applications. For browser tasks, prefer resettable self-hosted applications before live public websites. Record browser/OS versions, screenshots, action traces, and reset checks. Do not claim API success predicts GUI success.

### 1.6 Inspect versus Harbor

**Documentation:** Inspect supports custom solvers and scorers, repeated evaluations, sandbox providers, and multi-agent workflows, handoffs, and agents exposed as tools. Its multi-agent documentation explicitly recommends establishing a simple agent baseline. [Multi-agent guide](https://inspect.aisi.org.uk/multi-agent.html), [scoring guide](https://inspect.aisi.org.uk/scoring.html).

**Recommendation:** Inspect is the first choice for our controlled comparison because evaluation is the immediate goal. Keep the task schema independent of it so the environment can be tested with another runner later.

**Documentation:** Harbor packages executable tasks and supports separate verifier environments and configurable network policies. [Task format](https://github.com/harbor-framework/harbor/blob/main/docs/content/docs/tasks/index.mdx).

**Recommendation:** Prefer Harbor if terminal, repository, or file-artifact tasks dominate. Do not add both harnesses to the first pilot. Separate verification is a capability to configure and test, not an automatic guarantee that every task hides its grader correctly.

### 1.7 Isolation details that materially affect validity

**Documentation:** Inspect's default generated Docker configuration disables networking, but a custom Compose file replaces that configuration. Container network restrictions do not restrict tools executing in the host evaluation process or a provider's search capability. [Sandboxing documentation](https://inspect.aisi.org.uk/sandboxing.html).

**Documentation:** AISI distinguishes tool permissions, host isolation, and network isolation. Ordinary containers share the host kernel; VMs provide a different boundary. Its guidance recommends matching containment to the task rather than assuming one configuration covers all evaluations. [Sandboxing playbook](https://engineering-playbook.aisi.org.uk/isolate.html).

**Recommendation:** For the API pilot, let the solver request only typed application operations through a gateway. Keep model credentials, hidden checks, and reference solutions outside that application container. Give every trial a fresh database and scoped tool credentials. For unrestricted code execution, evaluate stronger isolation separately. Test isolation from both the solver container and host-side tools.

## 2. Contamination resistance requires several separate controls

No reviewed method proves universal elimination of contamination, particularly for proprietary models with unknown training data. The defensible goal is **documented resistance to specified exposure and leakage threats**, with residual uncertainty stated.

### 2.1 What established and recent methods actually offer

| Method and evidence | Useful contribution | Boundary for our project |
|---|---|---|
| LiveCodeBench: timestamped contest problems, evaluated after a model cutoff | Temporal separation and release tracking | Cutoffs may be uncertain; later model updates or live retrieval can expose the problem. The overview still contains old dataset counts, so use it for method, not current size. [Official methodology](https://livecodebench.github.io/) |
| LiveBench: refreshed evaluation cohorts | Operational discipline for renewing tasks | The current 2.0 landing page still requires JavaScript in this retrieval; its new methodology was not verified. Preserve the earlier review's caveat. [Current site](https://livebench.ai/), [v1 navigation](https://livebench.ai/v1/) |
| AppWorld: encrypted public bundles and filtering canary | Reduces accidental ingestion and signals material to exclude | Publicly obtainable content remains exposable; canaries depend on downstream cooperation. [Release policy](https://github.com/StonyBrookNLP/appworld/blob/main/README.md) |
| SWE-Bench Pro: private commercial code alongside public tasks | Private provenance is stronger than merely rewriting a public question | The creator's argument that copyleft code is less likely to be trained on is not evidence of exclusion. Public and private task difficulty also differs. [Original release](https://scale.com/blog/swe-bench-pro) |
| ConStat, NeurIPS 2024 | Compares benchmark performance with reference benchmarks/models to flag anomalous inflation | A statistical flag is not proof of exact training membership; a negative result is not a clean bill of health. [Published paper](https://proceedings.nips.cc/paper_files/paper/2024/file/a7f89793b9e6f8c6568dbbb6ff727b9b-Paper-Conference.pdf) |

**Recent evidence against overconfidence:** *The Reliability Gap in Benchmark Auditing* (July 2026 revision; arXiv records ECML PKDD acceptance) tests three detection paradigms and finds problems under distribution shift and limited sample sizes. Its closed-model comparisons lack known membership ground truth, and its open-model scope is bounded. **Use:** provenance and preventive controls first; detection as supplementary evidence. [Paper and limitations](https://arxiv.org/html/2606.03305v2).

**Search-time contamination:** A June 2026 preprint distinguishes retrieved benchmark metadata, question context, and explicit answers. **Use:** log retrieval and control accessible sources. Blocking a few benchmark domains is weaker than a known permitted corpus, because mirrors and copied answers may remain accessible. A controlled corpus changes the task, so report open-web and controlled-corpus conditions separately. [Paper](https://arxiv.org/abs/2606.05241).

### 2.2 Two recent papers that change the evaluation design

**SWE-Bench Pro V2, October 16, 2026 preprint.** The authors report repairing or retiring 480 of 731 original public tasks using agentic audits, expert review, and blind reimplementation. Their protocol restricts network access and grades submitted patches in a clean container. The paper explicitly says this stops test-time retrieval, not training-time memorization; forgery inside an allowed patch still requires auditing. **Use:** independently solve instructions without seeing the reference; grade only declared outputs against a fresh trusted environment. Do not interpret a higher corrected score as a weaker benchmark. [Full paper](https://arxiv.org/html/2610.24206v1).

**Scalable Weak-to-Strong Verifier Hardening, October 11, 2026 preprint.** It separates the verifier environment and iterates attack, repair, and validation. Validation includes replay of legitimate solutions and a fresh blind solve. The paper acknowledges remaining attacks and finite coverage; its text describes an intended code release, and the project page was inaccessible through this tool. **Use:** a bounded audit loop with held-out attacks, preserving valid alternatives. Do not claim a reusable implementation was verified or that a stopped attack search proves security. [Full paper](https://arxiv.org/html/2610.15924v1).

These complement **VerifierBench** from the existing review: check both false acceptance of invalid work and false rejection of valid work. A grader that blocks every output is unusable even if every attack fails. [VerifierBench](https://arxiv.org/html/2610.28679v1).

### 2.3 Proposed contamination and leakage protocol

The following is our synthesis, not a validated package supplied by one paper.

| Threat | Control | Evidence to retain |
|---|---|---|
| Training exposure | Newly authored private source material and task instances; known model snapshots where possible | Source lineage, creation date, model identifier, exposure history |
| Derivative/template overlap | Split by procedure, document lineage, task family, and composition; inspect structural and semantic near-duplicates | Family assignments, duplicate flags, reviewed borderline cases |
| Generator-specific bias | Cross generator and solver identities on a limited subset; independently authored comparison tasks | Generator identity, rejected candidates, expert-task results |
| Answer retrieval | Disable unnecessary browsing; otherwise use an explicit source policy and record every retrieval | Queries, retrieved content identifiers, timestamps, leakage flags |
| Hidden grader access | Separate process/environment and storage permissions; no reference artifacts in solver images | Access tests and artifact manifest |
| Scorer manipulation | Validate output format, regrade cleanly, audit side effects and alternate solutions | Verifier hash, audit suite, exploit replays, false-rejection cases |
| Repeated test tuning | Separate generator development, agent selection, and sealed final evaluation | Access log, frozen configuration manifest, release history |
| Provider or logging exposure | Check chosen inference service's handling terms; restrict task logs and reset cross-trial memories | Endpoint, configuration, retention policy, permitted recipients |

Do not send sealed task text to public search as a contamination check; that creates another exposure channel. Run local duplicate detection and use previously collected public comparison corpora where appropriate. If final-test feedback changes the agent or generator, that cohort becomes development data and a new final cohort is needed.

For stateful workflows, grade the authoritative server state or replay a recorded action sequence from the initial snapshot. Do not accept an agent-written JSON claim of the final database as proof of completion. Include required process constraints when specified by the workload: final state alone cannot detect every prohibited intermediate action.

AWS states that Bedrock inputs and outputs are not used to train base models or shared with model providers. This supports considering Bedrock for private evaluation, but does not establish the provenance of models' pre-existing training data or settle every logging/integration configuration. [AWS privacy statement](https://aws.amazon.com/bedrock/security-privacy-responsible-ai/).

## 3. Multiple models should collaborate through an explicit protocol

### 3.1 What the research supports

**Towards a Science of Scaling Agent Systems — April 8, 2026 v3.** The current paper studies 260 configurations across six benchmarks, rather than the 180/four described in the January blog. Benefits depend on decomposition and sequential dependencies. Cross-validated fit is moderate, and heterogeneous teams largely vary within model families; this does not validate arbitrary cross-vendor teams. Some added benchmark subsets are small. **Use:** stratify tasks by parallelizability and test architectures rather than assuming team size predicts success. [Current paper](https://arxiv.org/html/2512.08296v3).

**Single-Agent LLMs Outperform Multi-Agent Systems… — April 11, 2026 v2 preprint.** It finds single agents match or outperform teams on text-only multi-hop reasoning under matched requested thinking budgets. Limitations include approximate API token accounting and unequal realized consumption below the caps; tools and vision are out of scope. **Use:** measure actual usage and include extra-inference single-agent baselines. Do not generalize its results to all stateful tool workflows. [Paper and limitations](https://arxiv.org/html/2604.02460v2).

**MAST — October 2025 v3.** More than 1,600 annotated traces across seven frameworks motivate 14 failure modes across system design, inter-agent alignment, and verification. **Use:** classify failures such as incomplete handoffs, premature termination, and incorrect completion verification. Its model mix and task coverage do not establish present-day failure frequencies for our system. [Paper](https://arxiv.org/abs/2503.13657v3).

**Anthropic's multi-agent research system — engineering report.** It describes an orchestrator-worker design, bounded assignments, parallel search, and substantial token overhead. Its reported gains concern its research product and are not a matched-budget general superiority result. **Use:** workers return evidence and scoped outputs rather than unrestricted conversation histories; delegation has an explicit resource budget. [Engineering report](https://www.anthropic.com/engineering/multi-agent-research-system).

### 3.2 Framework shortlist

| Candidate | Documented contribution | Proposed role |
|---|---|---|
| Inspect agent protocol | Explicit workflows, handoffs, and agents-as-tools | First pilot: keeps solver and evaluation integration small. [Docs](https://inspect.aisi.org.uk/multi-agent.html) |
| LangGraph | Stateful orchestration, persistence, durable execution, deterministic and model-driven steps | Add if checkpointing and controllable graph execution justify the dependency. [Docs](https://docs.langchain.com/oss/python/langgraph/overview) |
| Microsoft Agent Framework | Python/.NET agent and multi-agent workflow framework | Candidate if its ecosystem fits; compare against the simplest implementation. [Repository](https://github.com/microsoft/agent-framework) |
| Strands | Agents-as-tools, graph, swarm, and workflow patterns | Useful AWS-aligned alternative. Current docs contain some inconsistent wording about built-in workflow support; verify exact SDK APIs. [Docs](https://strandsagents.com/docs/user-guide/sdk/multi-agent/multi-agent-patterns/) |
| CrewAI Flows | Structured state and event-driven flow control | Candidate for rapid application construction; only use in the experiment if budgets, retries, context, and traces remain fully observable. [Versioned docs](https://docs.crewai.com/v1.15.30/en/concepts/flows) |

**Currency correction:** AutoGen's current README directs new projects to Microsoft Agent Framework. It contains both archived/no-longer-maintained and maintenance-mode wording; either way it is not the preferred new-project dependency. [README](https://github.com/microsoft/autogen).

No framework above has been installed here. Feature documentation is not evidence of reliability, compatibility, or superiority. Using one orchestration implementation across the initial comparisons avoids confusing framework differences with collaboration benefits.

### 3.3 Proposed team protocols

**Two models: executor plus critic.** Model A proposes actions or completes a bounded stage; model B inspects the observed tool results, requirements, and proposed next action. B returns specific objections with evidence. A owns state-changing writes. Limit critique rounds. B has no access to the hidden evaluator or reference solution. Include A reviewing itself as a compute-control condition.

**Three models: coordinator plus two specialists.** The coordinator assigns bounded subtasks. Specialists can gather information concurrently against a common snapshot. Proposed writes return to the coordinator or a transaction service that serializes them and checks stale-state versions. This prevents duplicate or conflicting actions from silently changing task difficulty. Use shared writes only in a separate condition designed to study concurrency.

**Independent attempts plus selection.** A useful additional control when outputs can be compared, but an oracle that chooses whichever attempt passes the hidden grader is not a deployable solver. A selector must use solver-available information, and its cost counts.

Every handoff should record: trial ID, role, subgoal, available evidence, permitted tools, state version, remaining budget, expected output, and stopping condition. Keep append-only action and message logs. Context summaries must reference evidence rather than replacing it irreversibly.

Budget limits apply to the **whole team**: all prompts, repeated context, reasoning/output tokens, critique, retries, simulator calls, and selection. Report cost, elapsed time, and token consumption separately; they cannot generally be matched simultaneously across different providers. Hidden reasoning-token visibility may be incomplete, so disclose unavailable fields rather than inventing equivalence.

## 4. Measure task quality, solver performance, and benchmark integrity separately

**Research foundation:** *AI Agents That Matter* argues for cost-aware, reproducible evaluation and stronger controls against overfitting. [TMLR publication](https://openreview.net/pdf?id=Zy4uFzMviZ). *Towards a Science of AI Agent Reliability*, June 2026 v3, proposes twelve metrics across consistency, robustness, predictability, and safety, evaluated on two benchmarks. This supports a multidimensional report, not treating one aggregate reliability index as universal. [Current paper](https://arxiv.org/html/2602.16666v3).

The following metric set is our proposed operationalization. Do not describe it as an exact reproduction of either paper.

| Dimension | Proposed measurement | Interpretation |
|---|---|---|
| Task-generation validity | Accepted valid tasks / attempted candidates; rejection reasons; cost per accepted task | Exposes low yield and repair effort |
| Workload fidelity | Blind expert judgments of relevance, rule fidelity, missing information, and coverage | Generated tasks must match work, not just be executable |
| End-to-end success | All required outcomes satisfied and no forbidden effects/process violations | Primary binary endpoint |
| Partial completion | Fraction of required outcomes met, with predeclared weights if needed | Diagnostic only; cannot erase a critical violation |
| Repeatability | Mean single-run success and pass^k | Distinguishes occasional success from repeated reliability |
| Robustness | Paired success change under valid paraphrases, reordered records, distractors, and injected tool faults | Each perturbation needs a validity check |
| Harm and policy failures | Rate and severity of wrong-target edits, duplicate actions, policy breaches, and collateral changes | Report severe events separately from averages |
| Cost | Total dollars / successful completions, plus dollars per attempted run | Includes failed runs; undefined/infinite if no successes |
| Latency | Median and p95 elapsed time, timeouts, and completion within an explicit deadline | Include orchestration and tool waits; document queue policy |
| Calibration and escalation | Brier score on declared success probabilities; risk–coverage curve for abstention | Confidence must be recorded before evaluator feedback |
| Team contribution | Paired improvement over best eligible single baseline at the same budget; communication share; conflicting writes | Separates collaboration from extra spending |
| Grader validity | False acceptance and false rejection on independently labeled audit cases | Includes legitimate alternative solutions |
| Environment quality | Reset/replay success, infrastructure failures, snapshot consistency | Measures the testing system, not model skill |
| Generalization | Difference between development and sealed families; transfer to independently authored tasks | Measures dependence on our generator and templates |

### Repeated-success metrics

The original τ-bench introduces **pass^k**, meaning all k attempts succeed, unlike **pass@k**, meaning at least one succeeds. [Paper](https://arxiv.org/abs/2406.12045). Inspect provides distinct reducers for these quantities. [Metrics documentation](https://inspect.aisi.org.uk/metrics.html).

For a task with c successes in n independent, identically configured attempts, estimate:

```text
single-run success = c / n
pass@k = 1 - choose(n-c, k) / choose(n, k)
pass^k = choose(c, k) / choose(n, k)       for k <= n
```

Use the usual zero convention when there are too few successes or failures for a combination. Aggregate at task level with predeclared weights. Do not take the overall mean success rate to the kth power: tasks differ in difficulty. Reset state, sessions, and memories between repeats. Provider changes or shared mutable state undermine the identical-trial assumption.

For the pilot, three repeats provide pass^3 and variability diagnostics; they do not justify a pass^20 claim. Retrying until success is a separate deployment policy, with all retry costs and side effects counted.

### Uncertainty, failures, and scorer governance

Use paired comparisons on the same tasks. Resample at the task-family level for intervals because variants share structure; preserve pairing and repeated trials inside each sampled family. With only 8–12 families, intervals and generalization estimates remain fragile. Add independent families before merely producing hundreds of paraphrases.

Predeclare primary outcomes and comparisons before seeing final results. Report per-family results and overall intervals. For many exploratory configurations, clearly separate selection results from confirmation on sealed tasks. Choose final sample size using pilot variance, paired differences, the minimum worthwhile effect, and cost.

Timeouts or solver-caused failures count as agent failures. Confirmed infrastructure faults should be labeled and handled under a fixed retry policy, with all affected counts retained. Inspect can exclude unscored values from metrics, so headline accuracy alone can conceal missing coverage. Publish planned, attempted, scored, failed, invalidated, and unscored counts. [Scoring policy](https://inspect.aisi.org.uk/scoring-policy.html).

For subjective artifacts, use a rubric, evidence, blind human calibration, judge disagreement analysis, and fixed judge versions. Executable state checks should remain primary where they capture the requirement. An agent's own completion statement is not ground truth.

METR's time horizons measure human task duration associated with a predicted success level, not how long an AI runs autonomously. Its current page says it is no longer actively updated and was last updated September 8, 2026. **Use:** later add human-time difficulty strata if we can collect defensible human timings; do not fit a headline horizon to a tiny pilot. [Methodology](https://metr.org/time-horizons/).

## 5. Hosting products and the $200 AWS budget

The cost comparisons below are planning inputs, not deployment quotes. They exclude model inference unless explicitly stated. Billing units, resource guarantees, cold starts, and operating-system support differ, so equal nominal CPU/RAM does not establish equal performance.

| Option | Verified pricing/features relevant to this decision | Assessment |
|---|---|---|
| AWS EC2 with Docker | General-purpose Linux instances provide a conventional host; exact regional rate must be quoted before deployment. [AWS T3 page](https://aws.amazon.com/ec2/instance-types/t3/) | First pilot candidate for custom multi-service environments and existing AWS credit. Use short-lived workers; burstable CPU behavior needs measurement. |
| Bedrock AgentCore | Published runtime microVM v1 rates: $0.0895/vCPU-hour and $0.00945/GB-hour. v2 consumption: $0.1276/vCPU-hour and $0.0169/GB-hour. CPU treatment during I/O wait differs from provisioned-server billing. [Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/) | Consider after testing custom environment/reset needs. AgentCore runtime is not itself a benchmark world. Do not use old v1 estimates for v2. |
| E2B | Default 2-vCPU CPU cost $0.000028/s plus 4-GiB memory $0.000018/s = $0.1656/hour. Hobby lists one-hour sessions and 20 concurrent sandboxes; Pro $150/month plus usage. [Pricing](https://e2b.dev/pricing) | Good managed alternative for short code runs. The Pro base fee is large relative to this pilot. Promotional credits are not assumed available to this user. |
| Daytona | $0.0504/vCPU-hour plus $0.0162/GiB-hour: 2 vCPU and 4 GiB totals $0.1656/hour, before applicable storage and other charges. [Pricing](https://www.daytona.io/pricing) | Candidate for disposable workspaces; test image compatibility, reset, networking, and quotas. |
| Modal | Sandbox page lists non-preemptible CPU at $0.00003942/physical-core-second and memory at $0.00000667/GiB-second; a physical core is described as 2-vCPU equivalent. One core plus 4 GiB is approximately $0.238/hour. [Pricing](https://modal.com/pricing) | Useful scale-out candidate. Use sandbox rates, not cheaper generic compute rates; confirm resource semantics. |

The AgentCore page also lists planned/committed pricing language tied to October 2026; availability of those options was not independently established. Use the explicit consumption rates for provisional comparisons.

**Credit caveat:** AWS Activate explicitly supports third-party Bedrock models, but the user's credit program is unknown. AWS promotional-credit terms contain exclusions, including Marketplace unless authorized. Check the actual credit's eligible services and expiration before allocating inference spend. Direct external API bills are separate from AWS credit; Marketplace availability does not establish promotional-credit eligibility. [Activate announcement](https://aws.amazon.com/blogs/startups/aws-activate-credits-now-accepted-for-third-party-models-on-amazon-bedrock/), [credit terms](https://aws.amazon.com/awscredits/).

### Proposed allocation, conditional on eligibility

| Category | Initial cap | Purpose |
|---|---:|---|
| Environment compute | $35 | Short-lived CPU workers and reset/replay checks |
| Storage, logs, and networking | $15 | Images, snapshots, traces; avoid unnecessary always-on services |
| Task generation and grader audits | $40 | Candidate construction, repairs, independent checks |
| Solver/model and simulator calls | $80 | Controlled comparison runs |
| Reserve | $30 | Failed runs and measured overruns |
| Total | **$200** | Engineering feasibility, not final statistical claims |

These allocations are proposed caps, not measured forecasts. Human review labor is additional unless supplied by the project team. Use an application-side trial budget and concurrency limit, plus cloud alerts and automatic worker shutdown; a billing alert is not a guaranteed hard spending stop.

A useful cost model is:

```text
total = task_generation + verifier_audits + human_review
      + sum_over_all_calls(input_tokens * input_rate
                           + output_or_reasoning_tokens * applicable_rate
                           + other_provider_charges)
      + simulator_calls + sandbox_compute + storage + network + logs
```

Avoid double-counting reasoning tokens if a provider already includes them in billed output. Track cache discounts and actual invoices/usage, and report both the measured price and assumptions for future runs.

For scale: 50 tasks × 6 solver configurations × 3 repetitions = **900 trials**. At an illustrative measured all-model-call cost of $0.10, $0.50, or $2.00 per trial, inference alone would be $90, $450, or $1,800. These are sensitivity scenarios, not current model-price quotes. This is why we must measure a small sample before promising the full matrix within $200.

**When to spend more:** once task validity, reset reliability, and logging pass their gates, a $500–$1,500 incremental envelope could fund more independent task families, repeat runs, and expert audits. It is a proposed envelope, not a guarantee of sufficient sample size. Recalculate from measured cost and power; a high-cost long-horizon study may exceed it. Prioritize audit quality and broader independent coverage over a larger model roster.

## 6. Suggested staged plan

### Stage 1: define the workload and acceptance contract

Select one workload with observable outcomes and explicit rules. Support-ticket operations across a small CRM, inbox, and ticket store remains an example, not a user-selected domain. Include sequential tasks, tasks with genuinely independent subtasks, and clarification cases in proportions motivated by the workload.

Deliver: workload contract; task schema from the prior review; a list of mandatory outcome/process constraints; contamination threat model; error-severity categories; and a record of assumptions needing confirmation.

**Gate:** every required business rule has a source; no invented rule silently becomes ground truth. User/domain review establishes whether the environment represents the intended work.

### Stage 2: select and validate one execution stack

Use 5–10 development tasks for engineering, not ranking. Compare AppWorld reuse with a minimal API environment using the same task semantics. Start with Inspect; use Harbor instead if those tasks are mainly terminal/files. Run reference solutions and deliberate incorrect actions without paid solvers wherever possible.

Deliver: immutable initial snapshots, reset API, tool adapter, trace schema, independent scorer, and a measured resource/cost profile.

**Gate:** all reference cases replay correctly; all known critical invalid actions are rejected; valid alternatives are accepted; no cross-trial state leaks; intended network/secret boundaries are verified. These are finite test criteria, not a claim of universal correctness. A failed gate is repaired before scaling.

### Stage 3: extend the existing generator experiment

Retain the prior A–D comparison: direct generation; structured specification/review; executable primitives plus reference replay; and independent verifier audits plus controlled composition. Do not multiply every generator condition by every solver/team configuration initially.

Use the same workload briefs and record attempted and accepted task counts, repair effort, and cost. Have reviewers blind to generation condition where feasible. Independently authored tasks test whether success on generated tasks transfers.

Deliver: a validity/yield comparison and an accepted task-family catalog. The earlier target of roughly 50 accepted instances across 8–12 families remains an engineering pilot target, not a powered study.

### Stage 4: run a bounded collaboration screen

On development/selection tasks, choose two model families provisionally called A and B. Select exact available versions using a small capability/cost check, then freeze them. Do not use an unverified general leaderboard to declare the best model for this workload.

Suggested six configurations:

1. A alone.
2. B alone.
3. Best development-selected single model with extra inference/self-review under the team budget.
4. A executor + B critic.
5. A executor + A critic, testing whether role separation helps without model diversity.
6. A coordinator + B specialist + C specialist, testing a three-model team on decomposable work.

C is a third model family selected on development evidence. Keep its initial deployment small. If costs exceed the pilot envelope, screen on fewer development tasks first and postpone the full three-model condition; do not quietly reduce repetitions in the final comparison.

Deliver: measured costs, failure taxonomy, and quality/cost/latency trade-offs. A team that loses to the best eligible single-model baseline is a useful research finding.

### Stage 5: freeze and confirm

Before opening the final cohort, freeze model versions, prompts, orchestration, task generator, environment, verifier, budgets, and statistical comparisons. Generate the sealed cohort from held-out task families/source lineages under a fixed sampling plan. It is additional to development/selection data, not the same 50 tasks relabeled after tuning.

Use pilot paired differences and family-level variance to plan the number of independent families and trials. Include a representative suite and a separately labeled challenge suite. Report all exclusions, missing scores, uncertainty, and severe failures.

**Success criterion:** the benchmark demonstrates defensible task validity and scoring, and the selected agent's results transfer to independently authored or held-out work. Multi-model superiority is a hypothesis, not a required outcome.

### Stage 6: derive the customized agent

Only after confirmation, derive simple model-selection or team-selection rules from development/selection evidence: task type, expected cost, observed reliability, and escalation conditions. Compare the routed policy against the best fixed model and best fixed team on a fresh sealed evaluation. Account for routing overhead and avoid using hidden task difficulty or grader outputs as route features.

Add browser/desktop execution, live retrieval, or cross-task memory as separate extensions with new validity and leakage audits. Increasing realism should be supported by evidence that the simpler environment misses important workload behavior.

## Open decisions and limitations

The workload, tool interface, primary environment, exact models, credit eligibility, acceptable failure costs, expert review availability, and final study size remain open. No framework compatibility, installation, sandbox containment, dataset quality, or cost estimate has been empirically verified here. AppWorld component terms need a dedicated reuse check; ThinkingBox data remains inaccessible; LiveBench 2.0 methodology and verifier-hardening implementation availability remain unverified.

The strongest immediate next artifact is a workload-specific execution and evaluation specification containing the environment contract, independent grading rules, team protocol, metric definitions, budget instrumentation, and go/no-go gates above. This research supports building that specification without restarting the completed task-generation survey.
