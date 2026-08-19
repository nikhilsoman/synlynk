# GitHub-Write Broker — Design

**Date:** 2026-08-19
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman
**Resolves:** #865 ("Evaluate a narrow, auditable Codex GitHub-write path (sandbox egress exception)")

## 1. Motivation

Codex's `codex exec -s workspace-write` sandbox structurally blocks network egress to `api.github.com` by design (confirmed via `codex exec --help`: sandbox mode is a fixed enum — `read-only` / `workspace-write` / `danger-full-access` — with no per-command network-allowlist flag, and `synlynk/_constants.py` explicitly guards against ever adding `--dangerously-bypass-approvals-and-sandbox`). Issue #577's investigation root-caused this precisely and proposed two forks: keep Codex builder-only forever (B2-A), or build a Codex-specific elevated GitHub-write lane (B2-B) as a later platform spike "if we are willing to own it."

This design is that spike — but scoped wider than a Codex-only patch, per explicit direction: with Codex and Claude expected to dominate harness market share, both need genuine first-class parity in home (interactive) and headless (unattended) execution across all core functionality, including the highest-blast-radius GitHub actions (merges), from day one, through a single mechanism that behaves identically regardless of which agent or execution mode is involved.

## 2. Rejected Alternatives

**Allowlisted network egress** (scoped OS-level firewall exception to `api.github.com:443`, keychain access still blocked). Rejected: Codex's sandbox exposes no mechanism for a per-command network allowlist today — this would require an OS-level firewall rule layered around the Codex subprocess, which is macOS-specific, fragile against every Codex sandbox implementation change, and Codex-only — it does not give Claude/Grok/Agy the same capability, so it fails the "one mechanism for both" requirement.

**Elevated-trust invocation mode** (a `--gh-write-mode` dispatch flag that loosens Codex's sandbox flags for that invocation, trusting the agent's own judgment plus instruction-text guardrails). Rejected: any mechanism relying on agent judgment rather than external enforcement cannot satisfy a hard-coded, no-override merge gate by definition — enforcement has to live outside the agent's own process. This also reopens exactly the trust question #577 flagged rather than answering it.

## 3. Architecture

Three components, one flow, identical regardless of which agent or execution mode (home/headless) is involved:

1. **Write-request emission.** A dispatched agent that needs a GitHub write — instead of calling `gh` or an MCP GitHub tool directly — writes a single JSON file into its own workspace: `.synlynk/gh_write_request.json`. This is the only new surface any agent-facing prompt needs to learn.

   ```json
   {
     "action": "merge" | "review" | "comment" | "close" | "request-changes" | "label",
     "target": {"type": "pr" | "issue", "number": 1074},
     "body": "...",
     "extra_args": {"approve": true}
   }
   ```

2. **Broker** (`synlynk/gh_broker.py`) — a new host-side process running outside every agent's sandbox, invoked by the dispatch daemon. It watches for `gh_write_request.json` in worktrees it itself created (cross-checked against the job registry — a request file from an unregistered/unknown worktree is ignored entirely, not even rejected with a response), validates the action against a fixed allowlist, resolves the *role's* GitHub App installation token via the existing `get_installation_token(role, app_config)` (`synlynk/github_app_auth.py`), and executes via `gh` CLI itself — never MCP.

   For `merge` specifically, the broker additionally enforces a hard-coded gate before executing, with no override: `gh pr checks` all green, zero unresolved review threads, target branch not in a protected-branch list.

3. **Result + audit.** The broker writes `.synlynk/gh_write_result.json` back into the workspace and appends a line to `.synlynk/logs/gh_write_audit.jsonl` (actor role, action, target, outcome, `elevated: true|false`). Rejections reuse the existing `succeeded_gh_write_failed` terminal status from #701, so this plugs into `synlynk jobs`/`synlynk pr check` without new status plumbing.

   ```json
   {
     "status": "executed" | "rejected",
     "reason": null | "ci not green: 2 failing checks" | "unresolved review threads: 1" | "protected branch",
     "gh_output": "...",
     "timestamp": "2026-08-19T..."
   }
   ```

## 4. Security Boundary

**The token never enters the agent's sandbox.** The role's GitHub App installation token is resolved by the broker at execution time, in the broker's own process — never written into the worktree, never passed as an env var to the dispatched agent's subprocess, never visible to `codex exec` regardless of sandbox mode. This improves on #577's original B2-B sketch (a worktree-local token file), which would have put a live credential inside Codex's `workspace-write` filesystem access.

**The broker is itself a new trust boundary.** It runs as the same host user as the dispatch daemon (no privilege escalation, just a narrower one), only acts on request files from worktrees it registered, and every action — not only merges — gets an audit-log entry, so even non-gated actions are forensically visible.

**Fail-closed on every branch.** Malformed request, token-mint failure, action not on the allowlist, or an unregistered worktree → reject (or ignore, for unregistered worktrees) and log; never fall through to a shared/personal identity (matching #569's precedent) or to letting the agent attempt the write directly via MCP/`gh` (the exact failure pattern #659 exists to prevent).

## 5. Data Flow — Default (Post-Turn) Mode

The dispatch daemon runs the agent's turn to completion → checks for `gh_write_request.json` → if present, invokes the broker → broker validates, resolves the role token, executes or rejects, writes the result file and audit entry → the job's terminal status reflects the outcome.

The agent's own process has exited by the time the broker runs, so it cannot poll for the result within the same turn — acceptable for fire-and-forget actions (review, comment, label, ordinary merge), where the outcome is checked post-hoc via the job summary, matching today's dispatch model.

## 6. Elevated (Synchronous) Mode

Some tasks need to act *on* the write result within the same turn — e.g. "merge the hotfix, then verify deployment, then close the incident issue." For these, dispatch supports an elevated, synchronous mode:

- **Gated at dispatch time, not by the agent.** Elevated mode is set via a dispatch-time flag (e.g. `--sync-gh-write`), issued by whoever dispatches the task — architect or pm, per the role charter — never self-declared by the sandboxed agent mid-task. An agent claiming its own task is "urgent" would trivially defeat the gating; elevation must originate outside the sandbox, at the same trust level as `--requires-gh-write` today.
- **Sandbox-compatible mechanism.** `workspace-write` blocks network but allows repeated file reads/writes under the workdir and `/tmp`. In elevated mode the dispatch daemon runs the broker as a live sidecar for the duration of the turn (rather than only after), and the agent's prompt instructs it to poll `gh_write_result.json` with a bounded wait (e.g. up to 60s, sleep-and-reread) — no sockets, no new network surface.
- **The merge gate never relaxes.** Elevated mode changes latency, not rules: a synchronous merge request still goes through the identical CI-green / no-unresolved-threads / non-protected-branch check as an ordinary one. It does not implement a human break-glass override — that would be a separate, narrower mechanism (human-present, using the human's own `gh` auth rather than the broker's) and is out of scope here.
- **Audited distinctly.** Elevated requests carry `elevated: true` in the audit log so they can be filtered and reviewed separately, since they're rarer and higher-attention-worthy.

## 7. Error Handling

| Condition | Broker behavior |
|---|---|
| Malformed request JSON | Reject, write reason, audit-log entry |
| Token mint failure for the role | Reject, write reason, audit-log entry — never fall back to a shared/personal identity |
| Action not on the fixed allowlist | Reject, write reason, audit-log entry |
| Request file from an unregistered/unknown worktree | Ignored — no response written, since the broker doesn't recognize the source as a known job |
| Merge gate check fails (CI not green / unresolved threads / protected branch) | Reject with the specific failing check as `reason`, audit-log entry, no override path |

## 8. Testing Plan

- **Unit tests** for the broker's validation logic — allowlist enforcement, merge-gate checks (CI-green, unresolved-threads, protected-branch), and every fail-closed path — against a stubbed `gh`/token layer. No real GitHub calls in CI.
- **Integration-style test** driving the full request → broker → result-file round-trip against a local scratch worktree.
- **Regression test** mirroring the existing `tests/test_gh_write_guard.py` pattern from #701, extended to cover the broker path specifically.

## 9. Explicitly Out of Scope

- **Charter amendment** giving qa (or another role) delegated, gate-only merge authority distinct from architect's judgment-based merge authority. The existing roles/charters doc (`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`, §5) currently assigns "Merge" to architect, whose durability is explicitly "session-only, human-in-the-loop by design" — the opposite of what an unattended broker needs. This design intentionally does not amend that doc; the amendment ships as its own follow-up PR against the roles doc, mirroring the existing architect/qa split.
- **Human break-glass override** of the merge gate. Elevated mode (§6) is about synchronicity for the agent, not a bypass mechanism for humans; a genuine emergency-override path is a separate, narrower design if it's ever needed.
- **Structural MCP tool denylist** (the "3b" direction from #659's fix). #659 shipped with broadened auto-detection of GitHub-write task shapes (3a) only; a denylist remains a possible follow-up but is not required by this design, since the broker model makes direct MCP writes moot for any agent that adopts the request-file protocol.
