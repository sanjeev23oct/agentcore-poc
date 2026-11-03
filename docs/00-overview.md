# AWS Bedrock AgentCore — Overview

_Research snapshot: November 2026. AgentCore changed heavily through 2026 — Harness went GA June 17, 2026, CLI v1.0 shipped Oct 2026, Agent Registry reached GA in August 2026. This doc set reflects the state of the public AWS docs as of that date; re-verify dates/limits before relying on this for a build decision, since AWS ships changes to this service roughly weekly (see the [release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html))._

## What AgentCore actually is

Amazon Bedrock AgentCore is **not a single product** — it's a set of ten-plus loosely-coupled managed services that can be adopted independently or together:

| Service | One-line purpose |
|---|---|
| **Runtime** | Serverless, session-isolated (microVM) hosting for agent code in any framework/language, as a container or direct code deploy. |
| **Harness** | A fully managed, config-driven agent loop (no code) — built on Strands Agents, runs on top of Runtime. |
| **Gateway** | Turns APIs/Lambda/MCP servers/other agents into a single MCP-compatible endpoint, with auth and rate limiting. |
| **Identity** | OAuth/credential management for agents (M2M, OBO, user-delegated), integrates with existing IdPs. |
| **Memory** | Managed short-term (session) and long-term (cross-session) memory store. |
| **Registry** | A governed discovery catalog for agents, tools, skills, MCP servers across an org. |
| **Browser / Code Interpreter** | Managed sandboxes for web automation and code execution. |
| **Policy** | Cedar-compatible policy engine that gates tool calls at the Gateway layer. |
| **Evaluations / Optimization** | Automated agent quality scoring, batch eval, A/B testing, prompt/tool-description recommendations. |
| **Payments** | Managed wallet/x402/MPP support for agent-initiated microtransactions. |

Source: [What is Amazon Bedrock AgentCore?](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)

AWS's own framing is explicit that these are modular: "you can use together or independently." This matters for the adoption decision — you are not forced into an all-or-nothing platform. A LangGraph shop could, for instance, adopt only Identity + Gateway + Memory and keep its own orchestration and hosting.

## Key dates that matter for this evaluation

| Date | Event |
|---|---|
| Oct 2025 | AgentCore reaches GA (9 regions) |
| Feb 2026 | AgentCore CLI public preview |
| Mar 2026 | AgentCore CLI GA (v0.4.0); Evaluations GA |
| Apr 2026 | Harness public preview; Registry public preview |
| May 2026 | CDK L2 constructs graduate to stable |
| Jun 17 2026 | **Harness GA** |
| Aug 2026 | **Agent Registry GA** (org auto-detection, CMK encryption) |
| Sep 2026 | Runtime platform **V2** GA (Firecracker snapshot-restore cold starts) |
| Oct 2026 | **AgentCore CLI v1.0** (`@aws/agentcore` 1.0.0) — rebuilt CLI, direct resource commands, thin CDK app |
| Nov 2026 (today) | V2 concurrency limit raised to 250 connections/session; `OverheadLatency` metric added |

Source: [Release notes for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## How to read this doc set

- **01-architecture.md** — how the pieces fit together, managed vs. self-built
- **02-runtime-microvm.md** — Runtime execution model (Firecracker microVMs), cold start, limits, V1 vs V2
- **03-harness.md** — the managed agent loop, when to use it
- **04-multi-agent-orchestration.md** — supervisor/sub-agent patterns, what's native vs. DIY
- **05-strands-vs-langgraph.md** — framework support matrix, the critical Harness-vs-Runtime distinction
- **06-agent-registry-and-mcp.md** — Registry vs. Gateway, what's actually hot-swappable
- **07-gateway-identity-memory.md** — the three "bring your own orchestration" services in depth
- **08-scalability-and-ops.md** — scaling, observability, cost, regions
- **09-migration-from-langgraph.md** — concrete migration path for the existing LangGraph agent
- **10-enterprise-best-practices.md** — security, CI/CD, versioning
- **README.md** — index + decision table

See [README.md](./README.md) for the bottom-line recommendation.
