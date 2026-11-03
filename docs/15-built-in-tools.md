# Built-in Tools (Browser, Code Interpreter)

**Verification note:** the primary AWS doc page
([built-in-tools.html](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/built-in-tools.html))
did not render fetchable content during this research pass (JS-rendered page, fetch tool
returned no body). What follows is sourced from AWS's own doc pages for the individual tools
(`code-interpreter-create.html`) and secondary write-ups, flagged where unverified. Treat
specifics (exact size limits, API names) as needing a direct console/doc check before you
rely on them, not as confirmed facts the way other docs in this repo are.

## What exists

AgentCore ships two hosted built-in tools an agent can call without you building the
sandbox yourself:

| Tool | Purpose | Isolation |
|---|---|---|
| **Code Interpreter** | Execute code (Python; TypeScript/JavaScript per secondary sources) for data analysis, computation | Isolated sandbox session, separate from the agent's own Runtime/Harness session |
| **Browser** | Navigate and interact with web pages (clicking, typing, reading content) | Isolated browser environment, separate session |

Both are provisioned as their own AgentCore resource (a "tool resource"), then a session is
opened against that resource per use — same session/resource split as Runtime and Gateway.

## Code Interpreter specifics (from AWS's `code-interpreter-create.html`)

- Runs in a containerized, isolated environment.
- Natively handles CSV, Excel, JSON and similar structured formats.
- Inline file uploads: up to 100 MB.
- Files staged via S3 (through terminal commands, using an IAM role attached to the Code
  Interpreter): up to 5 GB.

## Why this matters for the migration decision

**Read [14-security-incidents.md](14-security-incidents.md) before relying on Code
Interpreter.** The two 2026 CVEs (CVE-2026-12530, CVE-2026-16796) were specifically in the
Code Interpreter package-installation path, and led to AWS credential theft from the
execution role attached to the Code Interpreter. If your agent needs to let an LLM install
packages or run arbitrary code based on user input, this is the exact feature that was
exploited — confirm SDK version ≥1.18.1 and keep the execution role scoped to least
privilege.

Browser tool: independently reported (BeyondTrust, Sept 2025) that "no network access"
sandbox mode still permitted DNS egress — relevant if you're using Browser against
semi-trusted content and assuming full network isolation.

## What's not yet covered in this repo

Flagging rather than guessing: whether there are additional built-in tools beyond these two
(e.g. a file system tool, a search tool) was not fully confirmed in this pass. If your POC
(Phase 1+ in [13-poc-plan.md](13-poc-plan.md)) needs capabilities beyond code execution and
browsing, check the AWS console's tool catalog directly rather than assuming this list is
exhaustive.
