# Reference Architecture: Multi-Agent RM Assistant for a Bank (CRM, Risk, Onboarding, SharePoint, cross-department agents)

**Scenario:** A Relationship Manager (RM) uses a web UI to ask questions and trigger actions,
e.g. *"Summarise client X's exposure, open onboarding items and last three meetings, and draft
a review note."* Answering needs several domain agents (CRM, Risk platform, Onboarding/KYC), bank
documents in **SharePoint**, and possibly agents owned by **other departments** or built in
**Microsoft Copilot Studio**.

**How this doc is organised:** Part A lists AWS-documented building blocks and AWS's own
financial-services guidance. Part B is the **recommended design**: our synthesis of those AWS
facts into one architecture. It is a design proposal to validate in the POC, not an AWS-published
blueprint. No third-party sources are used. Companion docs:
[18-sharepoint-and-enterprise-knowledge.md](./18-sharepoint-and-enterprise-knowledge.md) and
[19-interop-microsoft-copilot-and-cross-department-agents.md](./19-interop-microsoft-copilot-and-cross-department-agents.md).
Researched Nov 2026.

---

# Part A: What AWS documents (sources at the end)

## A1. AWS's own guidance on multi-agent patterns in financial services

AWS for Industries, *"Agentic AI in Financial Services: Choosing the Right Pattern for
Multi-Agent Systems"* (Dec 17 2025):

| Pattern | AWS's description | FS examples AWS gives |
|---|---|---|
| **Workflow** (sequential) | "valuable for regulated industries where audit trails and systematic task breakdown are essential" | AML/KYC (identity verification → enhanced due diligence) |
| **Graph** (hierarchical / supervisor) | Clear chain of responsibility; the coordinator is a single point of failure, which "necessitates robust failover mechanisms and monitoring systems in critical financial applications" | Loan underwriting: supervisor over credit, fraud, risk, policy agents |
| **Swarm** (mesh) | Fault tolerant, but "success depends on balancing emergent behavior benefits against regulatory compliance" | Equity research, trade settlement |
| **Loop** | Iterative refinement; "careful attention must be paid to termination conditions" | Credit scoring, algorithmic trading |

AWS-named anti-pattern: **"Large Singleton"**, one agent with too many tools. Fix: *"ensuring
agents have focused, small-scope responsibilities."*

## A2. AWS's KYC reference (closest published banking multi-agent architecture)

AWS Architecture Blog, *"Modernizing KYC with AWS serverless solutions and agentic AI"* (Apr 23
2026, with IBM Consulting; AWS says "for reference purposes only"):
- A **supervisor agent on AgentCore Runtime** coordinates five domain sub-agents (Identity
  Verification, Document Analysis, Fraud Detection, Compliance & Risk, Customer Experience) and
  decides parallel vs sequential execution.
- **Core banking, case management and risk/AML systems** are reached as tools defined with
  **OpenAPI schemas and Lambda targets behind AgentCore Gateway**.
- *"AgentCore Identity manages authentication and authorization for agents and their tool
  access"*, which restricts which sub-agents may call which tools.
- **Confidence-based human review**: low confidence (<75%) escalates to human review; 75–95%
  triggers extra verification.
- Audit via **CloudTrail and CloudWatch**; knowledge base (OpenSearch Serverless + S3) grounds
  decisions in policy documents; connectivity to on-prem via **Direct Connect / Site-to-Site VPN**.

## A3. AWS's multi-account (department / line-of-business) pattern

AWS ML Blog, *"Build a multi-account AI agent with AgentCore Gateway and MCP"* (Sep 24 2026):
- **Hub-and-spoke**: a central platform account runs the Gateway (hub); each line of business runs
  its own MCP server in its own account (spoke). Onboarding a new LOB = "adding a Gateway target".
- **Data stays in the LOB account.** The tool returns "the specific result the tool produced, not
  the raw dataset."
- Gateway uses **OAuth M2M credentials from AgentCore Identity** outbound. LOB servers validate the
  token; AWS recommends `allowedWorkloadConfiguration` = Gateway ARN so they accept only Gateway
  traffic.
- **Policy (Cedar) enforced at the Gateway**: *"Because the outbound call uses M2M, user-level
  authorization is enforced here at the Gateway."*
- Bedrock Guardrails for PII redaction on input and output; Agent Registry used for discovery.

## A4. Building blocks (details in earlier docs)

| Need | AWS building block | See |
|---|---|---|
| Host each agent (any framework, incl. LangGraph) | AgentCore **Runtime** | [02](./02-runtime-microvm.md), [05](./05-strands-vs-langgraph.md) |
| Agent ↔ agent calls | **A2A** on Runtime (OAuth 2.0 or IAM auth; Agent Cards); Gateway **Runtime targets**; Gateway **HTTP passthrough** for external A2A agents | [04](./04-multi-agent-orchestration.md) |
| Bank system APIs as tools | Gateway **OpenAPI / Lambda / MCP** targets; Private CA for internal TLS | [07](./07-gateway-identity-memory.md) |
| SharePoint documents | **Bedrock Managed Knowledge Base** SharePoint connector with document-level ACLs, exposed as a **Gateway connector target** | [18](./18-sharepoint-and-enterprise-knowledge.md) |
| RM sign-in | Runtime/Gateway inbound **JWT authorizer**; AWS documents **Microsoft Entra ID** discovery-URL setup | [19](./19-interop-microsoft-copilot-and-cross-department-agents.md) |
| Act on behalf of the RM downstream | Identity **OBO** / user-delegated / M2M flows | [07](./07-gateway-identity-memory.md) |
| Who may call which tool | AgentCore **Policy** (Cedar) at Gateway | [11](./11-guardrails.md) |
| PII / content safety | **Bedrock Guardrails** | [11](./11-guardrails.md) |
| Conversation and RM preferences | AgentCore **Memory** | [07](./07-gateway-identity-memory.md) |
| Discover approved agents/tools across accounts | **Agent Registry** (RAM cross-account sharing) | [06](./06-agent-registry-and-mcp.md) |
| Deterministic multi-step processes | **Step Functions** (Harness and Gateway integrations) | [04](./04-multi-agent-orchestration.md) |
| Streaming chat UI with generative UI and approvals | **AG-UI protocol on Runtime** (SSE event stream; SigV4 or OAuth 2.0; CopilotKit React sample with human-in-the-loop) | below |
| Quality and audit | Observability, **Evaluations**, CloudTrail | [08](./08-scalability-and-ops.md), [12](./12-evaluations.md) |

**AG-UI on Runtime** (AWS ML Blog, Jun 30 2026): Runtime supports three protocols. *"MCP connects
agents to tools, A2A connects agents to other agents, and AG-UI connects agents to users."* With
the AG-UI flag, AgentCore proxies requests unchanged to the container (`POST /invocations`,
`GET /ping`, port 8080). Events such as `TEXT_MESSAGE_CONTENT`, `TOOL_CALL_START`,
`TOOL_CALL_RESULT`, `RUN_FINISHED` stream over SSE. The CopilotKit sample shows the agent pausing
mid-run to render an input component (human-in-the-loop). Works with Strands, **LangGraph**, CrewAI.

---

# Part B: Recommended design (our synthesis; validate in POC)

## B1. Architecture

```
 RM (browser)                 Microsoft Teams / M365 Copilot (optional, see doc 19)
     │ Entra ID sign-in (OIDC)            │ Copilot Studio agent ──A2A──┐
     ▼                                    │                             │
 RM Web UI (React + AG-UI client) ────────┘                             │
     │ JWT (Entra)                                                      │
     ▼                                                                  ▼
 ┌─────────────────────── Platform account (hub) ─────────────────────────────────┐
 │ AgentCore Runtime: RM ORCHESTRATOR agent (LangGraph, AG-UI + A2A endpoints)     │
 │   - intent routing, plan, merge answers, citations, approvals                   │
 │   - Memory (session + RM preferences)   - Guardrails (PII)                      │
 │            │ MCP (JWT / OBO)                                                    │
 │            ▼                                                                    │
 │ AgentCore GATEWAY  ── Policy (Cedar): which RM role/agent may call which tool   │
 │   ├─ Runtime target ─────► CRM agent        (CRM team account)                  │
 │   ├─ Runtime target ─────► Risk agent       (Risk team account)                 │
 │   ├─ Runtime target ─────► Onboarding agent (Ops account) ─► Step Functions     │
 │   ├─ HTTP passthrough ───► other-department A2A agents / Copilot Studio agent  │
 │   ├─ Managed KB target ──► Bedrock Managed Knowledge Base ◄── SharePoint (ACLs) │
 │   └─ OpenAPI/Lambda/MCP ─► read-only bank APIs (Direct Connect / VPN)           │
 │ Registry (catalog of approved agents/tools)  Observability + Evaluations        │
 └─────────────────────────────────────────────────────────────────────────────────┘
```

## B2. Key decisions and why

1. **Use the graph (supervisor) pattern for the RM assistant; use the workflow pattern for
   onboarding.** RM questions vary, so a supervisor routes to domain agents. Onboarding is a
   regulated, ordered process, so make it a Step Functions workflow (or the KYC-style supervisor)
   that the onboarding agent *starts and reports on*. Don't let the LLM improvise the process
   (AWS A1/A2).
2. **One agent per domain, owned by the domain team** (CRM, Risk, Onboarding), each on its own
   Runtime, ideally in the team's own AWS account (AWS A3 hub-and-spoke). This avoids the "Large
   Singleton" anti-pattern, keeps data in the owning account, and lets teams release
   independently.
3. **Every hop goes through the Gateway.** Central auth, Policy, rate limits, and observability.
   Domain Runtimes accept only Gateway traffic (`allowedWorkloadConfiguration` / `aws:SourceArn`).
   New agents or tools are added as targets without redeploying the orchestrator.
4. **Keep the orchestrator in LangGraph on Runtime** (consistent with this repo's main
   recommendation, [README](./README.md)). Harness is not needed. Domain teams may use Strands or
   LangGraph; A2A and Runtime targets make the framework irrelevant to the caller.
5. **SharePoint through the Managed Knowledge Base connector with ACLs on**, exposed as a Gateway
   connector target. The RM's verified email is injected **by code, not by the model** (see B3 and
   [doc 18](./18-sharepoint-and-enterprise-knowledge.md)).
6. **Read and write are separate tools, and writes need approval.** For example `get_client_exposure`
   (read) and `submit_onboarding_case` (write). Writes require an explicit RM confirmation in the UI
   (AG-UI human-in-the-loop) and are additionally restricted by Policy. Mirrors AWS's KYC
   confidence-threshold escalation.
7. **Other departments and Microsoft agents connect over open protocols**: A2A for opaque agents
   owned by someone else, MCP for tools/data. Details in [doc 19](./19-interop-microsoft-copilot-and-cross-department-agents.md).

## B3. Identity flow (the part most likely to go wrong)

1. RM signs in to the UI with **Entra ID**. The UI receives a JWT.
2. Orchestrator Runtime validates the JWT (**custom JWT authorizer**, Entra discovery URL,
   allowed audience = Entra application ID). AWS states it supports Entra v1.0/v2.0 tokens
   "that do not have any custom claims", so **confirm in the POC that the claims you need (e.g. email,
   group or role) are present in a token AgentCore accepts.**
3. Orchestrator calls Gateway with the user's token, or a token obtained via **OBO**, so
   Policy can authorise each tool call against the calling principal. Validate in the POC exactly
   which identity attributes your Cedar policies can see. If a hop must use M2M credentials,
   user-level authorisation has to be enforced at the Gateway, as AWS notes in A3.
4. For SharePoint retrieval, the orchestrator's **tool wrapper code** adds
   `userContext.userId = <email claim from the validated JWT>`. The LLM never supplies it.
   AWS: the Gateway "does not populate `userContext` from the caller's IAM identity" and ACL
   filtering "is not a security boundary".
5. Domain agents call their own systems with OBO tokens where the system supports per-user
   authorisation, otherwise M2M plus Policy.

## B4. Data, memory and compliance

- **Memory namespaces per RM** (and per client if needed), so one RM's context never leaks into
  another's session. Set retention/TTL to match the bank's records policy.
- **Guardrails** for PII on orchestrator input and output. The knowledge-base target's
  `AgenticRetrieveStream` tool can also carry a Guardrail (`policyConfiguration.guardrailConfiguration`).
- **Audit trail**: CloudTrail plus per-agent trace log groups. Keep trace IDs in the UI response so
  any answer can be traced to the agents, tools and documents used.
- **Citations required** in every answer that uses documents or system data. The Managed KB
  agentic retrieval tool returns citations natively.
- **Region / data residency**: services in this design are available in different sets of AWS
  Regions. Bedrock Managed Knowledge Bases, in particular, are offered in a **subset** of Regions,
  and some features (third-party connectors, ACLs, the Gateway KB target) are not available in AWS
  GovCloud. Before committing, confirm each service against the bank's data-residency requirements
  using AWS's live Region pages: [Managed KB regions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-regions.html),
  [AgentCore regions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)
  ([08](./08-scalability-and-ops.md)).

## B5. Build order (fits the POC plan in [13](./13-poc-plan.md))

| Step | Deliverable | Proves |
|---|---|---|
| 1 | Orchestrator on Runtime + AG-UI chat UI + Entra sign-in | End-to-end identity and streaming |
| 2 | Gateway + one read-only CRM tool (OpenAPI target) | Tool governance, Policy on RM role |
| 3 | SharePoint Managed KB with ACLs on 1–2 sites, as Gateway target | Permission-trimmed answers with citations |
| 4 | Split CRM and Risk into separate Runtime agents behind Gateway | Multi-agent routing, cross-account |
| 5 | Onboarding: Step Functions workflow + write tool with UI approval | Safe actions, human-in-the-loop |
| 6 | One A2A integration (another department, or Copilot Studio) | Interop ([doc 19](./19-interop-microsoft-copilot-and-cross-department-agents.md)) |
| 7 | Evaluations on a fixed RM question set; failure analysis | Accuracy baseline before pilot |

**Test explicitly:** an RM without access to a SharePoint site gets no content from it; an RM
role without risk entitlement is denied by Policy; a write never executes without confirmation;
a domain agent being down produces a partial answer that says so instead of a guess.

## Sources (AWS)

- [Agentic AI in Financial Services: Choosing the Right Pattern for Multi-Agent Systems (AWS for Industries, Dec 2025)](https://aws.amazon.com/blogs/industries/agentic-ai-in-financial-services-choosing-the-right-pattern-for-multi-agent-systems/)
- [Modernizing KYC with AWS serverless solutions and agentic AI (AWS Architecture Blog, Apr 2026)](https://aws.amazon.com/blogs/architecture/modernizing-kyc-with-aws-serverless-solutions-and-agentic-ai-for-financial-services/)
- [Build a multi-account AI agent with AgentCore Gateway and MCP (AWS ML Blog, Sep 2026)](https://aws.amazon.com/blogs/machine-learning/build-a-multi-account-ai-agent-with-agentcore-gateway-and-mcp/)
- [Build generative UI for AI agents on AgentCore with the AG-UI protocol (AWS ML Blog, Jun 2026)](https://aws.amazon.com/blogs/machine-learning/build-generative-ui-for-ai-agents-on-amazon-bedrock-agentcore-with-the-ag-ui-protocol/)
- [Introducing A2A protocol support in AgentCore Runtime (AWS ML Blog)](https://aws.amazon.com/blogs/machine-learning/introducing-agent-to-agent-protocol-support-in-amazon-bedrock-agentcore-runtime/)
- [Amazon Bedrock Managed Knowledge Bases as Gateway connector target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-managed-kb.html)
- [Managed knowledge base supported regions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-regions.html)
- [Microsoft Entra ID as identity provider for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-microsoft.html)
- [Runtime inbound and outbound auth](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html)
