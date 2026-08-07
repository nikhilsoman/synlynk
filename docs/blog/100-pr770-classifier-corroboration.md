# PR #770 — Teaching the Classifier to Check Its Work First

## The goal at the end of the previous PR

Issue #720 documented a false-positive terminal-status incident: job-9460f9fc did extensive
reads, edits, tests, and a commit, but synlynk still classified it `permission_denied`. Two of
#720's three sub-projects had already shipped — the fail-closed empty-task guard, and the
task-receipt protocol (PR #768) — leaving the actual classifier bug untouched. That work was
re-filed standalone as issue #769, alongside two other sub-projects (scope enforcement and
safe-caller docs) that remain unscoped. The goalpost at the end of #768 was: fix the root cause
in `_log_has_permission_denied_signature()` itself.

## What shipped in this PR

`_log_has_permission_denied_signature()` (`synlynk/costs.py`) has two detection paths: a phrase
match against known denial strings, and a structured-event fallback that scans a job's JSON log
lines in reverse. The bug lived in the second path — it returned `True` on the **first**
denial-shaped event it found (`status == "SUCCESS"`, empty `response`, `num_turns <= 1`) without
checking whether any earlier event in the same log showed real activity. A harness can
legitimately do substantial multi-turn work and then emit one trailing empty-response turn (a
summary, a benign no-op); the old logic treated that final event's shape as sufficient proof of
denial on its own.

Two layers of fix, per the approved design
(`docs/superpowers/specs/2026-08-07-permission-denied-classifier-fix-design.md`):

**Layer 1 — log-level corroboration (`costs.py`).** New helpers `_event_shows_real_activity()`
and `_log_has_prior_activity_evidence()` scan every line *before* the candidate denial-shaped
event for a non-empty `response` on a `SUCCESS` event, or a `tool_use` block inside an
`assistant`-typed message. If either is found, the classifier returns `False` — this event isn't
proof of denial, it's a benign tail on a productive session. This is the only fix available to
`daemon_jobs` reconciliation, which has no `worktree_path` to check git state against.

**Layer 2 — git-state corroboration (`jobs.py`).** At the two `jobs`-table reconciliation call
sites (waitpid-reaped and dead-pid branches), `git_state` is already computed nearby. Both sites
now reuse the existing `_job_has_real_work_landed(git_state)` helper as an independent second
signal:

```python
permission_denied = _log_has_permission_denied_signature(log_text)
if permission_denied and _job_has_real_work_landed(git_state):
    permission_denied = False
```

This catches jobs whose log-level signals are ambiguous but where a real commit or remote push
proves the work happened. No new job status was introduced — a corroborated job simply falls
through to normal exit-code/git-state status derivation, same as before the bug existed.

## Dispatch, and a live instance of the bug it fixes

The plan (`docs/superpowers/plans/2026-08-07-permission-denied-classifier-fix.md`) was dispatched
to Codex as a single job (`job-f71bad21`), covering both production files and three new test
files end to end. It landed cleanly — 5 real commits, full test suite green (1686 passed at that
point) — but the job's own final status came back `permission_denied`. Its last action, an MCP
`create_pull_request` tool call, was auto-denied in its sandboxed dispatch environment, producing
exactly the denial-shaped trailing event this PR corroborates against. Because the fix hadn't
merged to `main` yet, the *still-buggy* classifier misjudged its own author.

Per the standing "never trust job status alone" discipline, the branch was verified directly
(clean git log, pushed to `origin/dispatch/codex/job-f71bad21`) rather than treated as a failure,
and PR #770 was opened by hand. The incident is documented in the PR body as a concrete
before/after case for the fix.

## Review and merge

Reviewed via the sanctioned COMMENT-review fallback (issue #423 — all dispatched agents share one
GitHub identity, so `gh pr review --approve` fails as self-review on every dispatch-authored PR).
`synlynk pr check` passed clean. A real merge conflict surfaced against `tests/test_jobs.py`
where PR #768 (task-receipt protocol) had landed on `main` in the interim and inserted tests at
the same anchor point — resolved by hand, preserving all five tests from both PRs, full suite
re-verified (1705 passed) before the merge commit. Squash-merged as `2756395`.

## What this achieves toward #769 / #720

The classifier no longer treats a single ambiguous trailing event as sufficient proof of denial —
it now requires the *absence* of corroborating evidence across the whole log, and independently
across git state where available. Combined with the fail-closed empty-task guard and the
task-receipt protocol already shipped from #720, dispatched-job status reporting is now
meaningfully harder to fool in either direction (false denial, false success).

## Next goalpost

#769 stays open. Two sub-projects remain unscoped: a `SCOPE_VIOLATION` job status enforced by
comparing declared scope against actual changed files at completion (denying GitHub writes for
design-only jobs that drift into code changes), and documentation for safe caller construction
(passing task text as structured data rather than interpolated shell strings). Each needs its own
brainstorm → spec → plan cycle before dispatch.
