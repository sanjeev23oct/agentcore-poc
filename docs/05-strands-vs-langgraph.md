# Strands vs LangGraph on AgentCore — the critical distinction

This is the single most consequential technical fact for the migration decision, so it gets its own doc.

## The short answer

| | Runtime | Harness |
|---|---|---|
| **LangGraph supported?** | **Yes** — deploy your graph as a container (or direct code deploy); Runtime is explicitly "framework-agnostic." | **No** — Harness's loop is built on and powered by Strands Agents; there's no way to swap in a different orchestration engine. |
| **Strands supported?** | Yes, same as any framework | Yes — it's native |
| **CrewAI / LlamaIndex / Google ADK / OpenAI Agents SDK?** | Yes, all listed explicitly as supported frameworks on Runtime | No |

## Evidence

AWS's own service description for Runtime:

> "AgentCore Runtime works with custom frameworks and any open-source framework, including CrewAI, LangGraph, LlamaIndex, Google ADK, OpenAI Agents SDK, and Strands Agents, any foundation model..."

Source: [What is Amazon Bedrock AgentCore?](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

AWS's own service description for Harness:

> "The harness is powered by [Strands Agents](https://strandsagents.com/), the open-source agent framework from AWS."
> "...export to Strands code and run it on AgentCore runtime when configuration isn't enough."

Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)

**Directly confirmed against AWS's harness-vs-runtime comparison page (Nov 2026)** — this was the one gap in the original research pass, now closed. The page's feature grid has a row literally titled "Choice of agent framework," marked `❌ No` for Harness and `🔵 Custom` for Runtime, and a second row, "Non-agent-loop patterns (graph, workflow style)," also marked `❌ No` for Harness. This is as explicit as AWS gets: Harness cannot run a different orchestration framework, and cannot run graph/workflow-style control flow (which is exactly what a LangGraph graph is) under any configuration. Source: [AgentCore harness vs. Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html).

Third-party technical analysis independently reaches the same conclusion:

> "Harness does not support LangGraph... Harness if configuration is enough, Runtime if you bring your own orchestration code."

Source: [LangGraph + AWS Bedrock AgentCore (2026)](https://www.factualminds.com/blog/langgraph-aws-bedrock-agentcore-2026/)

## What "framework-agnostic" means in practice on Runtime

Runtime does not execute your framework's graph itself — it hosts **a container (or a direct-code-deploy ZIP) that you write**, which happens to use LangGraph internally. The integration points are:
- You wrap your invocation entrypoint with the `BedrockAgentCoreApp`/`@app.entrypoint` decorator from the `bedrock_agentcore` Python SDK (the same SDK used in this repo's `agent.py` POC, just with `strands.Agent` swapped for a LangGraph `graph.invoke()` call).
- Your container must listen on port 8080, expose a health endpoint, and (per current guidance) build for ARM64.
- Runtime does not know or care that LangGraph is inside — it just invokes your entrypoint function per request/session.

This means **Runtime support for LangGraph is "bring your own container that uses LangGraph," not "LangGraph-native hosting."** There is no special LangGraph integration beyond what any Python framework gets by being invocable from a function.

## Where Evaluations DOES have LangGraph-specific support

Separately from hosting, **AgentCore Evaluations has first-class LangGraph instrumentation support** — it recognizes LangGraph's OpenTelemetry/OpenInference spans (via `opentelemetry-instrumentation-langchain` or `openinference-instrumentation-langchain`, Python and TypeScript) and extracts prompts/responses/tool calls from them for scoring. This is a real, documented integration — LangGraph is one of only two frameworks (alongside Strands) explicitly supported since Evaluations GA in March 2026, later expanded (Jul 2026) to also cover OpenAI Agents, LlamaIndex, Google ADK, and Claude Agent SDK, and (Sep 2026) their TypeScript equivalents.

Source: [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)

So: **hosting is framework-agnostic (Runtime), orchestration config is Strands-only (Harness), and evaluation/observability has explicit multi-framework support including LangGraph.**

## Memory's framework integrations

AgentCore Memory documents direct integration points for LangGraph, LangChain, Strands, and LlamaIndex (e.g., an `AgentCoreMemorySaver`/`AgentCoreMemoryStore` pattern referenced by third-party migration guides for wiring LangGraph's checkpointing to AgentCore Memory's long-term store). Source: [Add memory to your agent](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html); integration specifics via [LangGraph + AWS Bedrock AgentCore (2026)](https://www.factualminds.com/blog/langgraph-aws-bedrock-agentcore-2026/). Important nuance from that same source: **don't conflate LangGraph's own checkpointer with AgentCore long-term Memory** — checkpoints are LangGraph's execution-state mechanism; long-term facts/preferences need the separate Memory Store service, keyed by `actor_id`/`thread_id`.

## Bottom line

- The existing LangGraph production agent **can be hosted on AgentCore Runtime with no framework rewrite** — only the deployment wrapper changes.
- It **cannot** move to Harness without a full rewrite of the orchestration logic into Strands/Harness config, which defeats the point of "migrating" the existing agent (it would be a parallel new build, not a migration).
- Gains from Evaluations/Observability's native LangGraph instrumentation are available either way, independent of which hosting option you choose.
