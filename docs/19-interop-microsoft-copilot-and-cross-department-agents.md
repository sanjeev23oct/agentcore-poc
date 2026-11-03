# Interop: Microsoft Copilot / Copilot Studio and Agents from Other Departments

**How this doc is organised:** Part A uses AWS sources. Part B uses **Microsoft's own official
documentation** (Microsoft Learn) for the Microsoft side. That is vendor documentation about its
own product, kept separate from AWS content. Part C is our recommended approach. No independent
third-party sources are used. Researched Nov 2026.

---

# Part A: AWS side

## A1. Exposing an AgentCore agent to other platforms (A2A server)

- AgentCore Runtime supports the **A2A protocol**: the agent exposes HTTP endpoints *"using
  JSON-RPC 2.0 over HTTP/S or Server-Sent Events"* and publishes an **Agent Card**, a JSON file
  advertising identity, capabilities, endpoints and auth requirements.
- Works with any framework (AWS names Strands, OpenAI Agents SDK, **LangGraph**, Google ADK, Claude
  Agents SDK).
- Inbound auth: **OAuth 2.0** (JWT) or **AWS IAM**.
- **Microsoft Entra ID as the JWT issuer for Gateway and Runtime inbound auth is documented by
  AWS**: configure the tenant's OpenID discovery URL
  (`https://login.microsoftonline.com/<tenantId>/.well-known/openid-configuration` for v1.0 tokens,
  `.../<tenantId>/v2.0/.well-known/openid-configuration` for v2.0); allowed audience = the Entra
  Application ID; for v2.0 access tokens set `accessTokenAcceptedVersion=2` in the app manifest;
  for v1.0 access tokens request the scope `<entra-application-id>/.default`.
- **Limitation (AWS wording):** supported are Entra *"v1.0 and v2.0 Access and ID tokens that do
  not have any custom claims."* Validate in the POC that the tokens your clients (including
  Copilot Studio) send meet this.
- Entra can also be an **outbound** credential provider in AgentCore Identity, so agents can call
  Entra-protected resources.

## A2. Calling agents and tools from other teams or platforms

- **Gateway HTTP passthrough targets** front "application-to-application (A2A) agents" and
  "external MCP servers" (release notes, Jun 2026), so external agents get the same auth, Policy
  and observability as internal ones.
- **Gateway Runtime targets** for agents other teams host on AgentCore.
- **Gateway MCP server targets** for teams that expose tools rather than agents.
- **Agent Registry** to catalog and approve agents/MCP servers across the organisation, with AWS
  Organizations auto-detection and **cross-account sharing via AWS RAM** ([06](./06-agent-registry-and-mcp.md)).
- AWS's **hub-and-spoke** multi-account pattern: each line of business keeps data in its own
  account and is onboarded by "adding a Gateway target" ([17](./17-reference-architecture-bank-rm-multi-agent.md)).
- AWS Well-Architected **Agentic AI Lens** (AGENTPERF04-BP02), desired outcome: *"You use MCP for
  tool integration, A2A for agent-to-agent coordination, and streaming protocols for real-time
  agent-user interactions."* It lists *"implementing custom communication protocols instead of
  adopting standards like MCP and A2A"* as an anti-pattern.

---

# Part B: Microsoft side (from Microsoft Learn, vendor documentation)

## B1. Copilot Studio calling an external A2A agent (e.g. your AgentCore agent)

*"Connect to an agent over the Agent2Agent (A2A) protocol"* (Microsoft Learn, updated Oct 2026):
- In Copilot Studio: **Agents → Add agent → A2A agent**, enter the **endpoint URL** (the message
  endpoint, *not* the Agent Card URL). Name and description auto-fill from a card at the standard
  `.well-known` location.
- Authentication options: **None, API key, OAuth 2.0** (client ID, secret, auth URL, token URL,
  refresh URL).
- *"Because A2A connections use the custom connector infrastructure, you can also use them to
  connect to A2A agents running on-premises or within a virtual network."*
- **What Copilot sends:** each A2A message includes a `contextId`, locale and the **full chat
  history** (not only the latest message) in metadata. That is a data-sharing consideration for a
  bank.
- Microsoft's note: when connecting external agents *you* are responsible for data flows, quality,
  permissions, observability, identity, traceability and human oversight.
- Microsoft's integration guide: **A2A** for agents with their own reasoning hosted elsewhere;
  **MCP servers** for tools/resources; **custom connectors** for plain APIs; **Activity Protocol**
  for Microsoft 365 Agents SDK agents.

## B2. External agents calling a Copilot Studio agent (the reverse direction)

*"Connect clients to your agent with the MCP and A2A channels"* (Microsoft Learn, updated Oct 2026):
- Marked *"prerelease documentation and is subject to change"*; the channels are *"available only
  in early release cycle environments."*
- Clients authenticate *"with Microsoft Entra ID on behalf of the signed-in user"*: an Entra app
  registration with the **delegated** permission `MCS.InvokeAsA2A` (or `MCS.InvokeAsMCP`) and the
  OAuth 2.0 **authorization code flow**. Copilot Studio checks each user's access to the agent.
- Implication: a calling orchestrator needs a **user-delegated** token for the RM, not an
  app-only (M2M) token.
- Microsoft notes usage may consume **Copilot Credits** (usage-based billing).

## B3. Microsoft's multi-agent guidance

*"Multi-agent patterns"* (Microsoft Learn, Jul 2026):
- Use **MCP for tool and data access**; use **A2A for cross-platform agent-to-agent** messaging,
  requiring agents to publish agent cards and use A2A's task/artifact model.
- *"A2A is better suited for scenarios where the agents are or must be opaque to each other. For
  example ... agents owned by two different engineering organizations."*
- Require **human approvals for high-impact cross-agent actions**; enforce policy and auditing at
  the control plane (Microsoft names Agent 365).

**Both vendors give the same rule: MCP for tools and data, A2A for agents owned by others.**

---

# Part C: Recommended approach (our synthesis; validate in POC)

## C1. Decision table: how to connect each kind of agent

| Counterpart | Connect via | Why |
|---|---|---|
| Another department's agent on **AgentCore** | **Gateway Runtime target** (cross-account), listed in Registry | Native, IAM/JWT, Policy, no protocol translation |
| Another department's agent on **another framework/cloud** | Their **A2A** endpoint as a **Gateway HTTP passthrough target** | Opaque agent with its own reasoning; Gateway still governs the hop |
| A department that only has **data/APIs** | **MCP server / OpenAPI target** on Gateway | It's a tool, not an agent. Keep reasoning in your orchestrator |
| **Copilot Studio / M365 Copilot** calling *your* RM agents (RMs work in Teams) | Expose your orchestrator (or a narrower agent) as an **A2A server on Runtime**, Entra-issued JWT; add it in Copilot Studio as an **A2A agent** with OAuth 2.0 | Both sides document this path. Your agent keeps its own reasoning and controls |
| *Your* orchestrator calling a **Copilot Studio** agent | Copilot Studio **A2A channel** (**preview**, early-release only) via Gateway HTTP passthrough | Possible, but don't put a preview channel on a production critical path |
| Copilot Studio needing only **bank tools** (not a full agent) | Copilot Studio **MCP server** connection to your Gateway's MCP endpoint (Microsoft labels "Add an MCP server ... as a tool" **preview**) | Reuses the same governed tools; *verify Gateway inbound auth matches what Copilot Studio supports* |

## C2. Governance contract for every cross-department agent

Before an agent is added as a target, require a **Registry record** with:
owner and support contact; data classification of inputs and outputs; whether it acts on behalf of
the user (OBO) or as itself (M2M); allowed callers; read-only vs write capabilities; SLA and
timeout behaviour; Agent Card / tool schema version; evaluation results on an agreed test set.
Curators approve before the Gateway target is created. Policy then encodes "allowed callers" and
"write needs approval".

## C3. Identity across AWS and Microsoft

- Where the bank's workforce identity is already **Entra ID** (implied by SharePoint Online and
  Copilot use), use it as the single user identity provider. AWS documents Entra as the JWT issuer
  for Runtime and Gateway inbound auth, and the SharePoint connector already uses Entra.
- Carry the **RM's identity end-to-end** (JWT / OBO) so Policy and downstream systems authorise
  the human, not just the calling agent. Where a hop is M2M (common for A2A between departments),
  enforce user-level rules at the Gateway before the call.
- **Copilot sends full chat history over A2A** (B1). Decide whether your agent may log or store it.
  Trim or ignore what it doesn't need, and cover it in the data-sharing agreement between
  departments.

## C4. Risks to flag to stakeholders

- **Preview dependencies:** Copilot Studio's inbound A2A/MCP channels and its MCP-server tool
  connection are preview. AWS Agent Registry is generally available (AgentCore release notes).
  Re-check the status of every feature at build time; statuses change.
- **Chained agents multiply latency and failure modes.** Set timeouts per hop and return partial,
  clearly labelled answers. Long-running work belongs in async tasks (MCP Tasks extension, Step
  Functions), not in a synchronous chat turn.
- **Accountability:** when an answer combines your agent with another department's, the UI should
  show which agent produced which part (citations per agent), so errors can be routed to the owner.
- **Prompt-injection across agents:** treat another agent's output as untrusted input. Run it
  through Guardrails and never let it trigger write tools without RM confirmation.

## Sources

AWS:
- [Introducing A2A protocol support in AgentCore Runtime](https://aws.amazon.com/blogs/machine-learning/introducing-agent-to-agent-protocol-support-in-amazon-bedrock-agentcore-runtime/)
- [Microsoft Entra ID identity provider for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-microsoft.html)
- [Runtime inbound and outbound auth](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html)
- [Gateway inbound authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-inbound-auth.html)
- [AgentCore release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)
- [Build a multi-account AI agent with AgentCore Gateway and MCP](https://aws.amazon.com/blogs/machine-learning/build-a-multi-account-ai-agent-with-agentcore-gateway-and-mcp/)
- [Agentic AI Lens: AGENTPERF04-BP02 protocol-based agent communications](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentperf04-bp02.html)

Microsoft (vendor documentation):
- [Connect to an agent over the A2A protocol (Copilot Studio)](https://learn.microsoft.com/en-us/microsoft-copilot-studio/add-agent-agent-to-agent)
- [Connect clients to your agent with the MCP and A2A channels (preview)](https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/publication-channels-mcp-agent-to-agent)
- [Multi-agent patterns (Microsoft Learn)](https://learn.microsoft.com/en-us/agents/architecture/multi-agent-patterns)
