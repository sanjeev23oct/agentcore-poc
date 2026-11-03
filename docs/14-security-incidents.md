# Security Incidents (2026)

This doc exists because it should be in front of anyone approving a production migration.
AgentCore is young, and 2026 surfaced real, disclosed vulnerabilities — not hypothetical
risks. None of the other docs in this repo cover this; it was missed in the first research
pass and added only after being asked directly whether the feature list was complete.

## CVE-2026-12530 / CVE-2026-16796 — "AgentCorruption" (Code Interpreter credential theft)

**What happened:** The `bedrock-agentcore` Python SDK's Code Interpreter helper
(`install_packages()`) had insufficient input validation when installing pip packages
inside a sandbox session.

- **CVE-2026-12530** (SDK versions 1.1.3–1.6.0): a crafted package name could bypass an
  incomplete character blocklist and execute arbitrary shell commands inside the sandbox.
  From there, an attacker could read the temporary AWS credentials attached to the Code
  Interpreter's execution role.
- **CVE-2026-16796** (all versions before 1.18.1): after AWS's first fix, researchers found
  a bypass using pip's "package extras" syntax (`package[extra]`) to smuggle shell commands
  past the new validation.

**Attack prerequisites (all three required):**
1. Attacker-influenced input reaches `install_packages()` — i.e. your agent lets a user
   prompt influence what package gets installed in a Code Interpreter session.
2. A vulnerable SDK version.
3. A custom Code Interpreter with an IAM execution role attached.

**Impact:** arbitrary code execution inside the sandbox, AWS credential theft from the
execution role, and — per the researchers — the resulting activity "would look like
legitimate application activity in AWS logs," meaning standard CloudTrail/CloudWatch
monitoring would not flag it as anomalous.

**Fix status:** patched in SDK 1.6.1 (first CVE) and 1.18.1 (second CVE, closing the
bypass). **Action item: confirm your SDK pin is ≥1.18.1 before using Code Interpreter with
any user-influenced package installation.**

**CVSS:** 3.1 base score 7.3, 4.0 base score 8.4 (high severity).

**Disclosed:** technical analysis published September 28, 2026, by BeyondTrust.

Source: [Infosecurity Magazine — "Amazon Bedrock AgentCore Flaws Could Expose AWS
Credentials"](https://www.infosecurity-magazine.com/news/aws-agentcore-sdk-flaws-ai/)

## CoreBreak — CVE-2026-18830 (confirmation/approval bypass)

Disclosed at Black Hat USA 2026: the confirmation processor for agent tool-call approvals
did not verify tool ownership or that approval arguments matched the actual tool call being
approved. This allowed an attacker to forge an approval without the model ever actually
invoking the tool-call path that approval was supposed to gate — effectively bypassing
human-in-the-loop or policy-gated confirmations.

Relevant if your enterprise plan relies on AgentCore's lifecycle hooks or Policy engine
(Cedar policies, see [11-guardrails.md](11-guardrails.md)) as a hard control, not just a
soft check. Confirm current patch status before treating confirmation-gated tool calls as a
trustworthy security boundary.

Source: [Dark Reading — "'AgentCorruption' Puts AWS Environments at Risk With One
Prompt"](https://www.darkreading.com/cloud-security/agentcorruption-aws-environments-at-risk-single-prompt)
(covers the broader disclosure context this surfaced under)

## DNS exfiltration via sandbox "no network access" mode

Independently reported (BeyondTrust, September 2025 — predates the two CVEs above): even
with a Code Interpreter or Browser sandbox configured for "no network access," outbound DNS
queries were still permitted. This is enough to establish a covert, low-bandwidth
command-and-control or data-exfiltration channel, since DNS lookups can carry encoded data.

Relevant if your threat model assumes "no network access" sandbox mode is a hard
network-isolation guarantee — as of this report, it was not.

## CLI Docstring Injection — CVE-2026-11393

An unescaped triple-quote character in the `collaborationInstruction` field of AgentCore
CLI project configuration allowed injecting arbitrary code into CLI-generated application
code. Fixed in AgentCore CLI version 0.14.2.

Relevant if you use the AgentCore CLI project workflow (`agentcore create`/`add`) with
multi-agent collaboration config sourced from anything other than a fully trusted,
reviewed input.

## What this means for the migration decision

None of these are reasons to reject AgentCore outright — young platforms accumulate CVEs,
and AWS fixed all four reasonably fast once disclosed. But they are reasons to:

1. **Pin and track SDK/CLI versions explicitly** in any production deployment —
   `bedrock-agentcore >= 1.18.1`, AgentCore CLI `>= 0.14.2` at minimum, and watch the
   [release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)
   for future CVE-driven patches.
2. **Not treat the execution role as implicitly low-risk** — scope it to least privilege
   per Phase 3 of [13-poc-plan.md](13-poc-plan.md), since credential theft from an
   over-privileged execution role is the common thread across the Code Interpreter CVEs.
3. **Not treat "no network access" sandbox mode as a network isolation guarantee** without
   independently verifying DNS egress is blocked too.
4. **Not treat confirmation/approval gates as a hard security boundary** without confirming
   the CoreBreak-class bypass is patched in whatever version you deploy.
5. Add "check for new AgentCore CVEs" as a standing item in your security review cadence,
   not a one-time check before go-live — this is an actively evolving platform.

This list is not exhaustive — it reflects what surfaced in one search pass in November 2026.
A real pre-production review should check AWS's own security bulletins and CVE databases
directly, not rely solely on this doc.
