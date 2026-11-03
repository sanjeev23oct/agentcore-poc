# Guardrails on AgentCore: Bedrock Guardrails vs. AgentCore Policy

Two different AWS capabilities get called "guardrails" in and around AgentCore, and conflating them overstates what either one does. This doc separates them.

## The short answer

| | What it is | What it does | Where it attaches | AgentCore-specific? |
|---|---|---|---|---|
| **Amazon Bedrock Guardrails** | A pre-existing Bedrock feature (not new for AgentCore) | Content filtering, denied topics, PII detection/redaction, grounding/contextual-relevance checks on model input and output | One config object (`guardrailConfig`) passed on each model call, in Harness or in your own Runtime code | **No** — it's the same Bedrock Guardrails service used by any Bedrock application; AgentCore just has a documented wiring pattern for it |
| **AgentCore Policy** | A genuinely AgentCore-specific service | Deterministic, Cedar/Dogwood-authored rules that allow/deny *tool calls* based on identity, parameters, and session history | Intercepts every call at the **Gateway** layer, before the tool executes | **Yes** — this is new, not a repackaging of an existing Bedrock feature |

They are complementary, not redundant: Guardrails screens what the model *says*; Policy decides what the agent is *allowed to do*. Policy can even consume a Guardrails score as one of its inputs (see below) — so in a mature setup they're wired together, not substitutes for each other.

## Amazon Bedrock Guardrails on AgentCore

### It's the existing Bedrock feature, not something new

AgentCore does not ship its own content-filtering engine. What's documented is a wiring pattern for attaching the pre-existing **Amazon Bedrock Guardrails** service (the same one used by any direct Bedrock `Converse`/`InvokeModel` caller) to agent model calls.

Verified directly against AWS's live devguide (Nov 2026), under Harness → Models and instructions → "Apply Amazon Bedrock Guardrails":

> "Use Amazon Bedrock Guardrails to filter harmful content or block denied topics in model inputs and outputs. To apply a guardrail to each model request, add a `guardrailConfig` object to `bedrockModelConfig.additionalParams`. The harness passes this object to Amazon Bedrock with each model request."

Source: [Models and instructions — AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-models.html)

### What Bedrock Guardrails itself covers (general Bedrock feature, not AgentCore-specific)

Per the standard Bedrock Guardrails capability set that this wiring plugs into:
- **Content filtering** — configurable thresholds across categories (hate, insults, sexual, violence, misconduct, prompt attacks).
- **Denied topics** — block entire topics by natural-language description.
- **PII detection/redaction** — detect and mask/block a defined set of PII entity types in input or output.
- **Word filters** — custom blocklists and profanity filters.
- **Grounding / contextual-relevance checks** — score whether a RAG-style response is grounded in the provided source content and relevant to the query (Bedrock's "contextual grounding" check).

These are Bedrock Guardrails capabilities, not independently re-verified against the Guardrails service docs in this pass — treat this list as "what Bedrock Guardrails generally offers," confirmed by cross-reference to the AgentCore harness page's link to [Use a guardrail with the Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-converse-api.html), not independently re-fetched from the Guardrails service's own devguide in this pass. **If this distinction matters for the management decision (e.g., exact PII entity coverage), verify against the live [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) devguide before citing specifics.**

### How it's wired into Harness

Exact mechanics, confirmed from the live page:
- Guardrail config lives in `bedrockModelConfig.additionalParams.guardrailConfig`, with `guardrailIdentifier`, `guardrailVersion`, and an optional `trace` setting.
- Requires `bedrockModelConfig` to use the `converse_stream` API format — which is the harness default, so no extra config needed there.
- Can be set at harness creation/update time (applies to every invocation) **or** overridden per-call on `InvokeHarness` — same override pattern as model/prompt/tools.
- **Screens both directions in the loop**: the AWS harness documentation describes the guardrail screening the input, the harness then calling Bedrock again with the tool result appended, and the guardrail screening that output too — i.e., it runs on every model round-trip in the agent loop, not just the first and last turn.
- The harness execution role needs an explicit `bedrock:ApplyGuardrail` IAM permission scoped to the guardrail's ARN — this is not implicit.
- When a guardrail blocks something, the invocation's response stream reports `guardrail_intervened` as the stop reason — a concrete, checkable signal for your calling application.
- The guardrail must be in the **same AWS Region** as the model request.

Source: [Models and instructions — AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-models.html)

### How it attaches to Runtime (custom code) agents

Runtime is "bring your own code," so there is no AgentCore-specific wiring documented for it — you call the standard Bedrock `ApplyGuardrail` / guardrail-config-on-Converse pattern directly in your own agent code, exactly as you would in any non-AgentCore Bedrock application. This was not independently re-verified against a Runtime-specific devguide page in this pass, but it follows directly from Runtime's "framework-agnostic, you write the loop" architecture described in [02-runtime-microvm.md](./02-runtime-microvm.md) and [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md): there is no managed harness loop on Runtime to inject a config object into, so the integration point is your code's own Bedrock SDK calls, not an AgentCore API.

**Practical implication for the LangGraph migration:** if the existing LangGraph agent is deployed to Runtime (the recommended path per [09-migration-from-langgraph.md](./09-migration-from-langgraph.md)), adopting Bedrock Guardrails is exactly as much work as it would be in the current self-hosted deployment — call `ApplyGuardrail` or pass `guardrailConfig` on your own `Converse` calls inside the LangGraph nodes that call the model. AgentCore Runtime does not add or remove friction here; the convenience is Harness-only, and Harness is already ruled out for this agent.

### Latency and cost

**Not documented on the pages reviewed in this pass.** The AgentCore harness page does not state a latency overhead or cost adder for applying a guardrail — it only documents the mechanics (config, IAM permission, stop-reason signal). Bedrock Guardrails has its own per-text-unit pricing and adds a model round-trip for classification, which is well known for the general Bedrock service, but this research pass did not independently re-verify current guardrail latency/cost figures against the live Bedrock pricing/guardrails pages. **State this plainly in any management-facing cost model: "Guardrails latency/cost impact is not quantified in AgentCore's own docs; budget via the standalone Bedrock Guardrails pricing page before committing."**

## AgentCore Policy: the other "guardrail," and how it differs

This is the capability behind the "policy engines and Cedar policies" language that shows up in the AgentCore CLI (`agentcore add policy-engine`, `agentcore add policy`) and in [10-enterprise-best-practices.md](./10-enterprise-best-practices.md). It is a distinct service from Bedrock Guardrails, confirmed directly from AWS's live Policy devguide page (Nov 2026):

> "Policy in Amazon Bedrock AgentCore enables developers to define and enforce security controls for AI agent interactions with tools... With Policy in AgentCore, developers can create policy engines, create and store deterministic policies in them and associate policy engines with gateways. Policy in AgentCore intercepts all agent traffic through Amazon Bedrock AgentCore Gateways and evaluates each request against defined policies in the policy engine before allowing tool access."

Source: [Policy in Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

Key properties:
- **Gates tool calls, not model text.** Policy decides whether a specific tool call (by principal, tool name, resource, and input parameters) is allowed — it is an authorization layer, not a content filter.
- **Enforced outside agent code, at the Gateway.** Every call through a Gateway with an attached policy engine is evaluated before the tool executes — the agent cannot reason or prompt-inject its way around it, because the check happens in infrastructure the agent doesn't control.
- **Policy language: Cedar, or Dogwood (Cedar-compatible).** Policies are written in [Cedar](https://www.cedarpolicy.com/en) (AWS's open-source authorization-policy language) directly, or in [Dogwood](https://dogwood-policy.github.io/dogwood/index.html), an open-source language that is a strict superset of Cedar — "every valid Cedar policy is also a valid Dogwood policy." Dogwood adds condition forms Cedar can't express: `when guardrails { … }` and `when temporal { … }`.
- **Natural-language authoring.** You can describe a rule in plain English; AgentCore translates it to Cedar/Dogwood, validates it against the tool schema, and runs automated reasoning to flag policies that are overly permissive, overly restrictive, or unsatisfiable — before you enforce them.
- **Temporal (session-aware) conditions.** Beyond single-call rules, Dogwood policies can reason over session history — e.g., "require that an approval tool call happened earlier in this session before allowing a transfer," or "block an action after it has run N times," or "keep a running total under a budget" — within a 24-hour lookback window and up to 3 temporal operators per policy (per the Nov 2026 Quotas page).
- **This is where Policy and Guardrails actually connect.** Per the live Policy docs: "You can also consult information providers, such as Guardrails, that emit a signal at evaluation time — such as a content-safety or prompt-attack score — and make decisions based on the emitted score." So a Policy rule can say, in effect, "deny this tool call if the Guardrails content-safety score on the triggering input was above X" — Guardrails becomes one signal Policy can act on, not a competing mechanism.

Source: [Policy in Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html), [Guardrails in policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.md) (topic listed on the Policy page; not independently fetched — verify the exact signal-consumption mechanics before implementing).

### Quotas worth knowing (Nov 2026, from the live Quotas page)

| Limit | Value | Adjustable |
|---|---|---|
| Policy engines per account per Region | 1,000 | No |
| Policies per policy engine | 1,000 | No |
| Generated policies (7-day rolling window) per policy engine | 50,000 | No |
| Maximum policy size | 10 KB | No |
| Maximum total policy size per resource | 200 KB | No |
| Cedar schema size per policy engine | 400 KB | No |
| Temporal policies per policy engine | 20 (of the 1,000 total) | No |
| Temporal operators per policy | 3 | No |
| Maximum time window per temporal condition | 24 hours | No |

Source: [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html), re-fetched directly in this pass.

## What this means for the migration decision

- **Adopting Bedrock Guardrails requires no AgentCore adoption at all.** It's the same service, same pricing, same config shape whether you call it from a self-hosted LangGraph agent today or from a LangGraph agent hosted on AgentCore Runtime tomorrow. This is not a reason to move to AgentCore.
- **Adopting Policy *is* an AgentCore-specific gain, but it requires Gateway.** Policy only intercepts traffic that flows through an AgentCore Gateway with a policy engine attached — so it's only on the table if Gateway is already part of the adoption plan (which it is, per the hybrid recommendation in [README.md](./README.md)). If the existing LangGraph agent calls tools directly (not via Gateway), Policy provides zero protection on those calls until they're re-pointed at Gateway targets.
- **Natural-language policy authoring plus automated-reasoning validation is a genuinely differentiated enterprise control** — it directly addresses the "agent might reason around a prompt-level rule" risk that pure model-level guardrails can't fully close, since enforcement happens in infrastructure outside the agent's control loop.
- **Don't let "guardrails" in a vendor pitch deck imply more than content filtering.** If a stakeholder asks "does AgentCore have guardrails," the accurate answer is two-part: "yes, the same Bedrock Guardrails you could use today, with a documented Harness wiring pattern; and separately, yes, a genuinely new tool-call authorization layer called Policy, which is the part actually specific to AgentCore."
