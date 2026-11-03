# Scalability and Operations

## Scaling model

AgentCore Runtime is session-based, not instance-based, autoscaling: each invocation with a new session ID provisions its own microVM (or, for the Instances compute type, is scheduled onto a managed EC2 instance); AWS handles provisioning/scaling/teardown without you managing a fleet, ASG, or cluster. Per-session hardware is capped at 2 vCPU / 8 GB (Runtime microVMs); Instances can use larger EC2 instance types and GPU-accelerated types. There's no "set min/max replicas" control exposed the way you'd configure ECS/EKS — scaling is implicit and governed instead by account-level quotas (active session workloads/account, new-session creation rate, data-plane TPS). See [02-runtime-microvm.md](./02-runtime-microvm.md) for the current numbers.

Concurrency *within* a single session is now generous on platform V2: up to 250 concurrent connections (WebSocket/SSE/parallel tool calls) per session as of Nov 2026, up from 16 at V2's Sep 2026 GA. This specifically targets connection-heavy agent patterns (streaming UIs, many parallel tool calls) that would have throttled earlier in the year.

Source: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Observability

- **Unified tracing**: as of Jul 2026, Runtime agents can send spans to their *own* CloudWatch log group (`/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>`) rather than a shared `aws/spans` log group, enabling per-agent access control and encryption scoping. New agents in supported regions default to this since Jul 20, 2026; older agents must opt in via `UNIFIED_TRACES_DESTINATION_ENABLED=true`.
- **`OverheadLatency` metric** (Nov 2026, V2 only): isolates platform-attributable latency (time from request receipt to first response byte, excluding your agent's own processing) in the `AWS/Bedrock-AgentCore` CloudWatch namespace — the right metric to separate "AgentCore is slow" from "my agent/model call is slow."
- **`ActiveSessionCount`** (Jul 2026): real-time per-minute gauge of active sessions, dimensioned by `Service` (Runtime / CodeInterpreter / Browser), useful for quota-consumption alarms.
- **Cross-account observability**: a monitoring account can link up to 100,000 log groups across up to 5 source accounts each (Apr 2026) — relevant for a multi-account enterprise landing zone.
- **Trace latency**: put-to-get latency for complete traces (spans + logs) is under 10 seconds as of Apr 2026.
- **Evaluations/Optimization loop**: built-in evaluators (13+ as of GA, expanding through the year — skill evaluators, failure-analysis evaluator, third-party DeepEval/AutoEval evaluators), batch evaluation, A/B testing with statistical significance reporting, and automated prompt/tool-description recommendations from production traces — this "agent performance loop" (Optimization, Batch Eval, A/B Testing, User Simulation, Failure Insights) reached GA across the board by Jun 2026 and works regardless of where the agent runs (Runtime, Lambda, EKS, or non-AWS).

Sources: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Cost model

Pricing is consumption-based with no upfront commitment, but it is **split across every service you touch** (Runtime compute-seconds, Memory ingestion/retrieval/storage, Gateway invocations, Evaluations tokens, etc.) rather than one line item. Short-term Memory moved from flat per-event pricing to consumption-based (ingestion/retrieval/storage billed separately) in Nov 2026 — a cost-model change mid-stream that's worth watching for, since AWS has shown it will revise AgentCore pricing mechanics after GA. **Harness has no separate charge** — you pay only for the Runtime/Memory/Gateway/etc. it consumes under the hood.

Treat any specific $/invocation number you find in a blog post as stale; always check the live [AgentCore pricing page](https://aws.amazon.com/bedrock/agentcore/pricing/) before modeling cost, since this research pass did not independently verify current unit prices.

## Regions

AgentCore reached GA in 9 regions in Oct 2025 and has expanded steadily — Runtime/Tools hit 5 more regions in Jan 2026 (Stockholm, Paris, London, Seoul, Canada Central), São Paulo and Canada Central added Apr 2026, GovCloud (US-West) got Runtime/Gateway/Identity/Tools/Observability/Evaluations progressively through 2026 with Memory/Policy/Harness joining in Aug 2026. Agent Registry specifically expanded to US East (Ohio), Frankfurt, London, and Canada Central in Oct 2026 (9 regions total by Aug 2026 GA). Runtime's filesystem features (S3 Files/EFS mounts) are available across "all 15 AWS Regions where AgentCore Runtime is supported" as of May 2026. **Not every sub-service is available in every region** — always check the live [Supported AWS Regions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html) page per-service before committing to a region for production.

Source: [Release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

## Platform V1 vs V2 — operational recap

See [02-runtime-microvm.md](./02-runtime-microvm.md) for full detail. Operationally: V2 is required for acceptable cold-start latency, higher concurrency, and the `OverheadLatency` metric, at a reported (unverified by AWS primary source) higher per-unit price. There is no in-place "upgrade" of an existing V1 runtime to V2 described in the sources reviewed — treat it as a parallel deployment/cutover, similar to standing up a new endpoint and migrating traffic.
