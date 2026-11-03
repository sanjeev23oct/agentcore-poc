# Architecture: Runtime vs Harness vs Gateway vs Identity vs Memory

## The layering

```
                    ┌─────────────────────────────────────────┐
                    │              Your agent logic             │
                    │  (Strands / LangGraph / CrewAI / custom)  │
                    └───────────────┬───────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                                               │
   ┌────────▼─────────┐                          ┌──────────▼─────────┐
   │   AgentCore       │   "config, no code"      │   AgentCore         │
   │   Harness          │◄────────────────────────┤   Runtime            │
   │ (managed loop,      │   Harness IS a Runtime   │ (hosts your          │
   │  Strands-powered)   │   agent under the hood   │  container/code,     │
   └────────┬─────────┘                          │  any framework)      │
            │                                               └──────────┬─────────┘
            │                                                           │
            └───────────────────────┬───────────────────────────────────┘
                                    │  both call out to
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
   ┌────────▼────────┐    ┌─────────▼─────────┐    ┌─────────▼─────────┐
   │ AgentCore Gateway │    │ AgentCore Identity │    │ AgentCore Memory   │
   │ (tools, APIs, MCP, │    │ (OAuth, workload    │    │ (short/long-term   │
   │  other agents, A2A,│    │  identity, creds)   │    │  memory store)     │
   │  model routing)    │    └────────────────────┘    └────────────────────┘
   └────────┬───────────┘
            │
   ┌────────▼───────────────────────────────────┐
   │ Targets: Lambda, OpenAPI, MCP servers, other │
   │ Runtime agents, Step Functions, HTTP passthrough │
   └──────────────────────────────────────────────┘
```

## What's managed vs. what you build

| Concern | Harness | Runtime (direct) |
|---|---|---|
| Agent loop (model call → tool pick → tool exec → repeat) | **Managed** — Strands-based, config only | **You build it** (any framework) |
| Compute / isolation | Managed microVM (same substrate as Runtime) | Managed microVM or Instances |
| Memory | Managed, on by default (GA added this in Jun 2026) | Bring your own via Memory SDK |
| Identity/credentials | Managed via Identity integration | You wire up Identity SDK yourself |
| Observability | Automatic, unified across capabilities | You instrument (OTel) or use built-ins |
| Tool connectivity | Via Gateway, MCP servers, built-in Browser/Code Interpreter | Same, but you call the SDKs yourself |
| Custom orchestration logic (e.g., a LangGraph graph, custom control flow) | **Not supported** — Harness's loop is fixed/Strands | Fully yours — any framework, any language |

Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html), [What is Amazon Bedrock AgentCore?](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

**Key architectural fact: Harness is not a separate compute substrate.** Per AWS docs, "Each harness you create is backed by a managed AgentCore Runtime that AgentCore provisions and operates on your behalf." (Source: [Quotas for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)). So Harness = Runtime + a fixed, config-driven Strands loop + built-in memory/skills wiring. It is a convenience layer, not a different deployment target. This means a harness agent is still subject to Runtime's quotas (session limits, concurrency, cold start behavior described in [02-runtime-microvm.md](./02-runtime-microvm.md)).

## Gateway's actual role

Gateway is the integration/aggregation layer, not an execution environment. It:
- Converts APIs, Lambda functions, and MCP servers into a single MCP-compatible endpoint (aggregation mode: one `tools/list` call returns tools from every attached target).
- Fronts other agents (including Runtime agents and external A2A agents) via HTTP passthrough and dedicated Runtime targets.
- Routes LLM inference traffic across providers (Gateway "inference targets", added mid-2026).
- Handles both inbound auth (who can call the gateway) and outbound auth (how the gateway authenticates to each target) — this is explicitly called out as something few competing tools do in one managed service.

Source: [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)

## Identity's actual role

Identity is a workload-identity and credential broker, decoupled from both Runtime and Harness. It supports M2M, on-behalf-of (OBO), and user-delegated OAuth flows, issues/caches tokens for outbound calls, and as of Sep 2026 added a hosted **Consent Portal** for end-user authorization grants. It integrates with existing IdPs (Cognito, Okta, Entra ID, Auth0) rather than requiring user migration. Details in [07-gateway-identity-memory.md](./07-gateway-identity-memory.md).

## Memory's actual role

Memory is a standalone managed data service (short-term session memory + long-term cross-session memory with pluggable extraction strategies). It's usable from Harness (built-in, zero-config) or from Runtime/any external compute (via SDK, with explicit framework integrations for LangGraph, LangChain, Strands, LlamaIndex). It is **not** tied to Runtime or Harness — you can call AgentCore Memory APIs from a Lambda function or an on-prem service with no other part of AgentCore involved. Source: [Add memory to your agent](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html).

## Net architectural takeaway

For an org already running LangGraph, the clean adoption boundary is: **Runtime (hosting) + Gateway (tool/MCP aggregation) + Identity (auth) + Memory (state)**, each adopted independently, while keeping LangGraph as the orchestration layer. **Harness is off the table** for a LangGraph-based agent because it only runs its own built-in Strands loop — see [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md) for the evidence.
