# AWS Bedrock AgentCore — Enterprise Adoption Research (Nov 2026)

Research for evaluating a migration of an existing **production LangGraph agent** to AWS Bedrock AgentCore. Written from AWS's public devguide, release notes, and a handful of independently-verified third-party technical write-ups — not training-data recall, since AgentCore changed substantially through 2026 (Harness GA Jun 2026, CLI v1.0 Oct 2026, Agent Registry GA Aug 2026).

## Contents

1. [00-overview.md](./00-overview.md) — what AgentCore is, the services list, key 2026 dates
2. [01-architecture.md](./01-architecture.md) — how Runtime/Harness/Gateway/Identity/Memory relate; managed vs. self-built
3. [02-runtime-microvm.md](./02-runtime-microvm.md) — Firecracker microVM isolation, cold start, platform V1 vs V2, limits
4. [03-harness.md](./03-harness.md) — the managed config-driven agent loop, when to use it
5. [04-multi-agent-orchestration.md](./04-multi-agent-orchestration.md) — supervisor patterns; no native multi-agent primitive
6. [05-strands-vs-langgraph.md](./05-strands-vs-langgraph.md) — the critical finding: Harness = Strands-only, Runtime = framework-agnostic
7. [06-agent-registry-and-mcp.md](./06-agent-registry-and-mcp.md) — Registry (discovery) vs. Gateway (hot-swappable execution)
8. [07-gateway-identity-memory.md](./07-gateway-identity-memory.md) — the three services a LangGraph shop can adopt standalone
9. [08-scalability-and-ops.md](./08-scalability-and-ops.md) — scaling, observability, cost, regions
10. [09-migration-from-langgraph.md](./09-migration-from-langgraph.md) — concrete migration path, what's drop-in vs. rework
11. [10-enterprise-best-practices.md](./10-enterprise-best-practices.md) — security, CI/CD, versioning, cost control

## Decision table

| Option | What it means | Fit for this org (LangGraph, production, supervisor/multi-agent) |
|---|---|---|
| **Adopt AgentCore fully (Harness)** | Rewrite the agent's orchestration as Harness config, abandon LangGraph | **Not recommended.** Harness is powered by Strands Agents and has no documented path to run a LangGraph graph. This is a rewrite dressed up as a migration — you'd be throwing away working production orchestration logic (including hop-counter/supervisor guards) to gain config-driven convenience you don't strictly need. |
| **Adopt Runtime only (keep LangGraph)** | Containerize the existing LangGraph app, deploy to AgentCore Runtime; optionally adopt Gateway/Identity/Memory incrementally | **Recommended starting point.** Runtime is explicitly framework-agnostic and lists LangGraph by name. This preserves 100% of existing orchestration logic while gaining managed microVM isolation, platform-V2 cold starts, built-in Identity/Memory/Gateway if desired, and the Evaluations/Optimization loop (which has first-class LangGraph instrumentation support independent of hosting choice). |
| **Stay on self-hosted LangGraph** | No change | Defensible if the org has no pressing need for managed multi-tenant session isolation, managed OAuth/credential handling, or the evaluation/optimization tooling, and is cost- or lock-in-sensitive. AgentCore adds real value (isolation, ops surface, evaluation tooling) but is not solving a problem this org currently lacks a working answer for — it's an infrastructure upgrade, not a capability unlock, unless multi-tenant isolation or managed OAuth is an active pain point. |
| **Hybrid (Runtime + Gateway + Identity + Memory, LangGraph orchestration retained)** | Adopt the infrastructure services piecemeal, keep LangGraph as the brain | **Best long-term fit if moving at all.** AgentCore's own docs stress these services work "together or independently." Gateway in particular gives a real, verified capability gap-filler: dynamic tool/MCP-server addition without agent redeploy (via `tools/list` re-discovery), centralized OAuth and rate limiting, and Policy-layer guardrails outside agent code — all valuable regardless of orchestration framework. |

**Bottom line recommendation: do not adopt Harness for this agent. Pursue the hybrid path — deploy the existing LangGraph container to Runtime, and adopt Gateway/Identity/Memory incrementally based on which self-built piece (tool integration sprawl, OAuth/credential management, or memory/state) is currently costing the most engineering time.** Validate with the POC plan in [09-migration-from-langgraph.md](./09-migration-from-langgraph.md) before committing production traffic.

## Headline findings (most decision-relevant)

1. **Harness cannot run LangGraph.** It's explicitly "powered by Strands Agents" with an "export to Strands code" escape hatch — there is no config path to plug in a different orchestration engine. Confirmed from AWS's own Harness doc and independently corroborated by third-party migration analysis. This rules out full-platform adoption without a rewrite.
2. **Runtime is genuinely framework-agnostic** — AWS's own service description names LangGraph, CrewAI, LlamaIndex, Google ADK, and OpenAI Agents SDK alongside Strands as supported on Runtime. The existing agent can be containerized and hosted with a thin wrapper (`@app.entrypoint`), no orchestration rewrite required.
3. **There is no native multi-agent/supervisor primitive in AgentCore.** Multi-agent patterns are composed from Gateway (Runtime targets, HTTP passthrough for A2A), direct Runtime-to-Runtime calls, the A2A protocol (v1.0, Linux Foundation), or Step Functions — AgentCore provides transport/hosting/guardrails for the hops, not the orchestration logic itself. The existing LangGraph supervisor/hop-counter logic has nothing to "port to" and should simply be kept as-is inside the container.
4. **Agent Registry is a discovery/governance catalog, not a runtime hot-swap mechanism.** The actual hot-swap capability — adding/removing a tool or MCP server without redeploying the calling agent — belongs to **Gateway** (via standard MCP `tools/list` re-discovery), not Registry. Registry sits on top as an org-wide "what exists and is it approved" catalog, with Aug 2026 GA adding AWS Organizations auto-detection and cross-account RAM sharing.
5. **Platform V2 (GA Sep 2026) is a hard requirement for interactive use cases** — V1 cold starts run 5.4–30s vs. V2's ~2s via Firecracker snapshot-restore — but V2 must be explicitly selected (V1 is still the default if `platformVersion` is omitted) and reportedly costs more per unit; this is an easy default-configuration trap to fall into during a POC-to-prod transition.
6. **Session hard limits are real engineering constraints, not fine print**: 8-hour max session duration and 2 vCPU/8 GB per session on standard microVMs. Long-running or compute-heavy agent workloads need the newer **Instances** compute type (up to 14 days, GPU instances, your own EC2 quotas) or a redesign around resumability.
