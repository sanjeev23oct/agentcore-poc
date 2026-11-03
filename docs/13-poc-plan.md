# Complete POC Plan

Status: planning document. Phase 0 is the only phase with working code today (`agent.py`).
Everything else here is scoped but not built.

Goal: don't just read AWS's claims about AgentCore — build enough to confirm or refute each
one against your actual LangGraph workload, so the final migration recommendation rests on
evidence, not AWS marketing or a single research pass.

## Why phased this way

Each phase targets one specific claim from the docs (`01`–`12`) that matters for the
migration decision, in order of how much it changes the recommendation if it turns out wrong.
Phase 1 is first because it's the single highest-leverage test: if a real LangGraph graph
does *not* deploy cleanly to Runtime, the whole "hybrid" recommendation collapses and you're
back to full rewrite-or-stay-put.

## Phase 0 — Baseline agent (done)

- Single-tool Strands agent (`agent.py`), Bedrock Claude Haiku, local test via `strands.Agent`.
- Confirms: credentials, model access, Strands SDK, basic Bedrock Converse call.
- Does **not** confirm: Runtime deployment, Harness, any enterprise feature.

## Phase 1 — Deploy the real LangGraph agent to Runtime

**Tests the claim in [09-migration-from-langgraph.md](09-migration-from-langgraph.md):**
Runtime is framework-agnostic and a LangGraph graph needs only a thin wrapper, not a rewrite.

- Take a *real* (or representative-but-safe-to-share) LangGraph graph from your existing agent.
- Wrap it with `BedrockAgentCoreApp` / `@app.entrypoint`, same pattern as `agent.py` but
  invoking `graph.invoke(...)` instead of a Strands agent.
- Containerize per AWS's Runtime container contract (`agentcore configure` / `agentcore launch`,
  or manual Dockerfile if the CLI assumes Strands too tightly — this itself is worth noting).
- Deploy to Runtime, invoke via `InvokeAgentRuntime`.
- **Success criteria:** existing LangGraph nodes/edges/state work unmodified; only the
  entrypoint/transport layer changes.
- **Red flag to watch for:** if LangGraph's own checkpointing/state persistence conflicts with
  Runtime's session model, that's a real migration cost the docs don't currently capture.

## Phase 2 — Gateway: expose a tool as MCP, swap it without redeploy

**Tests the claim in [06-agent-registry-and-mcp.md](06-agent-registry-and-mcp.md):**
Gateway allows adding/removing MCP tools without redeploying the calling agent.

- Stand up an AgentCore Gateway with one target (e.g. a Lambda or an existing internal API).
- Point the Phase 1 agent at the Gateway as its tool source.
- While the agent is running, add a second target to the Gateway and confirm the agent picks
  it up on next `tools/list` call — no redeploy.
- Remove a target, confirm it disappears cleanly (no dangling tool-call errors).
- **Success criteria:** tool set changes are live within one conversation turn, zero agent
  redeploy.

## Phase 3 — Identity: OAuth for a real downstream API

**Tests claims in [07-gateway-identity-memory.md](07-gateway-identity-memory.md).**

- Pick one real downstream system your LangGraph agent currently calls with a static API key
  or service account.
- Reconfigure that call through AgentCore Identity using M2M (machine-to-machine) OAuth.
- **Success criteria:** static credential removed from agent code/config entirely; AgentCore
  handles token acquisition/refresh.
- Stretch: test on-behalf-of (OBO) flow if any downstream call should run as the end user
  rather than a service identity — this is the harder, more valuable case for enterprise.

## Phase 4 — Memory: short-term + long-term

**Tests claims in [07-gateway-identity-memory.md](07-gateway-identity-memory.md).**

- Compare AgentCore's built-in Memory against whatever your LangGraph agent uses today
  (custom checkpointing, a vector store, plain conversation history, etc.).
- Migrate one real use case (e.g. multi-turn session memory) to AgentCore Memory.
- **Success criteria:** feature parity check — does AgentCore Memory do everything your
  current approach does, or is there a gap (e.g. custom retrieval logic, TTL behavior,
  cross-session memory sharing)?

## Phase 5 — Multi-agent: supervisor calling sub-agents

**Tests the claim in [04-multi-agent-orchestration.md](04-multi-agent-orchestration.md):**
no native supervisor primitive — must be composed.

- Split the Phase 1 agent's responsibilities into 2 sub-agents (e.g. a retrieval agent and a
  drafting agent), each deployed as its own Runtime agent.
- Build a supervisor (could be LangGraph's own supervisor pattern, or Strands
  agents-as-tools) that calls both sub-agents via `InvokeAgentRuntime` or Gateway targets.
- **Success criteria:** confirm whether this is straightforward (a few hours) or genuinely
  awkward (fighting the platform) — this directly informs whether "no native primitive" is a
  minor inconvenience or a real cost in the migration decision.

## Phase 6 — Guardrails

**Tests claims in [11-guardrails.md](11-guardrails.md)** (pending verification pass).

- Attach Bedrock Guardrails (or whatever the verification pass confirms is the actual
  mechanism) to the Phase 1 agent.
- Test: denied topic triggers a block, a PII-bearing response gets redacted, a known jailbreak
  prompt gets caught.
- **Success criteria:** guardrail fires correctly, latency overhead is measured (not just
  cited from docs), and confirm whether it's configured per-Runtime-agent or per-Harness-agent
  or both.

## Phase 7 — Evaluations

**Tests claims in [12-evaluations.md](12-evaluations.md)** (pending verification pass).

- Run an offline evaluation against a small labeled test set (prompts + expected
  tool-call trajectory or expected answer) for the Phase 1 agent.
- If online evaluation / Recommendations is accessible, let a short burst of real traffic
  through and check what suggestions (if any) come back for system prompt or tool
  descriptions.
- **Success criteria:** evaluation harness runs end-to-end with real data, not just a docs
  read-through; confirms setup cost (hours, not days) for your team.

## Phase 8 — Scalability + cost probe

**Tests claims in [08-scalability-and-ops.md](08-scalability-and-ops.md).**

- Load-test the Phase 1 agent at a traffic level roughly matching your current production
  peak (or a safe fraction of it).
- Capture: cold start distribution on Platform V2, concurrent session behavior, CloudWatch
  `OverheadLatency` readings, actual AWS bill for the test window.
- **Success criteria:** real numbers to replace the docs' AWS-sourced numbers, specifically
  for your traffic shape — AWS's published limits are a ceiling, not a guarantee of your
  actual latency/cost.

## Phase 9 — Agent Registry (lower priority)

**Tests claims in [06-agent-registry-and-mcp.md](06-agent-registry-and-mcp.md).**

- Register the Phase 1/5 agents and the Phase 2 Gateway targets in AWS Agent Registry.
- Confirm it behaves as a catalog (discoverable, taggable, governable) and not as a runtime
  dependency — i.e. deleting a registry entry should not break a running agent.
- Lower priority because it's a governance/discovery nicety, not a capability gap — worth
  doing last, if at all, for this POC.

## What "complete" means for this POC

Not every phase needs to reach production polish. The bar per phase is: **enough working
code to confirm or correct one specific claim**, with the result written back into the
relevant doc (replace "AWS says X" with "AWS says X; we tested it and observed Y").

## Suggested order for a time-boxed POC

If you can't do all 9 phases, do them in this order — each one is a bigger blocker to the
migration decision if it turns out wrong:

1. Phase 1 (LangGraph on Runtime — the whole recommendation depends on this)
2. Phase 5 (multi-agent — your production use case likely needs this)
3. Phase 2 (Gateway/MCP — operational flexibility claim)
4. Phase 8 (scalability/cost — budget-owner question)
5. Phase 6 (Guardrails — compliance/security sign-off blocker)
6. Phase 3, 4, 7, 9 as time allows
