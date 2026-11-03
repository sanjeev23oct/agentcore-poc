# Migrating the Existing LangGraph Agent to AgentCore

## Can the existing LangGraph app be containerized and deployed to Runtime with minimal change?

**Yes, for hosting.** Runtime is framework-agnostic and explicitly lists LangGraph as a supported framework (see [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md)). The pattern, per AWS's `bedrock_agentcore` SDK (the same SDK already used in this repo's `agent.py` POC) and corroborated by third-party migration guidance:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    # your existing graph.invoke(...) call goes here
    ...
```

Source: [LangGraph + AWS Bedrock AgentCore (2026)](https://www.factualminds.com/blog/langgraph-aws-bedrock-agentcore-2026/)

## What's drop-in vs what requires rework

### Drop-in (minimal change)
- The LangGraph graph definition itself — nodes, edges, conditional routing, supervisor/hop-counter logic — **does not need to be rewritten**. Runtime just invokes your entrypoint function; it has no opinion on what's inside it.
- Existing tool-calling code, as long as tools are reachable from inside the container (direct SDK calls, or re-pointed at Gateway targets — see below).

### Requires rework
- **Deployment wrapper**: wrap the existing graph invocation with `@app.entrypoint`, per the pattern above.
- **Container/runtime requirements**: ARM64 image, health endpoint, listen on port 8080, create an actual Runtime endpoint (not optional — it's how `InvokeAgentRuntime` reaches your code).
- **Model configuration**: pin model IDs to inference profiles, set `max_tokens` explicitly, use `init_chat_model(..., model_provider="bedrock_converse")` if currently calling a different provider's SDK directly.
- **Memory**: if currently using LangGraph's own checkpointer for state, decide what stays as LangGraph checkpointing (execution state) vs. what moves to AgentCore Memory's long-term store (cross-session facts/preferences) — don't conflate the two. Wiring requires `actor_id`/`thread_id` configuration against the Memory Store service.
- **Identity/credentials**: if the agent currently manages its own API keys/secrets for tool calls, decide whether to move that to AgentCore Identity (OAuth flows, KMS-backed credential providers) or keep existing secret management and just host on Runtime.
- **Observability**: instrumenting for AgentCore Evaluations requires adding the LangGraph OpenTelemetry or OpenInference instrumentation library (`opentelemetry-instrumentation-langchain` or `openinference-instrumentation-langchain`) and enabling observability export to CloudWatch — not automatic just by deploying to Runtime.

Source: [LangGraph + AWS Bedrock AgentCore (2026)](https://www.factualminds.com/blog/langgraph-aws-bedrock-agentcore-2026/), [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)

## What you gain by moving to Runtime (even keeping LangGraph)

- **Session isolation** via per-session Firecracker microVMs — stronger than typical ECS/EKS container-level isolation for multi-tenant workloads ([02-runtime-microvm.md](./02-runtime-microvm.md)).
- **Managed cold start** on platform V2 (~2s regardless of image size) instead of hand-tuned container warm pools.
- **Built-in Identity** (OAuth M2M/OBO/user-delegated, KMS-backed credential signing) instead of self-built secret rotation and token refresh logic.
- **Gateway** as a single governed entry point for tools — centralizes auth, rate limiting, guardrails (via Policy), and dynamic tool addition without redeploy (see [06-agent-registry-and-mcp.md](./06-agent-registry-and-mcp.md)).
- **Managed Memory** with built-in extraction strategies (semantic, preference, summarization, episodic) instead of a self-built vector store + extraction pipeline, if you choose to adopt it alongside (or instead of) LangGraph's own state.
- **Unified observability + Evaluations/Optimization loop**: automated prompt/tool-description recommendations, A/B testing, batch evaluation, failure-pattern insights — all usable with LangGraph's own instrumentation, no Harness required.
- **Managed scaling** without operating ECS/EKS/ASG yourself; AWS absorbs the provisioning/teardown.
- **CI/CD via AgentCore CLI v1.0 / CDK**: `agentcore deploy`, direct resource commands, a thin CDK app with stable L2 constructs — see [10-enterprise-best-practices.md](./10-enterprise-best-practices.md).

## What you lose / must rebuild

- **Harness's zero-code conveniences are entirely off the table** — no managed memory-by-default, no skills catalog toggle, no lifecycle hooks, no interactive-shell debugging unless you reimplement equivalents yourself or adopt them piecemeal via direct SDK calls against Memory/Gateway from inside your LangGraph container.
- **No native multi-agent primitive to adopt "for free"** — your existing supervisor/hop-counter logic stays exactly as complex as it is today; AgentCore doesn't simplify multi-agent orchestration itself, only the infrastructure underneath it (see [04-multi-agent-orchestration.md](./04-multi-agent-orchestration.md)).
- **Vendor lock-in increases** in proportion to how deeply you adopt Gateway/Identity/Memory APIs inside the LangGraph app — those become AWS-specific SDK calls inside otherwise-portable LangGraph code. Runtime hosting itself (wrap-and-containerize) is comparatively low-lock-in since it's "just a container with an entrypoint."
- **Session/duration limits apply even if you don't change anything else**: 8-hour hard cap on microVM sessions, 2 vCPU/8 GB per session, 1 GB session storage. If the current self-hosted LangGraph deployment runs long-lived processes or bigger-than-8GB workloads, that's a real constraint, not a paperwork item — mitigations are the Instances compute type (up to 14 days, bigger/GPU instances) or redesigning the agent to be resumable across sessions using Memory.
- **A real cutover event, not a toggle**: there's no documented in-place migration of a running self-hosted LangGraph service into Runtime — it's parallel deployment, traffic shift, and decommission of the old infrastructure.

## Recommended POC scope (building on the existing Strands POC)

The POC at `/Users/sanjeevgulati/personal-repos/agentcore-poc` currently runs a single-tool Strands agent on Runtime. To actually validate the LangGraph migration path specifically (rather than just validating Runtime-in-general via Strands), a second POC branch should:
1. Take a trivial LangGraph graph (2–3 nodes, one conditional edge) and wrap it with the same `BedrockAgentCoreApp`/`@app.entrypoint` pattern.
2. Deploy it with `agentcore deploy` (CLI v1.0) and confirm cold start behavior on platform V2.
3. Add one Gateway target (e.g., a Lambda tool) and confirm the LangGraph agent can discover/call it without redeploying the container — validating the claim in [06-agent-registry-and-mcp.md](./06-agent-registry-and-mcp.md).
4. Wire up LangGraph + AgentCore Memory for one long-term fact, to validate the integration claim in [07-gateway-identity-memory.md](./07-gateway-identity-memory.md) firsthand rather than taking the docs' word for it.
