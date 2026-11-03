# Multi-Agent Orchestration on AgentCore

## Does AgentCore have a native supervisor/orchestrator primitive?

**Not as a dedicated "multi-agent" API.** There is no `CreateSupervisor` or `CreateMultiAgentWorkflow` resource type in the AgentCore API surface based on the service list in [What is Amazon Bedrock AgentCore?](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) (Harness, Runtime, Memory, Gateway, Identity, Browser, Code Interpreter, Observability, Payments, Evaluations, Optimization, Policy, Registry). Multi-agent systems are **composed** from these primitives rather than provided as a first-class abstraction. This should be stated plainly rather than guessed at: AWS's public docs do not advertise a native supervisor construct as of Nov 2026.

## The patterns AWS actually supports, concretely

### 1. Agent-to-Agent (A2A) protocol support in Runtime
AWS announced native **A2A protocol** support in AgentCore Runtime (see [Introducing agent-to-agent protocol support in Amazon Bedrock AgentCore Runtime](https://aws.amazon.com/blogs/machine-learning/introducing-agent-to-agent-protocol-support-in-amazon-bedrock-agentcore-runtime/)). A2A is a Linux Foundation-governed, client-server protocol (reached v1.0 in 2026) where any agent can act as client or server, agents publish "Agent Cards" describing their capabilities, and a supervisor agent calls sub-agents as A2A peers. This is the closest thing to a "native" multi-agent primitive AWS offers — but it's a wire protocol and SDK support, not a managed orchestration service; **you still write the supervisor logic**.

### 2. Gateway as the sub-agent invocation layer
Since Jun 2026, **Gateway can front other Runtime agents directly as targets** ("Gateway: AgentCore Runtime targets are now generally available" — [release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)). A supervisor agent calls its sub-agents through Gateway, which gives you unified auth, guardrails (via Policy), and observability on every supervisor→sub-agent hop, plus the option to enforce that a Runtime agent only accepts invocations that originate from the Gateway (`aws:SourceArn` / `allowedWorkloadConfiguration`). Gateway's **HTTP passthrough targets** (also Jun 2026) explicitly list "application-to-application (A2A) agents" and "external MCP servers" as intended use cases.

### 3. Direct Runtime-to-Runtime invocation
Nothing stops a supervisor agent (hosted on Runtime or Harness) from calling `InvokeAgentRuntime` directly against a sub-agent's Runtime endpoint, bypassing Gateway. This is the simplest pattern and is effectively "agents-as-tools" — the supervisor treats each sub-agent as a tool call.

### 4. Strands "Agents-as-Tools" pattern
Third-party guidance (e.g. the LangGraph/AgentCore migration article cited below) explicitly recommends, for new multi-agent builds on AgentCore, using **Strands Agents-as-Tools** on Runtime rather than hand-rolling a graph: "If you do not already have that graph, prefer Strands Agents-as-Tools on Runtime, which has the same AgentCore host and less framework surface." This is a framework-level pattern (Strands SDK), not an AgentCore service feature.

### 5. Step Functions as the orchestration layer
AWS Step Functions now integrates natively with both **Harness** (`InvokeHarness` state, added Jun 2026) and **Gateway** (Step Functions connector target, added Nov 2026). This gives you a visual, stateful workflow engine that can sequence/parallelize multiple harness or gateway-fronted agent calls with human-approval and error-handling steps built in — arguably the most "managed" multi-agent orchestration option AWS offers, but it's Step Functions doing the orchestrating, not AgentCore itself.

Sources: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html), [Multi-Agent Orchestration on AWS With AgentCore Runtime](https://dzone.com/articles/multi-agent-orchestration-on-aws), [Agent2Agent (A2A) Protocol on AWS](https://medium.com/@rameshrajach/agent2agent-a2a-protocol-on-aws-building-interoperable-multi-agent-systems-agentcore-first-d8d2f55863ee), [Amazon Bedrock AgentCore Implementation Guide Part 4: Multi-Agent Orchestration](https://hidekazu-konishi.com/entry/amazon_bedrock_agentcore_implementation_guide_part4_multi_agent.html)

## Summary table

| Pattern | Who builds the orchestration logic | What AgentCore provides |
|---|---|---|
| A2A protocol, Runtime↔Runtime | You (supervisor code) | Transport/protocol support, Agent Cards, discovery |
| Gateway Runtime targets | You | Auth, guardrails, observability, source enforcement on the hop |
| Gateway HTTP passthrough (A2A/external MCP) | You | Unified endpoint, policy, session stickiness |
| Strands Agents-as-Tools | You (in Strands code) | Hosting (Runtime), nothing orchestration-specific |
| Step Functions + Harness/Gateway states | You (Step Functions definition) | A managed state machine to call into AgentCore resources |

## Implication for an existing LangGraph supervisor

LangGraph's explicit graph/supervisor/hop-counter pattern (nodes, edges, conditional routing, cycle guards) has **no direct equivalent to port to** inside AgentCore — AgentCore doesn't ship a graph engine. Two realistic options:
1. **Keep LangGraph as the orchestration layer**, deploy the whole graph as a container to Runtime (see [09-migration-from-langgraph.md](./09-migration-from-langgraph.md)), and call out to Gateway/Identity/Memory for cross-cutting concerns. This preserves 100% of existing supervisor/hop-counter logic.
2. **Rewrite the supervisor using Strands Agents-as-Tools** if you want to also exploit Harness for the leaf agents — but this means abandoning LangGraph's graph semantics for Strands' tool-calling semantics, which is a real rewrite of orchestration logic, not a lift-and-shift.

Given there's an existing production LangGraph agent, option 1 is the only non-destructive path.
