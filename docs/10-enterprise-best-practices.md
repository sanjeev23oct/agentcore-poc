# Enterprise Best Practices

## Security

- **Session isolation**: each Runtime session is a dedicated Firecracker microVM with its own compute/memory/filesystem; the Instances compute type trades this for longer-lived shared EC2 instances — pick per workload sensitivity (see [02-runtime-microvm.md](./02-runtime-microvm.md)).
- **Execution roles / least privilege**: Runtime now supports **session context keys** (Oct 2026) that scope IAM access to a session or runtime, so sessions sharing an execution role can be restricted to only their own data without a separate role per session. Combine with the Gateway source-enforcement controls (`aws:SourceArn` for SigV4, `allowedWorkloadConfiguration` for JWT) to guarantee a Runtime agent is only reachable through your Gateway, not directly.
- **Credential hygiene**: AgentCore Identity's **Private Key JWT** client authentication (Jul 2026) keeps private keys in KMS and signs via API call, logged to CloudTrail — preferable to shared OAuth client secrets for M2M flows. Identity credential providers can also reference existing Secrets Manager secrets directly, preserving existing rotation/governance instead of migrating secrets into AgentCore.
- **Policy as a gate, not a suggestion**: AgentCore Policy intercepts every tool call at the **Gateway layer**, outside agent code — "the agent cannot reason around them," per AWS. It supports natural-language or Cedar-compatible ("Dogwood") policy authoring, and as of Jun 2026 integrates Bedrock Guardrails for prompt-injection, harmful-content, and sensitive-data checks on both tool outputs and gateway-target inputs.
- **Compliance posture**: AgentCore achieved SOC 1/2/3 scope (Jun 2026) and ISO/CSA STAR certification (Feb 2026) — relevant if the org has a vendor-compliance gate for new platforms.
- **Network isolation**: VPC egress support for Identity/Gateway/Runtime (Apr 2026) lets agents reach private resources (e.g., EKS-hosted MCP servers) and private IdPs without public exposure; PrivateLink is available for most control-plane and data-plane operations across services (expanding through 2026 — Identity control plane was still a documented gap as of Mar 2026 notes).

Sources: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html), [Provide identity and credential management...](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)

## CI/CD

- **AgentCore CLI v1.0** (`@aws/agentcore` 1.0.0, Oct 2026) is a full rebuild: faster startup, consistent command structure, and new **direct resource commands** (`harness`, `runtime`, `memory`, `identity`, `gateway`, `payment`) that work without first scaffolding a "project" — useful for ops tasks like invoking an existing Runtime by ARN or opening an interactive shell against a live resource.
- **Project workflow** retained: `create`, `add`, `remove`, `build`, `deploy`, `dev`, `invoke`, `status`, `logs`, `traces`, `export`, plus `eval` commands; every command supports `--region`, `--json`, `--debug`, `--version` flags for scripting.
- **Thin CDK app**: v1.0 projects ship a small CDK app built on `@aws/agentcore-cdk` constructs (which graduated from alpha to **stable** in `aws-cdk-lib` in May 2026) instead of generated boilerplate CDK code. Deployments turn on CloudWatch Transaction Search by default.
- **v0→v1 migration**: `agentcore migrate` produces a read-only migration plan before touching anything, refactors CloudFormation stacks per deployment target, and preserves v0 physical resource names; resources v1 doesn't yet support are kept outside the v1 stack. v0 projects keep working under the v1 CLI (handed off to a bundled v0 CLI internally) — not a forced flag-day migration.
- **Local dev loop**: `agentcore dev` provides a browser-based Agent Inspector (chat UI, token/tool-call inspection, execution timeline, local Memory browsing) before anything touches the cloud (Apr 2026).
- **IaC alternative**: native AWS CloudFormation support for Runtime/Memory resources predates the CLI tooling (Sep 2025) if the org standardizes on raw CloudFormation rather than CDK.

Source: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Observability

Covered in depth in [08-scalability-and-ops.md](./08-scalability-and-ops.md): unified per-agent CloudWatch log groups for spans (opt-in pre-Jul 2026, default after), `OverheadLatency` and `ActiveSessionCount` vended metrics, cross-account monitoring (up to 100K log groups per monitoring account), and the full Evaluations/Optimization loop (batch eval, A/B testing, failure-pattern insights, skill evaluators) that works regardless of hosting choice.

## Cost control

- Harness carries **no separate charge** beyond the underlying services it consumes.
- Short-term Memory moved to **consumption-based billing** (ingestion/retrieval/storage priced separately) in Nov 2026 — model this explicitly rather than assuming flat per-event cost.
- Gateway's new **configurable rate limits** (Aug 2026, token/request/connection-based, per caller/tool/model dimension) double as a cost-control lever, not just a reliability one — cap spend per tenant/caller directly at the gateway.
- Harness exposes its own "control cost with limits" configuration (iteration caps, timeout caps, token caps per invocation) — see [harness-operations.md](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-operations.html) (not independently fetched in this pass; verify specifics before relying on it).
- Always price against the live [AgentCore pricing page](https://aws.amazon.com/bedrock/agentcore/pricing/) — several pricing mechanics changed mid-2026 (see above), so cached numbers from older blog posts are unreliable.

## Versioning and endpoints

- Both Runtime and Harness support **immutable versions and named endpoints** — roll out a new version, then point an endpoint at it; rollback is "point the endpoint at the prior version," not a redeploy.
- Harness additionally supports **export to Strands code** at any point, giving an exit ramp from the managed config format to raw code run on Runtime if you outgrow configuration-only management.
- Memory, Evaluators, and Configuration Bundles (part of the Optimization loop) are independently versioned resources, so prompt/tool-description changes can be A/B tested with statistical-significance reporting before full rollout — a meaningfully more rigorous default than most self-hosted LangGraph deployment pipelines have out of the box.

Source: [AgentCore harness](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html), [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)
