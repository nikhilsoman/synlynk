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

Three components, one flow, identical regardless of which agent or execution mode (home/headless) is involved. The broker itself is **non-LLM host-level code, invoked by the dispatch daemon (or, in home mode, by the local session-attachment watcher defined in §5b) — never run "as" any agent's own turn.** qa's CI/CD/infra charter explains who is *accountable* for `gh_broker.py`'s operation, not who *executes* it; running the broker inside an agent's own dispatched turn (Grok, qa-routed or otherwise) would put a prompt-driven process on the same side of the trust boundary this design exists to remove it from.

1. **Write-request emission.** An agent that needs a GitHub write — instead of calling `gh` or an MCP GitHub tool directly — writes a JSON file into its own workspace, one per pending request (not a single overwriteable filename — see §7 for why): `.synlynk/gh_write_requests/<request_id>.json`.

   ```json
   {
     "schema_version": 1,
     "request_id": "req-3f9a1c22",
     "idempotency_key": "job-d2fa5c62-merge-1074",
     "nonce": "b8b6...",
     "job_id": "job-d2fa5c62",
     "repo": "nikhilsoman/synlynk",
     "actor_role": "dev",
     "action": "merge" | "review" | "comment" | "close" | "request-changes" | "label",
     "target": {"type": "pr" | "issue", "number": 1074},
     "commit_sha": "79a8102...",
     "body": "...",
     "action_args": {"approve": true}
   }
   ```

   `action_args` (renamed from an earlier, rejected `extra_args` shape — see §7) is a per-action, schema-validated map of allowlisted keys only; it is never forwarded to `gh` as raw CLI flags.

2. **Broker** (`synlynk/gh_broker.py`) — runs outside every agent's sandbox. It watches for request files in worktrees bound to a registered job (headless) or a registered interactive session (home, §5b) — a request from an unregistered source is never silently ignored; see §7 for the corrected behavior. It consumes each request atomically (rename-then-read, symlinks rejected, restrictive file permissions), validates `schema_version`, `nonce`/`idempotency_key` (replay protection — a previously-consumed `idempotency_key` is rejected, not re-executed), and that `actor_role` matches the role actually bound to the originating job — a job dispatched under a lower-privileged role cannot mint a higher-privileged write by naming a different role in the request. It validates the action against a fixed allowlist, resolves the *matched* role's GitHub App installation token via the existing `get_installation_token(role, app_config)` (`synlynk/github_app_auth.py`), and executes via `gh` CLI itself — never MCP.

   For `merge` specifically, the broker additionally enforces a hard-coded gate before executing, with no override: `gh pr checks` reports at least one check and all are green (a "no checks reported" response is treated as a failure, not a pass — see §7), zero unresolved review threads, target branch not in a protected-branch list. Where the request's role and the PR's own author identity collide (the #423 same-identity case — an App-token `gh pr review --approve` still fails GitHub's own "cannot approve your own PR" rule even under a distinct bot identity if the identities resolve to the same authorship chain), the broker maps the request to the sanctioned COMMENT-checklist path instead of attempting an approve that GitHub will reject, or returns a typed rejection reason if no checklist path applies to the action.

   For review-class actions, the broker supports batched submission: a request may include multiple inline comments plus a single final verdict (`APPROVE` / `REQUEST_CHANGES` / `COMMENT`) and an optional `in_reply_to` per comment, submitted as one GitHub pending-review-then-submit sequence — not as N separate comment calls, which fragments the review UI and spams notifications.

3. **Result + audit.** The broker writes `.synlynk/gh_write_results/<request_id>.json` back into the workspace and appends a line to `.synlynk/logs/gh_write_audit.jsonl` (repo, job ID, request ID, actor role, action, target, outcome, `elevated: true|false`). Rejections reuse the existing `succeeded_gh_write_failed` terminal status from #701, so this plugs into `synlynk jobs`/`synlynk pr check` without new status plumbing. **A written request file is never itself treated as task success** — the dispatch daemon (or, in elevated mode, the agent per §6) must observe the corresponding result file, and for merge/close-class actions the daemon additionally re-queries live GitHub state before marking the job's own outcome, so a broker crash between "executed" and "audit-logged" can't silently read as success.

   ```json
   {
     "request_id": "req-3f9a1c22",
     "status": "executed" | "rejected",
     "reason": null | "ci not green: 2 failing checks" | "ci: no checks reported" | "unresolved review threads: 1" | "protected branch" | "same-identity approve mapped to comment-checklist",
     "gh_output": "...",
     "timestamp": "2026-08-19T..."
   }
   ```

## 4. Security Boundary

**The token never enters the agent's sandbox.** The role's GitHub App installation token is resolved by the broker at execution time, in the broker's own process — never written into the worktree, never passed as an env var to the dispatched agent's subprocess, never visible to `codex exec` regardless of sandbox mode. This improves on #577's original B2-B sketch (a worktree-local token file), which would have put a live credential inside Codex's `workspace-write` filesystem access.

**The broker is itself a new trust boundary.** It runs as the same host user as the dispatch daemon (no privilege escalation, just a narrower one), only acts on request files from worktrees it registered, and every action — not only merges — gets an audit-log entry, so even non-gated actions are forensically visible.

**Fail-closed on every branch.** Malformed request, token-mint failure, action not on the allowlist, replayed `idempotency_key`, role/actor mismatch, or a request from an unregistered worktree/session → reject and log (see §7 — unregistered sources are now a typed rejection, not a silent ignore); never fall through to a shared/personal identity (matching #569's precedent) or to letting the agent attempt the write directly via MCP/`gh` (the exact failure pattern #659 exists to prevent).

**Direct `gh`/MCP write access must be structurally denied, not just discouraged, for every harness with `can_gh_write: true`, in both headless and home mode.** Codex's `workspace-write` sandbox gets this for free (no network egress). Grok, Claude, and Agy do not — they retain live `gh` CLI and GitHub MCP tool access by default, so a prompt instructing "use the broker instead" is a convention, not enforcement, and doesn't close the #569/#659 bypass. Shipping this design requires the dispatch environment (headless) and the interactive tool-configuration surface (home, via §5b's session registration) to remove the `gh` write subcommands and GitHub MCP write tools from what's available to the harness process itself, so the request-file protocol is the *only* path capable of a GitHub write, not merely the recommended one.

## 5. Data Flow — Default (Post-Turn) Mode

The dispatch daemon runs the agent's turn to completion → checks for pending files under `.synlynk/gh_write_requests/` → for each, invokes the broker → broker validates, resolves the role token, executes or rejects, writes the corresponding `.synlynk/gh_write_results/<request_id>.json` and an audit entry → the job's terminal status reflects the outcome, reconciled against live GitHub state per §3.3.

The agent's own process has exited by the time the broker runs, so it cannot poll for the result within the same turn — acceptable for fire-and-forget actions (review, comment, label, ordinary merge), where the outcome is checked post-hoc via the job summary, matching today's dispatch model.

## 5b. Interactive (Home-Mode) Attachment

Sections 3–5 as written implicitly assumed a dispatch daemon is always present to watch for request files. It isn't — an interactive/home session (e.g. Claude Code running directly in a user's terminal) is not dispatch-owned, so a request file written during such a session would sit unobserved indefinitely. This is a genuine scope gap surfaced independently by Round 2's `synlynk decide` panel (claude, codex, grok), not a cosmetic one: without a defined attachment path, home-mode sessions either silently lose GitHub-write capability, or — worse, for harnesses like Grok that retain live `gh`/MCP access — bypass the broker entirely with no daemon oversight at all, which is strictly worse than the headless case this design set out to fix.

**Mechanism:** on session start, an interactive harness that may need to emit GitHub writes registers itself by writing a small record into the repo it's operating in: `.synlynk/registered_sessions/<session_id>.json` — `{schema_version, session_id, role, worktree_path, pid, registered_at}`. A single broker watcher process — the same `gh_broker.py`, not a separate home-mode implementation — polls both dispatch-owned worktrees and session-registered worktrees identically; there is no home/headless code fork in the broker itself, only a difference in who creates the registration record (the dispatch daemon does it automatically per job; an interactive session does it once at startup). The watcher is started on-demand: the first time it observes a request file under a registered worktree with no watcher yet attached, dispatch/init tooling starts one; it does not need to run continuously as a system service.

**Unregistered sessions get no watcher, by design — this is the fail-closed default, not an oversight.** A session that never registers is treated exactly like the "unregistered worktree" case in §7: any request file it writes is never observed, and (per §7's revision) an interactive harness capable of detecting this should surface it as an explicit "broker not attached" condition rather than assuming success. This is why §4's structural `gh`/MCP-denial requirement applies to home mode too — without it, an unregistered or not-yet-attached interactive session would still have its own live write path as a fallback, defeating the point of registration in the first place.

**Registration is per-session, not per-repo-permanent** — a stale registration (process no longer running, per `pid`) is treated as unregistered by the broker, so a crashed or closed session doesn't leave a phantom watcher target.

## 6. Elevated (Synchronous) Mode

Some tasks need to act *on* the write result within the same turn — e.g. "merge the hotfix, then verify deployment, then close the incident issue." For these, dispatch supports an elevated, synchronous mode:

- **Gated at dispatch time, not by the agent.** Elevated mode is set via a dispatch-time flag (e.g. `--sync-gh-write`), issued by whoever dispatches the task — architect or pm, per the role charter — never self-declared by the sandboxed agent mid-task. An agent claiming its own task is "urgent" would trivially defeat the gating; elevation must originate outside the sandbox, at the same trust level as `--requires-gh-write` today. In home mode, elevation is likewise gated by the human operator (e.g. explicitly running an elevated-mode command), never by the interactive harness deciding for itself.
- **Sandbox-compatible mechanism.** `workspace-write` blocks network but allows repeated file reads/writes under the workdir and `/tmp`. In elevated mode the broker runs as a live sidecar for the duration of the turn (rather than only after), and the agent's prompt instructs it to poll for its specific `<request_id>.json` result with a bounded wait (e.g. up to 60s, sleep-and-reread) — no sockets, no new network surface. **This wait must be implemented as a single blocking host-side wait initiated by the dispatch daemon/session harness's outer loop, not as model-driven per-turn tool-loop polling** — the latter burns a meaningful fraction of the turn's own tool budget for no benefit (flagged by Round 2's grok response) and produces no different outcome than a plain blocking wait.
- **The merge gate never relaxes.** Elevated mode changes latency, not rules: a synchronous merge request still goes through the identical CI-green / no-unresolved-threads / non-protected-branch check as an ordinary one. It does not implement a human break-glass override — that would be a separate, narrower mechanism (human-present, using the human's own `gh` auth rather than the broker's) and is out of scope here.
- **Audited distinctly.** Elevated requests carry `elevated: true` in the audit log so they can be filtered and reviewed separately, since they're rarer and higher-attention-worthy.
- **Timeout is a reject, not a hang.** If no result file appears within the bounded wait — including the case where the request was silently unobservable because the worktree/session was never registered — the agent must treat this as a rejection (`status: timeout`) and surface it, never assume success by default.

## 7. Error Handling

| Condition | Broker behavior |
|---|---|
| Malformed request JSON (missing required fields, bad `schema_version`) | Reject, write reason, audit-log entry |
| Token mint failure for the role | Reject, write reason, audit-log entry — never fall back to a shared/personal identity |
| Action not on the fixed allowlist, or `action_args` contains a non-allowlisted key for that action | Reject, write reason, audit-log entry |
| `idempotency_key` already consumed (replay) | Reject as duplicate, write reason, audit-log entry — do not re-execute |
| `actor_role` does not match the role bound to the originating job/session | Reject as unauthorized, audit-log entry — never mint a token for a higher-privileged role than the request's own origin |
| Request file from an unregistered/unknown worktree or session (headless or home, §5b) | **Reject, not ignore** — write a result file stating `unregistered_source` where possible (best-effort; the broker may not have a channel to reach a truly unknown source) and always audit-log the sighting. A caller waiting in elevated mode treats the resulting timeout as `status: timeout` per §6, not as an indefinite hang. |
| `gh pr checks` reports no checks at all for the PR | Treated as a failure, not a pass — fail-closed. (Consequently this repo cannot rely on `gh pr merge --auto`.) |
| Merge gate check fails (CI not green / unresolved threads / protected branch) | Reject with the specific failing check as `reason`, audit-log entry, no override path |
| Same-identity approve (#423: App-token `review --approve` on a PR whose authorship chain resolves to the same identity) | Map to the sanctioned COMMENT-checklist path instead of attempting the approve; if no checklist path applies to the action, return a typed rejection rather than silently downgrading the action |
| Broker process crash between executing the GitHub action and writing the result/audit entry | Caller must not infer success from a missing result file; reconciliation (§3.3) re-queries live GitHub state before any job is marked terminal-success for a merge/close-class action |

## 8. Testing Plan

- **Unit tests** for the broker's validation logic — allowlist enforcement, `action_args` schema validation per action, idempotency/replay rejection, actor-role authorization, merge-gate checks (CI-green including "no checks reported", unresolved-threads, protected-branch), the #423 same-identity mapping, and every fail-closed path — against a stubbed `gh`/token layer. No real GitHub calls in CI.
- **Integration-style test** driving the full request → broker → result-file round-trip against a local scratch worktree, including a `request_id`-keyed concurrent-requests scenario (e.g. merge then close, without one overwriting the other).
- **Home-mode attachment test**: a scratch worktree with a session-registration file present is observed by the watcher; one without registration produces a `status: timeout`/rejection, not a hang, when polled in elevated mode — covering §5b and §7's unregistered-source behavior.
- **Regression test** mirroring the existing `tests/test_gh_write_guard.py` pattern from #701, extended to cover the broker path specifically, and to assert that `gh` write subcommands / GitHub MCP write tools are actually absent from a dispatched job's available toolset (not just documented as discouraged) per §4.

## 9. Explicitly Out of Scope

- **Charter amendment** giving qa (or another role) delegated, gate-only merge authority distinct from architect's judgment-based merge authority. The existing roles/charters doc (`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`, §5) currently assigns "Merge" to architect, whose durability is explicitly "session-only, human-in-the-loop by design" — the opposite of what an unattended broker needs. This design intentionally does not amend that doc; the amendment ships as its own follow-up PR against the roles doc, mirroring the existing architect/qa split. Per Round 1's grok review, that amendment covers who is *accountable* for `gh_broker.py`'s correct operation (a qa/infra concern), not who *executes* it — the broker is non-LLM host code regardless of which role's charter references it (§3).
- **Human break-glass override** of the merge gate. Elevated mode (§6) is about synchronicity for the agent, not a bypass mechanism for humans; a genuine emergency-override path is a separate, narrower design if it's ever needed.
- **Broker as a persistent system service.** §5b's watcher is started on-demand per the mechanism described there; running it as an always-on daemon/service (e.g. launchd/systemd unit) is a possible future hardening but not required for this design.
- Issue #342 (CWD not reliably pinned to the registered worktree in some dispatch paths) was flagged by Round 2's grok review as a related mechanical risk that could independently break request-file discovery. It is a pre-existing bug in dispatch's worktree handling, not something this design introduces or needs to re-solve — tracked separately at #342.
