# AWS Agent Registry and MCP — what's stored, and what's actually hot-swappable

## Two different things that are easy to conflate

1. **AWS Agent Registry** — a *discovery/governance catalog*. It stores metadata records describing agents, MCP servers, skills, and custom resources so humans and agents can find them. It is **not** in the tool-execution path.
2. **AgentCore Gateway targets** — the actual mechanism by which an agent gains or loses access to a tool/MCP server/sub-agent at runtime. This **is** in the execution path.

Confusing these two leads to overstating what Registry can do. Registry answers "what exists and is it approved for use"; Gateway answers "what can this specific agent actually call right now."

## What Registry stores and how it works

Per AWS docs, a **registry** has a name, authorization config (IAM or JWT), approval settings, and a set of **registry records**. Each record describes one resource (MCP server, agent, skill, or custom type) with searchable metadata. The typical workflow:

1. Admin creates a registry, sets auth/approval policy.
2. Publisher creates records, submits for approval.
3. Curator approves/rejects/deprecates records.
4. Consumers (human or agent) search/browse approved records, or query the registry's **native MCP endpoint** directly from an MCP-compatible client.

Source: [AWS Agent Registry: Discover and manage agents, tools, and resources](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html)

Capabilities added through 2026:
- **Aug 2026 GA**: AWS Organizations auto-detection (automatically catalogs Runtimes/Gateways across member accounts, stays in sync as resources change), customer-managed KMS key encryption, PrivateLink support, cross-account sharing via AWS RAM (ReadOnly/Consumer/Publisher/Admin managed permissions).
- **Oct 2026**: two new discovery APIs (`ListDiscoverableRegistryRecords`, `BatchGetDiscoverableRegistryRecord`), region expansion to US East (Ohio), Frankfurt, London, Canada Central.

Source: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Is Registry hot-swappable at runtime? — Honest answer: that's the wrong question

**Re-verified directly against the live Registry devguide page (Nov 2026).** AWS's own description confirms the catalog framing exactly: "AWS Agent Registry is a fully managed discovery service that provides a centralized catalog for organizing, curating, and discovering resources... enable both human users and AI agents to discover the right tools and agents through hybrid search, catalog browsing, and a native MCP endpoint." The documented access pattern is strictly **search and discovery** (direct API/SDK calls, or its MCP endpoint) — there is no mention anywhere on the page, its "Key capabilities," "How it works," or "Related services" sections of agents pulling live tool configuration from the Registry at inference time, or of a Gateway "subscribing" to a Registry category for auto-sync. The "Related services" section explicitly frames Registry as upstream of Gateway and Runtime ("Deploy and run the agents and MCP servers that you register," "Convert APIs and Lambda functions into MCP-compatible tools that can be registered") — i.e., Registry describes resources that Gateway/Runtime actually execute, it is not itself in that execution path. **This confirms the original claim: no documented "subscribe your Gateway to this Registry category and it auto-syncs targets" feature exists as of Nov 2026.**

## What IS hot-swappable: Gateway targets

This is where real dynamic tool-swapping happens, and it's well documented:

- Gateway operates in **aggregation mode**: it presents a single MCP endpoint whose `tools/list` response combines every attached target's tools.
- **Adding a new Gateway target (e.g., a new MCP server, Lambda, or OpenAPI target) does not require redeploying the calling agent.** The agent discovers the new tools on its *next* `tools/list` call — this is the standard MCP protocol behavior, and AWS's gateway preserves it. Practitioner write-ups describe this exact pattern for onboarding a new line-of-business MCP server: add a Gateway target, agent sees new tools on next poll.
- Removing a target similarly removes its tools from the next `tools/list` without touching the agent's deployment.
- Gateway now supports **MCP Sessions** (May 2026), **response streaming/SSE**, **elicitation pass-through**, **sampling messages**, and (Oct 2026) the **MCP Tasks extension** for long-running async tool calls — all of which make Gateway a genuinely full-featured, stateful MCP proxy, not just a static aggregator.
- Gateway also added **configurable rate limits** (Aug 2026) scoped per caller/target/tool/model, propagating to the data plane fleet within 30 seconds — another "change config, not code" lever.

Sources: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html), [AWS AgentCore Gateway MCP target issue (re:Post)](https://repost.aws/questions/QUoyIgV3v4Qg2Q0S4XmlCEcg/aws-agentcore-gateway-mcp-target-issue), [Govern MCP Tools at Scale with Kiro and AgentCore Gateway](https://builder.aws.com/content/3CS1jTWHngGW3IxFXCjcP2T9l8B/govern-mcp-tools-at-scale-with-kiro-and-agentcore-gateway)

## Net finding — correcting the hypothesis in the task brief

The task brief hypothesized Registry might support "hot-swapping MCP targets without redeploy." Based on the docs actually reviewed: **that capability exists, but it belongs to Gateway, not Registry.** Registry is the catalog you search to decide what to add; Gateway is the thing you add it to, and Gateway target changes take effect live without redeploying the agent, because tool discovery (`tools/list`) is dynamic by MCP design. This is a meaningful nuance for the decision doc — if the goal is "let agents discover and use new tools without redeployment," the answer is **"adopt Gateway,"** and Registry is an optional governance layer on top for org-wide discoverability, not a substitute for Gateway.

## Multi-agent discovery via Registry

Registry can catalog **agents** (Runtime endpoints) alongside tools, which is relevant to the multi-agent pattern in [04-multi-agent-orchestration.md](./04-multi-agent-orchestration.md): a supervisor could, in principle, search Registry to find an approved sub-agent's Runtime ARN, then invoke it directly or via a Gateway Runtime target. This is a discovery-time convenience, not a runtime dynamic-dispatch mechanism — the supervisor still needs code to decide when to search and how to invoke what it finds.
