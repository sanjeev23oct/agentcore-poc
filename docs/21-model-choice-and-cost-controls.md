# Model Choice and Cost Controls: Guardrails, LLM-as-a-Judge, Memory, Retrieval, Routing

**Question this answers:** besides the main agent model, AgentCore and Bedrock make other model
calls: safety screening, evaluation judging, memory extraction, retrieval. **Where can we choose a
cheaper model, where can't we, and what other cost levers exist?**

**How this doc is organised:** Part A is AWS documentation only (AgentCore devguide, Bedrock user
guide, Well-Architected Agentic AI Lens, Nov 2026). Part B is our recommended defaults. No
third-party sources. **No prices are quoted**; they change and vary by Region. Use the
[Amazon Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) and
[AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/) for numbers.

---

# Part A: What AWS documents

## A1. Summary: who picks the model?

| Where a model is used | Can you choose the model? | Main cost levers |
|---|---|---|
| **Your agent's own reasoning** (Runtime code or Harness) | **Yes**, any supported model; Harness can override per invocation | Tiered models, routing, fallback, pricing tier, batch (A2) |
| **Bedrock Guardrails** (content, topics, PII, prompt attack, grounding) | **No model choice.** You choose which **policies** and a **safeguard tier** (Classic / Standard) | Enable only the policies you need; apply where they add value (A3) |
| **Evaluations: built-in evaluators** | **No**, fixed by AWS | Sampling %, evaluation level (A4) |
| **Evaluations: custom LLM-as-a-judge** | **Yes**, any Bedrock model (`modelId`) | Cheaper judge model, sampling %, multi-dimension in one call |
| **Evaluations: derived evaluators** | **Yes**, reuse a built-in/third-party evaluator's prompt and scoring on **your** model | Run AWS's evaluator logic on a cheaper model |
| **Evaluations: code-based** | **No LLM**, your Lambda | Cheapest for rule-checkable criteria |
| **Memory: built-in long-term strategies** | Managed by AWS | Use only the strategies you need |
| **Memory: custom strategies** | **Yes**, model override per step (extraction, consolidation) | Cheaper model for extraction |
| **Managed KB: `AgenticRetrieveStream`** | **Yes**: `MANAGED` or `CUSTOM` model; reranker `MANAGED` / `CUSTOM` / `NONE` | `maxAgentIteration`; use `Retrieve` (single search) when enough |
| **Bedrock KB GraphRAG** | **Yes**, you choose the graph-construction model | Model choice at ingestion ([16](./16-context-graph-and-semantic-layer.md)) |

## A2. The main agent model: tiering and routing

**Well-Architected Agentic AI Lens, AGENTCOST02-BP01** (risk if not done: **High**): *"Match each
task to the cheapest model capable of acceptable quality, and escalate only when confidence
drops."* AWS recommends:
- Classify tasks into **simple** (classification, format conversion, intent extraction),
  **moderate** (multi-step reasoning, summarisation) and **complex** tiers, each mapped to a model,
  with the policy recorded as an architecture decision.
- A lightweight **pre-classifier** (rules or a small model) that *"must cost less than the tier
  price differential."*
- **Model cascading**: escalate to a bigger model only when the smaller one's confidence is low;
  fallback chains move *up* a tier on failure rather than retrying.
- **Pricing tiers**: *"Flex for development and testing at the lowest per-token cost, Standard for
  production, and Priority only for latency-sensitive user-facing interactions"*; **batch
  inference** *"up to 50% savings"* for non-time-sensitive work (including **offline
  evaluation**); **Reserved Tier** *"30 to 50% savings"* for consistent high volume.
- Measure **cost-per-correct-response** with AgentCore Evaluations; review routing quarterly.

**Built-in routing options:**
- **AgentCore Gateway inference targets** with rule-based routing and an ordered **model fallback
  chain** when the primary is throttled or unavailable ([07](./07-gateway-identity-memory.md)).
- **Bedrock Intelligent Prompt Routing**: one endpoint that routes between models **in the same
  family**, predicting response quality per request *"to optimize for both response quality and
  cost."* Default routers use select Amazon Nova and Meta Llama models; configured routers let you
  choose models and routing criteria.
- **Harness**: model is configuration; switchable per invocation and mid-session ([03](./03-harness.md)).

## A3. Bedrock Guardrails: no model to choose, but tiers and policies

- You **don't pick a model** for Guardrails. You configure **policies** (content filters, prompt
  attacks, denied topics, sensitive information/PII, contextual grounding, etc.) and, for some, a
  **safeguard tier**.
- **Tiers** apply to content filters and prompt attacks, denied topics, and contextual grounding:
  - **Standard**: *"more robust performance"*, extensive language support, prompt-leakage
    detection, better handling of code. **Uses cross-Region inference.**
  - **Classic**: *"established guardrails functionality supporting English, French, and Spanish."*
  - AWS suggests Standard for multi-language apps or higher accuracy needs, and Classic where content
    is English/French/Spanish, or while migrating.
- **Data-residency note:** because the Standard tier uses **cross-Region inference**, screening
  requests may be processed in other Regions within the configured guardrail profile. Confirm this
  is acceptable under the bank's data-residency rules before choosing Standard.
- **Billing basis** is per text unit (or image) **per configured safeguard**. Cost scales with the
  number of policies enabled and the volume of text screened. See the Bedrock pricing page for
  current rates and any tier differences.
- **Coverage limit (important for agents):** AWS: content filters *"do not evaluate tool results
  (`toolResult`), tool definitions (`toolSpec`), or model-generated tool call arguments
  (`toolUse.input`)"* in tool-use workloads. Text returned by tools or other agents is **not**
  screened by a guardrail attached to the model call. Screen it explicitly with the standalone
  `ApplyGuardrail` API if needed ([11](./11-guardrails.md)).
- The KB target's `AgenticRetrieveStream` can attach a guardrail (`policyConfiguration`)
  ([18](./18-sharepoint-and-enterprise-knowledge.md)).

## A4. Evaluations (LLM-as-a-judge)

- **Built-in evaluators**: configurations *"including their evaluator models and prompt templates,
  cannot be modified"* ([12](./12-evaluations.md)). The service runs them on a model it operates.
- **Custom LLM-as-a-judge evaluators**: *"specify the judge model in `modelConfig`"*: a
  `modelId` on the Bedrock Runtime endpoint (`bedrockEvaluatorModelConfig`) or Bedrock Mantle
  endpoint (`responsesEvaluatorModelConfig`), plus optional `maxTokens`, `temperature`, etc.
  **AWS's own ground-truth examples use Claude Haiku 4.5 as the judge.**
- **Derived evaluators**: reuse a built-in or third-party evaluator's prompt and scoring, but run
  them **on your own model** instead of the service-operated one.
- **Code-based evaluators**: an AWS Lambda function, so no LLM call. Suitable for checks expressible as
  rules (format, required fields, exact values).
- **Cost levers AWS documents:**
  - **Sampling** for online evaluation: `samplingPercentage` **0.01%–100%** (console default 10%).
    Set it explicitly, since defaults differ between interfaces.
  - **Evaluation level**: *"Select the appropriate evaluation level based on your cost, latency,
    and performance requirements"*: tool call, trace, or session.
  - **Multi-dimension evaluators** rate several dimensions *"in a single judge call"* instead of
    several evaluators.
  - Custom evaluators with ground-truth placeholders work only in on-demand/batch runs, not
    online.

## A5. Memory long-term extraction

- AgentCore Memory *"invokes an Amazon Bedrock model in your account on your behalf"* for
  long-term strategies.
- **Custom strategies** accept a **model override per step**: e.g. semantic extraction and
  consolidation, summary consolidation, episodic extraction and consolidation, each with its own
  `modelId`, plus optional appended prompt text. You must have access to the override model.

## A6. Managed Knowledge Base retrieval

On the Gateway KB target ([18](./18-sharepoint-and-enterprise-knowledge.md)):
- `AgenticRetrieveStream`: `foundationModelType` `MANAGED` (default) or `CUSTOM` (your Bedrock model
  ARN); `rerankingModelType` `MANAGED` / `CUSTOM` / `NONE`; `maxAgentIteration` caps planning and
  retrieval loops; `generateResponse: false` returns results only (no synthesised answer).
- `Retrieve`: a single hybrid search, no planning loop.

---

# Part B: Recommended defaults (our synthesis; confirm with cost and quality data from the POC)

| Component | Recommended default | Why |
|---|---|---|
| **Intent classification / routing in the orchestrator** | Small, cheap model (or rules) as pre-classifier | AWS AGENTCOST02-BP01; most RM questions are routing plus lookup |
| **Answer synthesis for RMs** | Mid-tier model; escalate to a larger one only for complex analysis | Cascade on low confidence, not by default |
| **Fallback** | Gateway inference fallback chain to an alternative model | Availability without code changes |
| **Guardrails** | Enable only needed policies (PII, prompt attack, denied topics for advice limits, grounding for document answers). Choose **tier** on language and residency grounds, not cost alone | No model choice; cost is per policy and volume |
| **Tool and other-agent outputs** | Screen with `ApplyGuardrail` where content is untrusted (other departments, external agents) | Model-call guardrails don't screen tool results (A3) |
| **Online evaluation** | Custom or derived evaluators on a **small judge model**, **sampled** (start ~5–10%), trace level; code-based evaluators for rule checks | Continuous signal at controlled cost |
| **Pre-release / regression evaluation** | Larger judge model on a fixed test set, run as batch / on-demand | Accuracy matters more than cost here; volume is small |
| **Judge calibration** | Before trusting a cheaper judge, compare its scores with a larger judge and human labels on the same sample | A cheap judge that disagrees with humans gives false confidence |
| **Memory** | Built-in strategies first; custom strategy with smaller extraction model only if Memory cost becomes material | Avoid premature tuning |
| **SharePoint Q&A** | `Retrieve` for simple lookups; `AgenticRetrieveStream` with `maxAgentIteration` capped for multi-part questions | Pay for planning only when needed |
| **Dev / test** | Flex pricing tier; batch inference for offline jobs | Lowest cost where latency doesn't matter |

**Governance:** record the model-per-task mapping as an architecture decision (AWS recommends this),
tag costs per agent and department ([20](./20-reusability-first-department-to-enterprise.md)), and
re-test quality whenever a model is swapped for a cheaper one. AWS lists *"failing to monitor
customized model performance after switching to a smaller tier"* as an anti-pattern.

## Sources (AWS)

- [AGENTCOST02-BP01 Architect tiered model selection (Agentic AI Lens)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentcost02-bp01.html)
- [Create evaluator (AgentCore)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-evaluator.html)
- [Custom evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/custom-evaluators.html)
- [Third-party and derived evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/third-party-evaluators.html)
- [Create online evaluation (sampling)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/create-online-evaluations.html)
- [Configure a custom memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-custom-strategies.html)
- [Managed KB as Gateway connector target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-managed-kb.html)
- [Bedrock Guardrails content filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html)
- [Safeguard tiers for guardrails policies](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tiers.html)
- [Intelligent prompt routing](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html)
- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/)
