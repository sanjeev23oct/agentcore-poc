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

## A5. Harness vs Runtime: AWS's own comparison (key rows)

AWS's *"AgentCore harness vs. Runtime"* page: Harness is *"a managed agent harness - the orchestration
loop itself is provided, powered by Strands Agents"*; *"switching a model or adding a tool is a config
change, not a redeploy."* Runtime is *"a serverless hosting environment. You bring agent code -
written in any framework or no framework ... The orchestration loop is yours."* The harness *"runs
inside Runtime"*. There is no separate Harness charge (see [03](./03-harness.md)).

| Capability | Harness | Runtime (your code) |
|---|---|---|
| Memory, Gateway tools, MCP tools, observability, execution limits, streaming responses, outbound identity | ✅ configuration only | 🔵 you write code |
| Inbound auth (IAM / OAuth), session isolation, VPC, versioning and endpoints | ✅ | ✅ |
| **Choice of agent framework** (e.g. LangGraph) | ❌ No | 🔵 Yes, your code |
| **Non-agent-loop patterns (graph, workflow style)** | ❌ No | 🔵 Yes, your code |
| **Bidirectional streaming** | ❌ No | 🔵 Yes, your code |
| Lifecycle hooks (e.g. allow/deny before a tool call) | 🟣 config + Lambda | 🔵 your code |

**Related AWS integrations (release notes):**
- **Step Functions + Harness**: *"run multiple harnesses in parallel or sequence, and wrap them
  with human approval, error handling, or conditional routing steps."*
- **Gateway Step Functions connector**: exposes state machines to agents as MCP tools. *"Your agents
  decide when to run a workflow and what input to pass, and the state machine decides which steps run
  and in what order."* Standard workflows record each step; task tokens support human-in-the-loop.
- **Reachability caveat:** AWS documents Gateway **Runtime** targets and **A2A on Runtime**. As of
  Nov 2026 we found **no documented Gateway target type or A2A endpoint specifically for a
  harness**. A harness is invoked with its `InvokeHarness` API (directly, from a Lambda, or from Step
  Functions). Re-check before design sign-off.

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
 │   ├─ Runtime target ─────► CRM insight agent (CRM team account)                 │
 │   ├─ Step Functions ─────► Onboarding/KYC workflow (Ops account; Harness steps) │
 │     connector                                                                   │
 │   ├─ HTTP passthrough ───► other-department A2A agents / Copilot Studio agent  │
 │   ├─ Managed KB target ──► Bedrock Managed Knowledge Base ◄── SharePoint (ACLs) │
 │   └─ OpenAPI/Lambda/MCP ─► read-only CRM and risk platform APIs (DX / VPN)      │
 │ Registry (catalog of approved agents/tools)  Observability + Evaluations        │
 └─────────────────────────────────────────────────────────────────────────────────┘
```

## B2. Which build option for each use case

**Rule: pick the least custom option that meets the need**, in this order:

| Option | What it is | Choose it when |
|---|---|---|
| **1. No agent: a tool** | API or function exposed as a Gateway target (OpenAPI / Lambda / MCP) | The answer is a deterministic lookup or calculation. No reasoning needed |
| **2. No custom agent: managed retrieval** | Bedrock Managed KB as a Gateway connector target ([18](./18-sharepoint-and-enterprise-knowledge.md)) | Question answering over documents, with citations and permissions |
| **3. Workflow** | Step Functions, exposed to agents via the Gateway connector; LLM steps can be harnesses | The process is regulated or fixed-order, needs audit of each step or human approval |
| **4. Harness** | Configuration-only agent (Strands loop managed by AWS) | A standard tool-calling assistant is enough, invoked directly or as a workflow step |
| **5. Runtime + your code** | LangGraph / Strands / any framework on Runtime | You need graph or custom control flow, a specific framework, bidirectional streaming, AG-UI with in-flow approvals, or an A2A / Gateway Runtime-target endpoint other agents can call |
| **6. Connect, don't build** | Existing agent reached via A2A / Gateway target | Another team already has the capability ([19](./19-interop-microsoft-copilot-and-cross-department-agents.md), [20](./20-reusability-first-department-to-enterprise.md)) |

**Applied to this bank's use cases:**

| Use case | Recommended option | Why (AWS facts in A5 unless noted) | Avoid |
|---|---|---|---|
| **RM orchestrator** (routes questions, merges answers, citations, approvals in UI) | **5. Runtime + LangGraph** | Graph/supervisor pattern and framework choice are "❌ No" on Harness; AG-UI sample with human-in-the-loop is on Runtime (A4); keeps existing LangGraph skills ([09](./09-migration-from-langgraph.md)) | Harness: can't run a graph |
| **Client / CRM lookups** ("show client X's profile, products, last contacts") | **1. Tool** (OpenAPI/Lambda target, read-only) | Deterministic data; no LLM needed to fetch it | Building a "CRM agent" just to call one API |
| **CRM insight agent** reused by other departments ("summarise relationship, suggest next best action") | **5. Runtime** (Strands or LangGraph), published as Gateway Runtime target / A2A | Must be callable by other agents and teams; those endpoints are documented for Runtime | Harness, *if* it must be an A2A peer or Gateway Runtime target (reachability caveat, A5) |
| **Risk exposure / limits** | **1. Tool** for the numbers (risk platform API), plus the orchestrator to explain them | Risk figures must come from the system of record, never be computed by an LLM | Letting a model calculate exposure |
| **Risk analysis assistant** for a single team (Q&A over risk reports plus a few tools) | **4. Harness** | Standard tool-calling loop; memory, Gateway tools, limits, observability by configuration | Custom code with no custom need |
| **Onboarding / KYC process** | **3. Step Functions workflow**, with **Harness steps** for document reading or summarising, exposed to the orchestrator via the Gateway Step Functions connector | Ordered, auditable, human approval via task tokens; AWS FS guidance uses workflow for KYC (A1) | Letting an LLM decide the process order |
| **Policy / product document Q&A** (SharePoint) | **2. Managed KB** via Gateway (`AgenticRetrieveStream`) | Citations and SharePoint permission filtering built in; no agent to maintain | Custom RAG pipeline or self-managed vector store |
| **Another department's existing agent** | **6. Connect** (A2A via Gateway HTTP passthrough, or Gateway Runtime target) | Reuse, not rebuild; Gateway still governs the hop | Re-implementing their logic |
| **RMs who work in Teams / M365 Copilot** | **6. Connect**: Copilot Studio calls your orchestrator over A2A | Documented by both vendors ([19](./19-interop-microsoft-copilot-and-cross-department-agents.md)); no second UI to build | Rebuilding the agent inside Copilot Studio |
| **Quick internal POC** (one team, few tools) | **4. Harness** | Fastest; AWS documents export to Strands code if config becomes limiting ([03](./03-harness.md)) | Starting with a full custom build |
| **Existing production LangGraph agent** | **5. Runtime** | Runtime is framework-agnostic; Harness is not ([05](./05-strands-vs-langgraph.md)) | Rewriting it as a Harness |

**Signals a Harness agent should move to Runtime:** it needs branching or cycles beyond a tool loop,
a specific framework, bidirectional streaming, or must be exposed as an A2A peer / Gateway Runtime
target. AWS's documented path is export to Strands code ([03](./03-harness.md)).

## B3. Key decisions and why

1. **Use the graph (supervisor) pattern for the RM assistant; use the workflow pattern for
   onboarding.** RM questions vary, so a supervisor routes to domain capabilities. Onboarding is a
   regulated, ordered process, so make it a Step Functions workflow (with Harness steps where an LLM
   is useful) that the orchestrator starts and tracks through the Gateway Step Functions
   connector. Don't let the LLM improvise the process (AWS A1/A2, A5).
2. **One capability per domain, owned by the domain team** (CRM, Risk, Onboarding), ideally in the
   team's own AWS account (AWS A3 hub-and-spoke). Each capability uses the least custom option
   from B2: a tool where no reasoning is needed, an agent only where it is. This avoids the "Large
   Singleton" anti-pattern, keeps data in the owning account, and lets teams release
   independently.
3. **Every hop goes through the Gateway.** Central auth, Policy, rate limits, and observability.
   Domain Runtimes accept only Gateway traffic (`allowedWorkloadConfiguration` / `aws:SourceArn`).
   New agents or tools are added as targets without redeploying the orchestrator.
4. **Keep the orchestrator in LangGraph on Runtime** (consistent with this repo's main
   recommendation, [README](./README.md)). Harness can't run a graph (A5), but fits single-team
   assistants and workflow steps (B2). Domain teams may use Strands or LangGraph; A2A and Runtime
   targets make the framework irrelevant to the caller.
5. **SharePoint through the Managed Knowledge Base connector with ACLs on**, exposed as a Gateway
   connector target. The RM's verified email is injected **by code, not by the model** (see B4 and
   [doc 18](./18-sharepoint-and-enterprise-knowledge.md)).
6. **Read and write are separate tools, and writes need approval.** For example `get_client_exposure`
   (read) and `submit_onboarding_case` (write). Writes require an explicit RM confirmation in the UI
   (AG-UI human-in-the-loop) and are additionally restricted by Policy. Mirrors AWS's KYC
   confidence-threshold escalation.
7. **Other departments and Microsoft agents connect over open protocols**: A2A for opaque agents
   owned by someone else, MCP for tools/data. Details in [doc 19](./19-interop-microsoft-copilot-and-cross-department-agents.md).

## B4. Identity flow (the part most likely to go wrong)

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

## B5. Data, memory and compliance

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

## B6. Build order (fits the POC plan in [13](./13-poc-plan.md))

| Step | Deliverable | Proves |
|---|---|---|
| 1 | Orchestrator on Runtime + AG-UI chat UI + Entra sign-in | End-to-end identity and streaming |
| 2 | Gateway + one read-only CRM tool (OpenAPI target) | Tool governance, Policy on RM role |
| 3 | SharePoint Managed KB with ACLs on 1–2 sites, as Gateway target | Permission-trimmed answers with citations |
| 4 | Add risk platform tools, and a CRM insight agent on Runtime in the CRM team's account, behind Gateway | Multi-agent routing, cross-account |
| 5 | Onboarding: Step Functions workflow (Harness steps) via the Gateway connector + write tool with UI approval | Safe actions, human-in-the-loop |
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
- [AgentCore harness vs. Runtime (feature grid)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)
- [AgentCore release notes (Step Functions connector; Step Functions + harness)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)
- [Invoke AgentCore harness with Step Functions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-step-functions.html)
- [AWS Step Functions as Gateway connector target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-step-functions.html)
