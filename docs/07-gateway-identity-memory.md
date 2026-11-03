# Gateway, Identity, Memory — the three services a LangGraph shop would adopt independently

These three are the realistic adoption surface for an org that wants to keep LangGraph as its orchestration layer (see [09-migration-from-langgraph.md](./09-migration-from-langgraph.md)) but take advantage of AgentCore's managed infrastructure.

## Gateway: exposing tools/APIs as MCP, auth

Gateway's core jobs, per AWS:
- **Translation** — converts MCP-style agent requests into API/Lambda invocations.
- **Composition** — combines many APIs/functions/tools/agents/model providers behind one endpoint.
- **Security Guard** — inbound OAuth (who can call the gateway).
- **Secure Credential Exchange** — outbound auth (how the gateway authenticates to each target), including token refresh and secure storage.
- **Semantic Tool Selection** — search over large tool catalogs so agents don't need the full tool list in every prompt.
- 1-click integrations with Salesforce, Slack, Jira, Asana, Zendesk.

Source: [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)

**Target types** (as of Nov 2026): MCP server, OpenAPI, Lambda, HTTP passthrough (fronts arbitrary HTTP endpoints, external APIs, A2A agents, external MCP servers), AgentCore Runtime (GA Jun 2026), AWS Step Functions (Nov 2026), inference/model-routing targets (Jun 2026, with InvokeModel wire-format support added Oct 2026 and automatic model fallback on throttling/outage). Private CA support (Oct 2026) lets Gateway trust internally-signed TLS certs on targets without an intermediate ALB.

**Auth**: 3-legged OAuth (3LO) for MCP targets reached GA in Apr 2026, enabling per-end-user tokens for external services requiring consent. JWT or IAM (SigV4) inbound authorization. Gateway can also enforce that a Runtime agent only accepts calls that originated from it (`aws:SourceArn` for SigV4, `allowedWorkloadConfiguration` for JWT) — i.e., Gateway can be the *only* front door to your agent.

**Rate limiting** (Aug 2026): customer-defined, dimensioned by JWT claim/IAM principal/target/tool/model, with request/token/connection-based enforcement and a fail-open design.

## Identity: OAuth flows (M2M / OBO / user-delegated)

AgentCore Identity issues **workload identities** for agents — a specialized form of workload identity compatible with standard patterns, so it plugs into existing IdPs rather than requiring user migration.

Three grant flows are explicitly supported:
- **Machine-to-machine (M2M)** — agent authenticates as itself to a downstream service.
- **On-behalf-of (OBO)** — agent accesses a resource on behalf of an authenticated user without separate consent flows per call (GA Apr 2026).
- **User-delegated access** — end-user explicitly grants the agent access, now supportable through a hosted **Consent Portal** (Sep 2026) that requires a JWT-authenticated Gateway as the trust source.

**Private Key JWT client authentication** (Jul 2026) lets agents authenticate to a downstream IdP's token endpoint with a KMS-signed JWT assertion instead of a shared client secret — the private key never leaves KMS, every signature is in CloudTrail, and it works across all three grant flows with RS256/PS256/ES256.

Identity integrates with Cognito, Okta, Microsoft Entra ID, Auth0, and any standard IdP; credential providers can reference existing AWS Secrets Manager secrets directly (Jun 2026), preserving your org's existing secret rotation/governance.

Sources: [Provide identity and credential management... AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html), [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Memory: short-term vs long-term, built-in vs bring-your-own

**Short-term memory**: turn-by-turn context within a single session (e.g., resolving "what about tomorrow?" against prior turns).

**Long-term memory**: automatically extracted insights that persist across sessions — preferences, facts, summaries. Built-in extraction strategies include semantic, user-preference, summarization, and episodic (added Dec 2025); as of 2026 you can also attach structured metadata for filtered retrieval (Apr 2026), use flexible namespaces (Aug 2026), ingest non-conversational JSON payloads directly via `IngestData` (Aug 2026), set per-record TTL (Oct 2026), and get push notifications on record lifecycle events instead of polling (Mar 2026).

**Built-in vs bring-your-own**: Harness gets Memory wired in by default since GA (zero config). Runtime/custom code must call the Memory SDK explicitly — but AWS documents direct integrations for **LangGraph, LangChain, Strands, and Strands LlamaIndex**, so a LangGraph app isn't limited to generic REST calls; there are idiomatic adapters (e.g., `AgentCoreMemorySaver`/`AgentCoreMemoryStore` patterns referenced in migration guides) for wiring LangGraph's own checkpointing alongside AgentCore's long-term store.

**Billing model change**: short-term memory moved to consumption-based pricing (ingestion/retrieval/storage billed separately) as of Nov 2026, replacing a flat per-event rate — relevant for cost modeling in [08-scalability-and-ops.md](./08-scalability-and-ops.md).

Sources: [Add memory to your agent](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html), [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Quotas worth knowing before committing (Nov 2026)

| Service | Limit | Value |
|---|---|---|
| Memory | Memory resources/region/account | 150 (adjustable) |
| Memory | Strategies per Memory resource | 6 (not adjustable) |
| Memory | `CreateEvent` per actor/session (conversational) | 5/sec |
| Memory | Long-term extraction tokens/min | 150,000 (adjustable) |
| Identity | Workload identities | 11,000 (adjustable) |
| Identity | OAuth2/API-key/payment credential providers | 50 each (adjustable) |
| Gateway | Targets per gateway | 100 (adjustable) |
| Gateway | Tools per target | 1,000 (adjustable) |
| Gateway | tool-call/tool-list rate (account) | 200 TPS (adjustable) |

Source: [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html)
