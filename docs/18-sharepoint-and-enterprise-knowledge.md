# SharePoint and Enterprise Knowledge for Agents (Bedrock Managed Knowledge Base + AgentCore Gateway)

**Sources:** AWS documentation only (Bedrock user guide and AgentCore devguide, Nov 2026). Part B
is our recommended setup derived from those docs. No third-party sources used.

---

# Part A: What AWS documents

## A1. The SharePoint connector (Bedrock Managed Knowledge Base)

Connects **SharePoint Online** sites as a data source. Supported (AWS):
- Files and pages from multiple sites (`/sites/`, `/teams/`, `/personal/` URLs; vanity domains OK)
- Auto-detected fields: title, author, created/modified dates
- Include filters by item path and date range
- **Exclude by Microsoft Purview sensitivity label** (default or custom labels)
- **Incremental sync** of added, updated and deleted content
- **Document-level access control (ACLs)**, only with Entra ID App-Only auth

### Authentication options

| Method | Use | ACLs? |
|---|---|---|
| **Entra ID App-Only** (`ENTRA_ID_APP_ONLY`, certificate), **recommended by AWS** | Most data sources | **Yes** |
| User-managed 3LO (`MANAGED_OAUTH2`) | Quick start | No |
| OAuth 2.0 ROPC (`OAUTH2_APP`) | Only if App-Only impossible; **fails with MFA / Conditional Access** | No |

Credentials go in **AWS Secrets Manager**.

### Microsoft permissions by use case (application permissions, admin consent)

| Use case | Microsoft Graph | SharePoint |
|---|---|---|
| Selected sites, no ACLs (least privilege) | `Sites.Selected` | `Sites.Selected` (read per site) |
| Selected sites, **with ACLs** | `Sites.Selected`, `User.Read.All`, `GroupMember.Read.All` | `Sites.Selected` with **fullcontrol** per site |
| All sites, no ACLs | `Sites.Read.All` | `Sites.Read.All` |
| All sites, with ACLs | `Sites.Read.All`, `User.Read.All`, `GroupMember.Read.All` | **`Sites.FullControl.All`** ("Sites.Read.All is not sufficient") |

AWS's note: `Sites.FullControl.All` grants broad access to every site, so use `Sites.Selected`
for least privilege.

## A2. How ACL-aware retrieval works

- **Ingestion** crawls permissions: site memberships and role assignments, library permissions,
  item-level permissions "including unique permissions that break inheritance", and Entra security
  groups, mail-enabled security groups and distribution groups, with nested (transitive)
  memberships resolved.
- **Query time**: you pass a user context (email). Results are filtered to documents the user may
  see. **Deny always overrides allow.**
- **Real-time verification** for SharePoint: each returned document is re-checked live against
  SharePoint, catching permission changes since the last sync.
- **Fails closed**: on any ACL error, documents are withheld, never returned to unauthorised users.
- **Identity = email**, exact match, *"no alias resolution or cross-identity-provider mapping."*
  A mismatch fails silently, so the user just gets no results.
- **Group membership is as fresh as the last sync**; very large groups can lag after sync.
  Per-user access results are eventually consistent, AWS says "typically within about two
  minutes" of a change in SharePoint.
- **ACL setting is permanent** per data source: it can't be added later or removed.
- **Misconfiguration is silent**: AWS notes ACL problems "do not produce explicit errors during
  retrieval". Documents are just omitted. An **expired certificate or revoked admin consent
  denies all users**, so certificate renewal must be an operational runbook item.

**AWS's warning, verbatim:** *"Bedrock Managed Knowledge Base provides ACL-aware filtering, not a
security boundary. Bedrock Managed Knowledge Base does not authenticate end users — your
application is responsible for authenticating users and passing verified identity context."*
AWS also lists email lifecycle (reassigned addresses after an employee leaves) as your
responsibility.

Other connectors with ACL support: OneDrive, Google Drive, Confluence (cloud and Data Center),
ServiceNow (partial real-time), Box, Zendesk, Salesforce, S3 and Custom (customer-supplied ACLs, no
real-time check). Web Crawler has no ACLs.

## A3. Exposing the knowledge base to agents: Gateway connector target

AgentCore Gateway has a **native connector target for Managed Knowledge Bases**. It exposes two MCP
tools:
- **`AgenticRetrieveStream`**: plans a retrieval strategy, runs multiple retrieval steps, can
  expand to full documents, and streams a **synthesized answer with citations**. Admin-set options
  include model, reranking, `maxAgentIteration`, and a **Bedrock Guardrail**.
- **`Retrieve`**: single hybrid search returning passages with source references.

Knowledge base IDs and retrieval settings are **set by the administrator on the target**, so the
agent can't choose other knowledge bases. Selected parameters can be exposed with
`parameterOverrides`. Outbound auth is IAM (Gateway service role).

**Per-user filtering through Gateway:** *"The Gateway does not populate `userContext` from the
caller's IAM identity — your application must supply it explicitly."* AWS instructs: expose
`$.userContext` via `parameterOverrides`, and *"have the calling application (not the model)
include `userContext`."*

## A4. Regions (Managed Knowledge Base)

Managed Knowledge Bases are offered in a **subset** of AWS Regions, and in AWS GovCloud the
third-party connectors (including SharePoint), ACLs and the Gateway KB target are not available.
Check the bank's data-residency requirements against AWS's live
[Supported Regions page](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-regions.html)
before designing around this service.

---

# Part B: Recommended setup for the RM assistant

1. **Auth:** Entra ID App-Only with certificate; **`Sites.Selected` + fullcontrol on only the
   sites in scope** (e.g. product policies, credit policy, RM playbooks). Avoid
   `Sites.FullControl.All` in a bank tenant unless security signs off.
2. **Turn ACLs on at creation.** This can't be changed later. Even for "everyone can read"
   sites, ACLs protect you when someone later restricts a folder.
3. **Exclude sensitive content by Purview label** (e.g. "Highly Confidential", "Board") rather than
   relying only on ACLs.
4. **Inject identity in code.** In the orchestrator's KB tool wrapper, set
   `userContext.userId` from the **email claim of the validated Entra JWT**. Never let the LLM fill
   it, and strip any model-supplied value.
5. **Make the email match.** Confirm the Entra claim you use (`email`, `upn` or
   `preferred_username`) equals the address SharePoint associates with the user. Test with a guest
   or alias user, since mismatches return nothing silently.
6. **Prefer `AgenticRetrieveStream` for RM questions** (multi-part questions, citations
   returned), with a Guardrail attached on the target. Use `Retrieve` when the orchestrator does
   its own synthesis.
7. **Treat "no results" carefully.** ACL failures fail closed and return zero or fewer results. The
   agent should say "I couldn't find accessible documents" rather than answer from general
   knowledge.
8. **Sync schedule:** align incremental sync frequency with how fast policy documents change. Rely
   on real-time ACL verification for permission changes, not sync frequency.
9. **Joiner/mover/leaver:** coordinate with IAM/Entra teams so reassigned emails can't inherit a
   former employee's access (AWS-stated customer responsibility).

**POC test cases:** (a) user with access sees cited answer; (b) user without access to a site
gets nothing from it; (c) permission removed in SharePoint and the document stops appearing within
minutes, before the next sync (real-time check); (d) Purview-labelled document never appears; (e) email mismatch user, to see
the failure mode and how the UI reports it.

## Sources (AWS)

- [Microsoft SharePoint connector (Managed KB)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-ds-sharepoint.html)
- [Document-level access controls for SharePoint](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-ds-sharepoint-acl.html)
- [ACL awareness enablement (Managed KB)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-acl.html)
- [Set up Microsoft Entra ID App-Only authentication for SharePoint](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-sharepoint-entra-setup.html)
- [Managed Knowledge Bases as Gateway connector target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-connector-managed-kb.html)
- [Connect to your knowledge base through AgentCore Gateway](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-gateway-target.html)
- [Managed KB supported regions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-regions.html)
