# Reusability: Building the First Department's Agents So Other Teams Can Reuse Them

**Question this answers:** when one department builds agentic AI for the first time, what should
become a **shared service**, what should become a **reusable template or library**, what should
become a **standard**, and what is **learning** to pass on, so the second and third departments
build faster and more safely instead of starting again?

**How this doc is organised:** Part A uses AWS sources only (AWS Prescriptive Guidance, the AWS
Well-Architected Agentic AI Lens, AWS blogs). Part B is our recommended categorisation and plan,
derived from Part A and from the design in [17](./17-reference-architecture-bank-rm-multi-agent.md).
It is a proposal to agree with architecture and risk teams, not AWS-published guidance. No
third-party sources are used. Researched Nov 2026.

---

# Part A: What AWS says about reuse

## A1. Agents as reusable, discoverable services

AWS Prescriptive Guidance, *Operationalizing agentic AI on AWS*, "Preparing the business":
- *"Agents become modular, reusable, and discoverable services that accelerate innovation."*
- Enterprise value comes when agents can *"discover, invoke, and collaborate with one another"*.
  This *"means defining standards for agent registration, authentication, and capability
  exchange"*, and *"mirrors the shift from monoliths to microservices"*.
- *"Create centers of excellence to share best practices, tooling patterns, and reusable assets."*
- Establish **AgentOps teams** (AI/ML practitioners, domain specialists, architects, engineers,
  product owners, compliance leads, platform architects) that own an agent's whole lifecycle.
  Provision and release with infrastructure as code and automated deployment (AWS names AWS CDK
  and AWS CodePipeline).
- *"Governance must be embedded into the agent architecture from the first day."*

## A2. What AWS treats as shared enterprise components

AWS Prescriptive Guidance, *Agentic AI architecture in the enterprise*, defines **three core
service categories** agents consume:
- **Model access**: *"controls access to foundation models with policy enforcement, safety
  measures including guardrails, and cost tracking/allocation capabilities."*
- **Tools**: *"manages discovery and secure execution of tools"*, with authorisation *"so tools can
  be used only by the right actors and for the right context."*
- **Knowledge bases**: access to enterprise data with *"role-based access control ... to enforce
  least privilege and need-to-know principles."*

*"Observability, security and discoverability span multiple layers."*

## A3. Well-Architected Agentic AI Lens best practices on reuse

| Best practice | What AWS recommends |
|---|---|
| **AGENTOPS04-BP01** Tool registry and catalog | A centralised registry as *"a single authoritative source for tool capabilities, current versions, and operational status."* Anti-pattern: *"each team to manage tool definitions independently without a shared registry, producing duplicate tools"*. Start with AgentCore Gateway before building anything custom. Enforce **documentation standards** (purpose, parameter schemas, error codes, rate limits, auth) as an onboarding gate; use **semantic versioning** and **deprecation workflows**. |
| **AGENTOPS03-BP04** Portfolio governance (risk: **High**) | A central catalog of *"every agent, owner, capabilities, dependencies, lifecycle state, cost profile, and business value"*, using **AWS Agent Registry**. Teams *"discover existing agents before building new ones"*. A lightweight CI/CD gate flags duplicates (*"heavy approval processes encourage bypass"*). EventBridge notifies dependants of changes; **quarterly portfolio reviews** of utilisation, cost, redundancy, health. |
| **AGENTSUS01-BP01** Specialised agents with explicit boundaries (risk: **High**) | One atomic capability per agent, each with a timeout, memory ceiling and token budget. *"Reusable specialized agents are exposed through a shared tool layer, so one well-bounded agent serves many parent workflows"* via **AgentCore Gateway**, so development cost is amortised. Budgets cascade from parent to child; **Policy** (Cedar) rejects calls exceeding declared limits. |
| **AGENTPERF04-BP02** Protocols | MCP for tools, A2A for agent-to-agent; custom protocols are an anti-pattern ([19](./19-interop-microsoft-copilot-and-cross-department-agents.md)). |

## A4. AWS's multi-account reuse pattern

AWS ML Blog, *Build a multi-account AI agent with AgentCore Gateway and MCP* (Sep 2026): a central
**platform account** runs the Gateway; each line of business keeps its data and MCP server in its
own account; onboarding a new line of business is *"adding a Gateway target."* Details in
[17](./17-reference-architecture-bank-rm-multi-agent.md).

---

# Part B: Recommended categorisation (our synthesis; agree with architecture and risk teams)

## B1. Five categories of reuse

| # | Category | What it means | Who owns it | How others reuse it |
|---|---|---|---|---|
| 1 | **Shared platform services** | Run once, consumed by many; centrally secured and operated | Platform / AgentOps team | Call it (endpoint, target, API) |
| 2 | **Shared business capabilities** | Domain agents, tools and knowledge bases other departments call | The owning domain team | Add as a Gateway target / A2A peer after Registry approval |
| 3 | **Reusable building blocks** | Code, templates and infrastructure modules teams copy or import | Platform team / Centre of Excellence | Version-pinned library or template repo |
| 4 | **Standards and guardrails** | Rules every agent must meet to go live | Architecture, security, risk, compliance | Checklist and automated gates in CI/CD |
| 5 | **Learning and knowledge** | Decisions, evidence and lessons from the first build | Centre of Excellence | Playbooks, design records, training |

**Rule of thumb for deciding the category:**
- Must be **identical for everyone, holds credentials or data, or needs central audit**? Make it a
  **service** (1 or 2).
- Teams need the **same starting point but legitimately different details**? Make it a **building
  block** (3).
- It's a **requirement**, not an implementation? Make it a **standard** (4).
- It's **judgement or experience**? Capture it as **learning** (5).

## B2. What the first department should produce in each category

### 1. Shared platform services (build once, run centrally)

| Service | Based on | Why central |
|---|---|---|
| **Gateway hub per environment** (dev / test / prod) | AgentCore Gateway (A4) | One governed front door; new tools and agents added as targets, no redeploys |
| **Identity integration**: Entra inbound authorizer configuration and outbound credential providers | AgentCore Identity | Credentials and token handling should exist once, audited |
| **Model access with guardrails and cost allocation** | Bedrock, Bedrock Guardrails, Gateway inference targets | AWS A2: policy, safety and cost tracking on model use |
| **Policy (Cedar) engine and base policy set** | AgentCore Policy | Default-deny, read/write separation, budget limits enforced outside agent code |
| **Agent and tool catalog** | AWS Agent Registry (cross-account sharing) | AWS A3: discover before building; ownership and lifecycle |
| **Observability and evaluation pipeline** | AgentCore Observability, Evaluations, CloudWatch | Same trace, audit and quality evidence for every agent |
| **Enterprise knowledge bases** (e.g. bank policy library from SharePoint) | Bedrock Managed KB with ACLs, as a Gateway target ([18](./18-sharepoint-and-enterprise-knowledge.md)) | Permission-aware; avoids each team crawling the same sites |

### 2. Shared business capabilities (owned by the domain, consumed by others)

From the RM assistant ([17](./17-reference-architecture-bank-rm-multi-agent.md)), candidates that
other departments are likely to need:
- **Client/CRM lookup agent or tools** (read-only first)
- **Risk/exposure agent or tools**
- **Onboarding/KYC status and workflow** (Step Functions behind a Gateway tool)
- **Policy-document Q&A** over SharePoint

Each published capability needs a **contract** ([19](./19-interop-microsoft-copilot-and-cross-department-agents.md) C2):
owner, data classification, read vs write, OBO vs M2M, allowed callers, SLA/timeouts, versioned
schema, evaluation results. Following AWS AGENTSUS01-BP01, keep each one **narrow and bounded**,
since narrow capabilities are the ones others can reuse.

**Don't share the RM orchestrator itself** as a capability. It encodes RM-specific intent and UX.
Share what it calls, plus the template it was built from (category 3).

### 3. Reusable building blocks (templates and libraries)

- **Agent template repository**: a LangGraph-on-Runtime skeleton with health check, Entra
  authentication, tracing, structured errors, timeouts and token budgets already wired in.
- **Infrastructure-as-code modules** (AWS names CDK in A1): Runtime, Gateway target, Memory, KB,
  Policy, alarms.
- **Tool-wrapper library**: identity injection (e.g. setting KB `userContext` from the verified
  token, never from the model), timeouts, retries, standard error format, PII redaction hooks.
- **Policy and Guardrail templates**: standard Cedar policies (read-only by default, write needs
  approval) and Guardrail configurations.
- **UI shell**: AG-UI chat front end with citations, approval prompts and trace links.
- **Evaluation harness**: test-set format, evaluator configuration, pass thresholds.
- **A2A Agent Card and MCP tool-description templates** meeting the documentation standard.

### 4. Standards and guardrails (mandatory to go live)

- **Tool and agent documentation standard** (AWS AGENTOPS04-BP01): purpose, schemas, error codes,
  rate limits, auth.
- **Registry record contract** and **approval workflow**, including a duplicate check before build
  (AGENTOPS03-BP04).
- **Versioning and deprecation policy**: semantic versions, notice period, multiple active versions
  during migration.
- **Identity rules**: user identity carried end-to-end; when M2M is allowed; who may set
  `userContext`.
- **Action rules**: read vs write separation; human approval for high-impact actions; no write
  triggered by another agent's output alone.
- **Data rules**: classification per tool; Memory namespaces and retention; what may be logged.
- **Security baseline**: patch tracking for AgentCore SDKs and tools ([14](./14-security-incidents.md));
  sandbox use ([15](./15-built-in-tools.md)).
- **Quality gate**: minimum evaluation scores before promotion ([12](./12-evaluations.md)).
- **Cost tagging and budgets** per agent and department.

### 5. Learning and knowledge (pass on judgement, not just code)

- **Architecture decision records**: e.g. why LangGraph on Runtime rather than Harness; why the Gateway is mandatory.
- **POC evidence pack**: latency, cost per conversation, evaluation scores, failure analysis.
- **Lessons learned**: identity mismatches, ACL behaviour, timeouts across agent chains,
  prompt-injection findings.
- **Reusable evaluation datasets** of realistic, anonymised questions with expected answers.
- **Runbooks**: certificate renewal, credential rotation, incident response for agents.
- **Enablement**: role-based training (AWS A1) for engineers, product owners, risk and
  compliance; a Centre of Excellence that curates categories 3–5.

## B3. Sequencing: what to make reusable *during* the first build

Making everything a shared service up front slows the first delivery. A staged approach:

| When | Do | Category |
|---|---|---|
| **During first build** | Build on Gateway, Identity, Policy, Registry as if they were shared (separate platform account from day one, per AWS A4) | 1 |
| | Write the standards as you meet each decision; record ADRs | 4, 5 |
| | Keep domain tools narrow, documented and registered | 2 |
| **At first go-live** | Extract the agent template, IaC modules and tool-wrapper library from working code | 3 |
| | Publish the evidence pack and lessons learned | 5 |
| **When the second department starts** | Onboard them as a Gateway/Registry consumer; reuse capabilities via contracts | 1, 2 |
| | Stand up the Centre of Excellence and portfolio review cadence (AWS: quarterly) | 4, 5 |

**Signals reuse is working:** the second department ships with no new platform components; most
of its tools come from the Registry; no duplicate agents are flagged at the CI/CD gate.

## B4. Operating model needs (often missed)

- **Ownership and funding**: each shared service and capability has a named owner, an SLA, and a
  funding or chargeback model (cost tags). Otherwise "shared" services decay.
- **Change management across teams**: breaking changes follow the deprecation policy; dependants
  are notified (AWS suggests EventBridge events).
- **Single accountable reviewer** for each published capability's data classification and action
  permissions. This matters more as more departments depend on it.

## Sources (AWS)

- [Preparing the business for agentic AI at scale (AWS Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-operationalizing-agentic-ai/preparing-business.html)
- [Agentic AI architecture in the enterprise (AWS Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/govern-architect-agentic-ai/enterprise-architecture.html)
- [AGENTOPS04-BP01 Implement tool registry and catalog management (Agentic AI Lens)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentops04-bp01.html)
- [AGENTOPS03-BP04 Organizational agent portfolio management and governance at scale (Agentic AI Lens)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentops03-bp04.html)
- [AGENTSUS01-BP01 Design specialized agents with explicit resource boundaries (Agentic AI Lens)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsus01-bp01.html)
- [AGENTPERF04-BP02 Implement efficient protocol-based agent communications (Agentic AI Lens)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentperf04-bp02.html)
- [Build a multi-account AI agent with AgentCore Gateway and MCP (AWS ML Blog, Sep 2026)](https://aws.amazon.com/blogs/machine-learning/build-a-multi-account-ai-agent-with-agentcore-gateway-and-mcp/)
