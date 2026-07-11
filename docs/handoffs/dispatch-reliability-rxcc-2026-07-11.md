# Synlynk Handoff — Dispatch Reliability Issues

**Source:** rxcc repo, 2026-07-11, dispatching fixes for #832 (Agy) and #833 (Codex)

## 1. Environment availability — Grok not actually dispatchable

- `synlynk dispatch --help` positional `agent` argument only accepts `claude`, `agy`, `codex` — no `grok`.
- `synlynk agent list` shows no `.agents/` directory / no custom agent config in this repo.
- Yet `synlynk doctor` output includes a `doctor [grok]` section with passing checks — inconsistent signal, since the harness appears to know about Grok but doesn't expose it as a dispatch target.
- **Impact:** work intended for Grok (backend/infra) had to be rerouted to Codex mid-session after discovering the mismatch.
- **Ask:** either wire up `grok` as a real dispatch target (matching what `doctor` implies), or remove/correct the `doctor [grok]` section so it stops implying availability that doesn't exist.

## 2. Harness attach rate / stability — Agy dispatch timeouts

Two separate Agy dispatch attempts for the same task (#832, WebKit/Mobile Safari Playwright E2E flake) both failed with a generic `Error: timeout waiting for response` from the agent harness itself — not a task-content error.

- **Attempt 1** (`job-48c8a6db`): timed out during `npx playwright install` (WebKit browser download), 607s.
- **Attempt 2** (`job-0bb76dbe`): timed out much later and at a different point — mid-investigation, while chasing a 429 rate-limit / `OTP_STUB_ENABLED` load-order theory, 549s, exit -1, 0 files touched.

Because the two failures happened at unrelated points in the task, this doesn't look like a WebKit-download-specific network issue — it looks like a harness-level stall that can occur at arbitrary points in a long-running job.

- **Impact:** neither attempt produced a usable diagnosis or partial PR; #832 remains unresolved.
- **Ask:** reproduce outside browser-install-heavy tasks to isolate whether this is a generic idle/response-timeout in the harness vs. something specific to Playwright/WebKit tooling. Consider a longer or configurable response timeout, and/or heartbeat logging so a stalled job is distinguishable from a genuinely hung task.

## 3. Instruction adherence / environment — Codex sandbox git write-access scoping

Two dispatch attempts for #833 (api-integration OTP-verify 500s) both correctly diagnosed the root cause and proposed a valid fix, but neither could commit or push it.

- The second attempt surfaced the exact underlying error:
  ```
  fatal: cannot lock ref 'refs/heads/fix/codex/live-38f-api-integration-otp-500':
  Unable to create '/Users/nikhilsoman/dev/rxcc/.git/refs/heads/....lock': Operation not permitted
  ```
- **Root cause:** the dispatched worktree has write access to its own files but not to the main repo's shared `.git/refs/heads/` directory — even though git worktrees share ref storage with the main repo by design. This structurally blocks any `git checkout -b` / commit / push from a dispatched Codex job in this environment, regardless of task content. Confirmed reproducing identically on both attempts.
- **Impact:** the fix had to be applied and pushed manually by a human (Claude, on explicit user authorization) after reading it out of the job logs — the dispatch itself could not close the loop.
- **Ask:** fix worktree sandbox permissions to include write access to the main repo's `.git/refs/heads/` (or whatever the equivalent shared git metadata path is for the sandboxing mechanism in use), so dispatched jobs can actually create branches and push. This is the highest-priority fix of the three — it silently turns every git-worktree-based Codex dispatch into a diagnosis-only job.

## Suggested general improvement

Regardless of root-causing the above: add job-level partial-progress capture (e.g. auto-export a diff/patch on job completion or failure) so a diagnosed-but-unpushed fix can be retrieved programmatically instead of a human re-deriving the exact change from free-text job logs.

---
*Not for synlynk: for reference, in rxcc #833 was resolved via PR #834 (fix applied manually, bypassing the blocked dispatch). #832 is still open/unresolved.*
