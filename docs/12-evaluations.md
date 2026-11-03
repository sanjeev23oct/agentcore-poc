# AgentCore Evaluations and Optimization

Evaluations is the one AgentCore capability that is explicitly documented to work **regardless of hosting choice** — it evaluates agent telemetry (spans/traces), not agent deployment target, so it's available to a LangGraph-on-Runtime agent on equal footing with a Harness agent. This is the strongest "adopt independently" case in the whole platform.

## What gets evaluated, and how

AgentCore Evaluations scores agent behavior by reading **OpenTelemetry or OpenInference spans** your agent already emits (or that you instrument it to emit), converting them to a unified internal format, and scoring them with LLM-as-a-judge techniques plus some deterministic checks.

> "Amazon Bedrock AgentCore Evaluations provides automated assessment tools to measure how well your agent or tools perform specific tasks, handle edge cases, and maintain consistency across different inputs and contexts... Under the hood, traces from these agents are converted to a unified format and scored using LLM-as-a-Judge techniques for both built-in and custom evaluators."

Source: [Evaluate agent performance with Amazon Bedrock AgentCore Evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html)

### Built-in evaluators confirmed by name (Nov 2026)

The docs organize evaluators into trace-level and session-level, ground-truth and non-ground-truth. Specific named evaluators found in this pass (via AWS documentation references, not all independently re-fetched page-by-page — verify exact scoring methodology against each evaluator's own doc page before quoting precision numbers to management):

| Evaluator | Scope | What it checks |
|---|---|---|
| `Builtin.Correctness` | Trace | How accurately the response matches an expected answer (ground-truth) |
| `Builtin.Helpfulness` | Session | Whether the response helps the user, without a ground-truth answer |
| `Builtin.Faithfulness` | Session | Groundedness — whether claims in the response are supported by retrieved/provided context |
| `Builtin.GoalSuccessRate` | Session | Whether the agent's behavior satisfies a natural-language assertion of the session goal |
| `Builtin.TrajectoryExactOrderMatch` | Session | Actual tool-call sequence matches an expected sequence exactly |
| `Builtin.TrajectoryInOrderMatch` | Session | Expected tools appear in order, extra calls allowed between them |
| `Builtin.TrajectoryAnyOrderMatch` | Session | All expected tools were called, order doesn't matter |
| `Builtin.FailureAnalysis` | Session (insight-providing) | Categorizes failures (tool errors, hallucinations, incorrect reasoning, repetitive behavior, etc.), traces root cause to specific spans, suggests fixes |
| Skill evaluators | Trace, conditional | Apply only when a tool call loads an AWS skill |

So yes: **trajectory (tool-call-sequence) evaluation, tool-use correctness, and groundedness/faithfulness are all explicitly supported**, confirmed by evaluator name, as is a dedicated failure/root-cause analyzer. Built-in evaluators are fixed — "Built-in evaluator configurations, including their evaluator models and prompt templates, cannot be modified" — if you need different scoring logic, you write a **custom evaluator** instead (up to 10,000 per account, up to 50 dimensions per multi-dimension custom evaluator, per the live Quotas page).

Source: [Built-in evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-evaluators-overview.html), [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)

### Third-party evaluators

AWS also documents integration with **third-party evaluators** (e.g., a DeepEval `ToolUse` metric that "checks whether the agent picked the right tool and passed correct arguments" per this pass's research) — not independently re-fetched in full from [third-party-evaluators.md](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/third-party-evaluators.html) in this pass; verify the full list before relying on specific third-party evaluator names.

## Online vs. batch vs. on-demand evaluation

AWS documents three distinct evaluation modes, each with its own devguide section and its own service quotas (confirmed from the live Quotas page):

| Mode | What it is | Typical use |
|---|---|---|
| **Online evaluation** | A persistent "online evaluation configuration" resource that continuously monitors a data source (e.g., a CloudWatch log group tied to a deployed agent) and scores sessions as they happen, using configured evaluators | Continuous production quality monitoring; up to 1,000 configurations/account, up to 25 evaluators per configuration |
| **Batch evaluation** | An on-demand job (`StartBatchEvaluation`) that scores a defined set of existing sessions (by time range or explicit session IDs) against one or more evaluators, once | Retrospective analysis of a time window, or re-scoring after a prompt change; up to 500 sessions/job, up to 10 evaluators/job, 5 concurrent jobs/account |
| **On-demand evaluation** | A single synchronous evaluation call against supplied content, not tied to a deployed agent's session history | Ad hoc scoring, e.g. in a CI pipeline, before sessions even exist; max 1 evaluator per on-demand call, 20,000 spans per call |

Source: [Online evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/online-evaluations.html), [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html) — the online-evaluations.html page itself is mostly a topic index in the live docs (prerequisites, create/get/list/update/delete, results); the mode distinctions above are confirmed primarily from the Quotas page's separate quota sections for each mode, which is strong evidence the three are genuinely distinct resources/APIs, not just marketing names for one feature.

There is also a separate **dataset evaluation** path (`dataset-evaluations.md`, and a `BatchEvaluationRunner` in the Python SDK) for running an agent against a fixed test dataset and evaluating the resulting sessions — closer to a regression-test harness than production monitoring. Not independently fetched in full in this pass.

## The "Recommendations" / agent-performance loop

This is the GA capability the task brief specifically flagged — AI-generated suggestions for system-prompt/tool-description changes, derived from production traces. Confirmed directly from the live AgentCore Optimization devguide page:

> "AgentCore optimization builds on AgentCore Evaluations and introduces three capabilities: **Recommendations** — AI-generated improvements to system prompts and tool descriptions based on real agent traces and a target evaluator. The service analyzes failure patterns based on the target evaluator and produces an optimized variant of the system prompt or tool descriptions. **Configuration bundles** — Versioned, immutable snapshots of agent configuration... **A/B testing** — Controlled traffic splitting between two variants through AgentCore Gateway, with online evaluation scoring for each session and reporting statistical significance."

Source: [AgentCore optimization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html)

### How the loop actually works end to end

1. **Triage with Insights.** Run `Builtin.FailureAnalysis` (via batch evaluation) over a window of production sessions. It groups failures across sessions into a three-level hierarchy — failure categories → subcategories → root-cause clusters — each with affected session counts, an explanation, and a suggested fix. Example from AWS's own sample response: a cluster named "Tool calls fail because of permission and quota errors," root cause "Constraints are not visible to the agent before it acts," suggested fix "Update the tools to return current limits and permissions, and update the system prompt to check them before it changes a resource."
2. **Generate a recommendation.** Call `StartRecommendation` with your current system prompt, pointed at the same traces and a target evaluator. The service returns a recommended system prompt (or tool description) plus an explanation of what it changed.
3. **Validate with A/B testing**, not a blind rollout. Compare the original and recommended configuration with live traffic, split through Gateway, with statistical-significance reporting before you commit to the change.

Source: [AgentCore insights: Triage agent failures with pattern analysis](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/insights.md) (standalone page), [Insights in batch evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-insights.md) (current mechanism)

### Important and time-sensitive correction: standalone "Insights" is being sunset

This matters for anything written about AgentCore Insights before this pass, and the task brief's own framing ("analyzes production traces to suggest... improvements") should be anchored to the *current* mechanism, not the deprecated one. Directly from the live devguide, as of this research pass (Nov 2026):

> "**Insights job creation ends October 16, 2026.** Beginning October 16, 2026, Amazon Bedrock AgentCore insights no longer supports creating new batch or recurring insights. Existing recurring insight jobs continue to process sessions and generate reports through October 30, 2026. Beginning October 31, existing recurring insights will also stop generating reports."

The replacement, which is the thing to actually build against today, is **insight-providing evaluators inside Batch Evaluation** — specifically `Builtin.FailureAnalysis`, included alongside any other evaluators (e.g., `Builtin.GoalSuccessRate`) in a normal `StartBatchEvaluation` call. Results come back in the `insightResults` field of `GetBatchEvaluation` (up to 50 insights per job, each with root causes, suggested fixes, and up to 10 sample sessions per root cause). Recurring/scheduled analysis is now configured via a `ClusteringConfig` (`DAILY`/`WEEKLY`/`MONTHLY`) on an **online evaluation configuration**, not a standalone Insights resource.

Source: [AgentCore insights: Triage agent failures with pattern analysis](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/insights.md), [Insights in batch evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/batch-evaluations-insights.md)

**Note the standalone Insights page is also explicitly marked "public preview"** ("Features and APIs may change before general availability") even as it's being sunset in favor of the batch-evaluation-integrated version — so "is the recommendation loop GA?" has a nuanced answer: **Evaluations and Optimization (Recommendations, Configuration Bundles, A/B Testing) are GA; the specific triage/insights mechanism that feeds Recommendations changed hosts mid-2026 and the newer batch-evaluation-integrated version's GA status was not explicitly confirmed on the pages reviewed in this pass** — treat "insights-driven recommendations" as a GA capability delivered through a feature that itself just migrated, and re-verify GA status on `batch-evaluations-insights.md` before presenting it as fully stable to leadership.

## Framework support, including TypeScript

Confirmed directly from the live "Supported agent frameworks" page (Nov 2026) — this is a detailed, actively maintained compatibility matrix, not a marketing list:

| Framework | Python support | TypeScript support |
|---|---|---|
| Strands Agents | Built-in (Strands SDK) | Built-in (`@strands-agents/sdk >= 1.5.0`) |
| LangGraph | OpenTelemetry (`opentelemetry-instrumentation-langchain >= 0.55.0`) or OpenInference (`openinference-instrumentation-langchain >= 0.1.62`) | Three options: AWS's own ADOT-native instrumentation (`@aws/aws-distro-opentelemetry-instrumentation-langchain >= 0.12.0`), Traceloop (`@traceloop/instrumentation-langchain >= 0.27.0`), or OpenInference (`@arizeai/openinference-instrumentation-langchain >= 4.0.14`) |
| OpenAI Agents | OpenTelemetry or OpenInference | ADOT-native or OpenInference |
| LlamaIndex | OpenTelemetry or OpenInference | Not listed |
| Google ADK | OpenInference only | Not listed |
| Claude Agent SDK | OpenInference only | Not listed |
| Vercel AI SDK | Not applicable (TS-only framework) | ADOT-native only |

Source: [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)

**Confirms and sharpens the existing claim in [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md)**: LangGraph has genuinely first-class, multi-option instrumentation support in both Python and TypeScript — more instrumentation-library choice, in fact, than most other non-Strands frameworks on this list. This is real, current, and directly relevant: the existing production LangGraph agent's evaluation story is not a second-class citizen regardless of which language it's in or whether it ends up hosted on AgentCore Runtime or kept self-hosted (Evaluations ingests telemetry via CloudWatch regardless of hosting, per the framework-agnostic claim at the top of this doc).

A generic-framework fallback path also exists (`supported-frameworks-generic.md`, not independently fetched in this pass) for frameworks not in the table, presumably via raw OpenTelemetry spans matching a documented attribute contract.

## What setup is actually required

Evaluations is **not automatic just because you're running on AgentCore** — confirmed by the framework/instrumentation-matrix structure above and by the explicit note on the "Supported agent frameworks" index page:

> "Instrumenting your agent is only one part of producing telemetry that the evaluation service can read. Your agent must also have observability enabled, so that it exports its telemetry to Amazon CloudWatch."

Source: [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)

Concretely, to get a LangGraph agent evaluated:
1. Add the LangGraph OpenTelemetry or OpenInference instrumentation library (pick Python or the relevant TypeScript package from the table above).
2. Enable AgentCore observability export to CloudWatch for the hosting environment (Runtime, Harness, or — per the framework-agnostic framing AWS uses — potentially a non-AWS host, since Evaluations works "regardless of where the agent runs (Runtime, Lambda, EKS, or non-AWS)" per the existing [08-scalability-and-ops.md](./08-scalability-and-ops.md) finding, not independently re-verified against a primary source in this specific pass).
3. Create an online evaluation configuration (continuous) or run a batch/on-demand evaluation (point-in-time) against the resulting CloudWatch log groups, selecting built-in and/or custom evaluators.
4. Optionally wire the results into the Optimization loop: `StartRecommendation` against a target evaluator, then A/B-test the recommended configuration through Gateway before full rollout.

## How this integrates with Harness vs. Runtime

- **Harness**: Evaluations and the cost-control/observability surface are built in — no separate instrumentation step, since Harness's Strands-based loop emits its own telemetry automatically.
- **Runtime**: you add the instrumentation library for whatever framework you're using (LangGraph, in this org's case) and enable observability export yourself — exactly the setup steps above. This is real but modest engineering work (library install + config), not a rewrite.
- Either way, the **evaluators, batch/online jobs, and Optimization loop (Recommendations, Configuration Bundles, A/B testing) are the same APIs** — Evaluations does not have a Harness-only or Runtime-only tier of built-in evaluators documented in the pages reviewed.

## Headline points for the migration decision

1. **Evaluations is hosting-agnostic and LangGraph has first-class, multi-library support in both Python and TypeScript** — this is a real, verified capability gain available whether the org stays self-hosted-with-AgentCore-Evaluations-bolted-on or moves to Runtime, and it does not require Harness.
2. **Trajectory, tool-use, and groundedness scoring are all named, built-in evaluators**, not hand-wavy marketing claims — `Builtin.TrajectoryExactOrderMatch`/`InOrderMatch`/`AnyOrderMatch` and `Builtin.Faithfulness` are real, callable evaluator IDs today.
3. **The "Recommendations" loop is real and GA-level for the Evaluations/Optimization core**, but the specific triage mechanism feeding it (Insights) migrated from a standalone, soon-fully-deprecated feature (new jobs blocked since Oct 16, 2026) into an evaluator embedded in Batch Evaluation — verify GA status of that specific sub-feature before using it in a board-level capability claim.
4. **None of this requires Harness.** The entire Evaluations/Optimization value proposition is available to the recommended hybrid path (Runtime + Gateway + Identity + Memory, LangGraph orchestration retained) with a bounded, well-documented instrumentation step — not a rewrite.
