# AgentCore Harness

## What it is

Harness is the fully managed, **configuration-driven agent loop**. Instead of writing orchestration code, you call `CreateHarness` with a model, system prompt, tools, and skills, then call `InvokeHarness`. AWS runs the model→tool→model loop, memory, identity wiring, filesystem, and observability for you.

> "The managed agent harness in AgentCore turns that work into configuration. You declare what your agent does (model, tools, skills, instructions); AgentCore handles the environment, compute, memory, identity, networking, and observability that turn the config into a running agent."

Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)

**Harness is explicitly powered by Strands Agents** — AWS's own open-source agent framework — and the docs offer an "export to Strands code" escape hatch "when configuration isn't enough." This is the clearest signal in the docs about what Harness actually is under the hood: a hosted, config-surfaced Strands loop, not a framework-neutral orchestration engine.

## Timeline

| Date | Milestone |
|---|---|
| Apr 2026 | Public preview |
| Jun 17, 2026 | **GA** — added built-in memory by default, more model providers (LiteLLM, Bedrock Mantle), AWS skills catalog, evaluations/optimization, unified observability, versioning/endpoints, export-to-Strands |
| Jul–Nov 2026 | Lifecycle hooks, interactive shells, custom OpenAI-compatible endpoints, Consent Portal integration, MCP tool-result metadata streaming |

Source: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## What's configurable

- **Models**: Bedrock, OpenAI, Google Gemini, any LiteLLM-compatible or custom OpenAI-compatible endpoint. You can switch model providers *mid-session* without losing context.
- **Tools**: via Gateway, direct MCP servers, inline functions, or the built-in Browser/Code Interpreter tools.
- **Skills**: an AWS-curated skills catalog toggled on with one switch, or your own from Git/S3.
- **Memory**: on by default since GA; built-in short-term + long-term, or bring your own.
- **Filesystem**: per-session scratch space, plus S3 Files/EFS mounts (up to 5 per harness) for cross-session/cross-harness sharing.
- **Lifecycle hooks** (added Sep 2026): `before_invocation`, `before_tool_call`, `after_tool_call`, `after_invocation` — can call out to Lambda for synchronous allow/deny decisions, or SNS/EventBridge for non-blocking notifications.
- **Interactive shells** (Sep 2026): persistent WebSocket terminal sessions inside the same microVM, up to 10 concurrent per session, 256 KB replay buffer.
- **Custom container**: bring your own image if the managed default environment's dependencies aren't enough — but the agent *loop itself* is still Strands-driven.

Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)

## Harness vs. Runtime — when AWS says to use which

AWS maintains a dedicated comparison page title ([harness-vs-runtime.md](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html), referenced from the Harness topic list) but its content wasn't independently fetched in this research pass — the practical rule derived from the rest of the docs and third-party analysis (see [LangGraph + AWS Bedrock AgentCore (2026)](https://www.factualminds.com/blog/langgraph-aws-bedrock-agentcore-2026/)) is:

| Use Harness if... | Use Runtime directly if... |
|---|---|
| A standard tool-calling loop is sufficient | You need custom control flow — conditional branches, cycles, human-in-the-loop checkpoints, parallel fan-out/fan-in beyond simple tool calls |
| You're fine being Strands-shaped | You have an existing agent in LangGraph, CrewAI, LlamaIndex, Google ADK, OpenAI Agents SDK, or custom code |
| You want memory/identity/skills wired up with zero glue code | You need fine-grained control over state, checkpointing, or multi-agent topology |
| Fast POC-to-prod for a single-agent tool-caller | Framework-agnostic multi-agent systems |

## Cost note

There is **no separate Harness charge** — you pay for the underlying Runtime, Memory, Gateway, etc. that a harness consumes. Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html).

## Bottom line for this evaluation

Because the existing production agent is LangGraph-based, **Harness is not a deployment target for it as-is.** The only way to use Harness would be to throw away the LangGraph graph and re-implement the agent's logic as a Harness config (tools + skills + a system prompt), which is a rewrite, not a migration. See [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md) and [09-migration-from-langgraph.md](./09-migration-from-langgraph.md) for the detailed framework-support evidence and migration path.
