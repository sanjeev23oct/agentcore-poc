# Runtime Execution Model: microVMs, Cold Start, Concurrency

## Isolation model

AgentCore Runtime runs each session in a dedicated **Firecracker microVM**. Firecracker is the same open-source VMM AWS uses for Lambda and Fargate; it provides hardware-level isolation and (per AWS's own published figure) boots in under ~125ms at the VMM layer. Each session gets its own compute, memory, and filesystem — "preventing any agent from accessing another user's data." When a session ends (idle timeout or max duration), the microVM is destroyed and session context is discarded unless explicitly persisted to Memory or session storage.

Sources: [Firecracker: the virtualization technology behind AWS Lambda and Bedrock AgentCore Runtime](https://builder.aws.com/content/36Cbsfx6GT4nUDWE1zT9Rjf64et/firecracker-the-virtualization-technology-behind-aws-lambda-and-bedrock-agentcore-runtime), [The new AgentCore Runtime is now available](https://aws.amazon.com/about-aws/whats-new/2026/09/new-agentcore-runtime-generally-available/)

As of Oct 2026, Runtime also supports an **Instances** compute type — agents run on AWS-managed EC2 in your own account instead of microVMs, supporting sessions up to 14 days, GPU instance types, and multiple agents sharing one instance. This trades per-session hard isolation for longer-lived/cheaper compute, and your account absorbs EC2/EBS/VPC/ASG quotas on top of AgentCore's own. Source: [Release notes, Aug 2026 — Instances compute type](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html).

## Platform V1 vs V2

Runtime has two "platform versions" that materially change cold start and operational behavior. **If you omit `platformVersion` when creating a runtime, you get V1** — V2 must be deliberately selected.

| | V1 | V2 |
|---|---|---|
| Startup model | Boots each session from scratch | Prepares the environment once, snapshots it; every new session restores from the snapshot |
| Cold start (P75) | 5.4–30 seconds (200MB–2GB images) | ~1.9–2.0 seconds, largely independent of image size |
| Memory management | Static allocation | Elastic — idle memory can be reclaimed mid-session |
| Env var limit | 4 KB | 4 KB as of Oct 2026 (previously 1.5 KB code-deploy / 2.5 KB container — raised to match V1) |
| Concurrent connections per session (default 2 vCPU) | 16 (8/vCPU) | 250 as of Nov 2026 (previously also 16) |
| `OverheadLatency` CloudWatch metric | Not available | Available (added Nov 2026) |
| Unit price | Lower | Higher (per community reporting — verify current pricing page before budgeting) |
| GA date | Original Runtime | Sep 18, 2026 |

Sources: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html) (Nov 2026 and Sep 2026 entries), [AgentCore Runtime versioning and endpoints](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html), community analysis at [AgentCore Runtime V2: 7 Snapshot-Safe Code Rules](https://builder.aws.com/content/3KGEvOVen1wWLLcWi6JsI4MfxVH/agentcore-runtime-v2-7-snapshot-safe-code-rules) (verify pricing claim directly against the [AgentCore pricing page](https://aws.amazon.com/bedrock/agentcore/pricing/) — not independently confirmed from an AWS primary source in this research pass).

**Practical implication for a cold-start-sensitive workload:** V2 is the only reasonable choice for a user-facing agent as of Nov 2026 — a 5–30s cold start on V1 is not viable for interactive chat. The snapshot-restore model means your container/code must be "snapshot-safe" (e.g., not bind to ephemeral ports or cache data that goes stale across a restore) — worth a close read of the V2 migration guidance before committing.

## Quotas that matter for capacity planning (Nov 2026 defaults)

| Limit | Value | Adjustable |
|---|---|---|
| Active session workloads/account | 5,000 (us-east-1, us-west-2), 2,500 elsewhere | Yes |
| Total agents/account | 1,000 | Yes |
| Max hardware per session | 2 vCPU / 8 GB | No |
| Max Docker image size | 2 GB | No |
| Max direct-code-deploy package | 250 MB compressed / 750 MB uncompressed | No |
| Request timeout (sync) | 15 minutes | No |
| Max payload size | 100 MB | No |
| Streaming max duration | 60 minutes | No |
| Async job max duration | 8 hours (microVM) / 14 days (Instances) | No |
| Concurrent connections/session (V2, default 2vCPU) | 250 | No |
| Data-plane API rate (`InvokeAgentRuntime` etc.) | 1,000 TPS/account (shared quota) | Yes |
| New session creation rate | 25 TPS/account (shared) | Yes |
| Idle session timeout | 15 min (adjustable up to 8h microVM / 14d Instances) | Yes |
| Max session duration | 8 hours (microVM) / 14 days (Instances) | Yes |
| Session storage | 1 GB/session | No |

Source: [Quotas for Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html) — this is the authoritative, current page; re-check before capacity planning since several of these values changed multiple times in 2026 (e.g. the data-plane rate moved from 200 TPS/agent to a shared 1,000 TPS/account pool in Aug 2026, and the per-session connection limit moved from 16 to 250 in Nov 2026).

## What this means for the migration decision

- **2 vCPU / 8 GB per session is a hard ceiling** on Runtime (not Instances). A LangGraph agent with heavy in-process compute (large local embeddings, big in-memory indices) may not fit without moving that work to a separate tool/service behind Gateway or Code Interpreter.
- **8-hour hard session cap on microVMs** means long-running agentic workflows (multi-hour research agents, overnight batch jobs) must either use Instances (up to 14 days) or be redesigned as resumable/stateless-between-invocations using Memory + session storage.
- Session isolation is a genuine security win over a typical self-hosted LangGraph deployment on ECS/EKS, where isolation is usually at the container or process level, not a full hardware-virtualized microVM per end-user session.
