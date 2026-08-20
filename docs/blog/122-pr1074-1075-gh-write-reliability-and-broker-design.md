---
title: "PR #1074 / #1075 — GitHub-Write Reliability, and the Spec for the Next Step"
date: 2026-08-20
series: "Building the OS for Multi-Agent Development"
post: 122
pr: "#1074, #1075"
merged: 2026-08-19
---

## The Goal at the End of the Previous PR

Issue #859 had already closed the identity half of dispatched GitHub writes: role-scoped GitHub
App tokens mean a dispatched job's `gh` calls are attributable to the role that made them, not to
whichever personal keyring happened to be logged in. That left a second, distinct question open
and explicitly unscoped — issue #865, "can Codex physically make the write at all?" Codex runs
under `codex exec -s workspace-write`, and that sandbox structurally blocks network egress to
`api.github.com`. A 2026-08-09 `synlynk decide` panel (Claude + Agy + Codex) had already agreed a
real path exists — an allowlisted egress rule, a brokered relay, or a separate elevated-trust
invocation mode — but that it needed its own scoped design and security review before any code
got written. That was the state entering this session: identity solved, physical write path still
an open design question.

## Strategic Shift in This PR

None to the overall roadmap, but the work order inverted mid-session. Brainstorming #865's broker
design surfaced a related, more urgent bug: dispatched agents doing PR reviews or issue closes were
occasionally hitting silent "user cancelled MCP tool call" failures — confirmed 5-for-5 on recent
jobs, including one closing issues via Grok. Root-causing it (issue #659) found that the
`_format_prompt_for_agent` guardrail telling agents to use the `gh` CLI directly instead of MCP
GitHub tools was only ever injected when `requires_gh_write=True` was explicitly passed — and
operators reliably forgot to pass it for tasks whose GitHub-write intent was implicit in the task
text ("close issue #935 citing the PR") rather than stated as a flag. That's a live reliability bug
independent of #865's sandbox-egress question, so it got fixed first, as PR #1074, while #865's
design work continued in parallel as PR #1075.

## What This PR Shipped

**PR #1074 (fix #659):** `synlynk/dispatch.py` gained `_task_requires_gh_write(task, task_type)` —
a conservative regex classifier that promotes `requires_gh_write` to `True` when task text combines
a GitHub-write action verb (`approve`, `close`, `comment`, `merge`, `review`, `request-changes`)
with a GitHub/PR/issue target (`github`, `gh`, `pull request`, `pr #N`, `issue #N`). The explicit
`--requires-gh-write` CLI flag remains an override that still works unchanged — this only closes
the gap for tasks where the operator didn't think to set it. `cli.py`'s dispatch preview path and
`dispatch_agent()` itself both now run task text through this classifier before resolving the
harness or building the prompt. Alongside the detection fix, the guardrail text itself got
stronger: what used to be an advisory paragraph is now headed "GitHub Write Instructions
(MANDATORY)" and explicitly names `close_issue` and other `github_*` MCP write tools as disallowed,
not just discouraged — addressing the other half of the failure mode, where the guardrail was
present but not reliably followed.

**PR #1075 (docs, resolves #865's brainstorm):** the design spec itself
(`docs/superpowers/specs/2026-08-19-gh-write-broker-design.md`), hardened across three
`synlynk decide` panel rounds. The architecture settled on a brokered relay: dispatched jobs write
a typed request file (`schema_version`, `request_id`, `idempotency_key`, `nonce`, `job_id`, `repo`,
`actor_role`, `commit_sha`, an allowlisted `action_args` map) to
`.synlynk/gh_write_requests/<request_id>.json`; a non-LLM host-code broker consumes it atomically,
executes the write with the role's own App token, verifies the result against live GitHub state,
and writes `.synlynk/gh_write_results/<request_id>.json`. A late addition — §5b, added after a
dedicated approval round — extends the same broker to interactive home-mode sessions (not just
dispatch jobs) via a session-registration file (`.synlynk/registered_sessions/<session_id>.json`)
and a unified watcher, with unregistered sources rejected by default rather than silently ignored.

Both PRs hit the same unrelated CI snag on the way in: a repo-wide "guard against `__init__.py`
regrowth" check was failing on `main` itself (4054 lines against a 4000-line limit), unconnected to
either PR's diff. That got its own fix — PR #1077, dispatched to Codex, splitting `logs.py` and
`platform_status.py` out of `__init__.py` (4054 → 3690 lines) — before #1074 and #1075 could merge.
A second, quieter finding came out of getting #1074 green after #1077 landed: `gh run rerun`
replays a workflow run against the merge-ref it captured at the *original* trigger event, not a
freshly recomputed one against `main`'s new tip — so reruns kept reporting the stale 4054-line
failure even after the real fix was on `main`. The actual fix was forcing a genuine `synchronize`
event via `gh api repos/.../pulls/<N>/update-branch`, which both #1074 and #1075 needed.

## Brainstorm Visuals Used

None — #865's design work stayed in text/spec form across the `synlynk decide` panel rounds; no
architecture question in this thread benefited from visual mockups.

## What This Achieved on the Path to Autonomy

Issue #659's fix closes a real trust gap in autonomous dispatch: a dispatched agent silently
failing to post a review or close an issue — with no error surfaced anywhere — is worse than a
loud failure, because nothing downstream knows the task didn't actually complete. Broadening
detection to cover implicit-intent task text (not just the explicit flag) means that gap shrinks
without requiring every dispatch caller to remember a flag correctly every time. #865's spec is the
harder, more consequential piece: it's the design that will eventually let Codex make GitHub writes
at all, closing the last capability gap between "Codex can review code" and "Codex can act on that
review" — without punching a hole in the sandbox that isolates it.

## The Goal at the End of This PR

The broker spec is approved and merged, but nothing has been built yet — the next goalpost is the
implementation plan (`docs/superpowers/plans/`) for §5's in-scope slice, followed by the actual
broker build. Two items are explicitly deferred per the spec's own §9, not yet scheduled: a
follow-up PR amending `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`
for qa's delegated merge-gate authority, and the broker-as-persistent-system-service question,
which the spec deliberately left unanswered rather than guessing at.
