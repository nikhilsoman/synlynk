---
decision_id: dec-r1-701consolidation
topic: "ROUND 1/4 — Is issue #935 the same bug the Job Truth epic already fixed, an incomplete fix, or a genuinely new gap?"
date: 2026-08-15
panel: [claude-direct-evidence]
status: approved
---

## Topic
Issue #701 named #331/#579 (status untruthfulness) and #426/#569/#577/#659 (gh-write
unreliability) as the evidence base, and a prior epics plan
(`docs/superpowers/plans/2026-08-09-job-truth-and-gh-write-epics.md`) shipped fixes
for several of them before v0.13.1 (PRs #857, #867, #868, #925-#929). Issue #935 was
opened AFTER those fixes shipped, describing a fresh reviewer-dispatch reliability
failure (3 of 4 PR-review dispatches failed same session). Did the prior fix not hold?

## Evidence (read directly from code + issue history, not self-reported)

- `synlynk/jobs.py:2049` `_reconcile_daemon_jobs()` — confirmed the Ground-Truth
  Verification (GTV) code (`_inspect_worktree_git_state`, `_worktree_files_touched`)
  IS wired into the production daemon-job path today, exactly as PR #867 claims.
  This is not a stale claim — it's present in the current tree.
- `synlynk/dispatch.py:356` `_build_subprocess_env()` — confirmed fail-closed identity
  isolation (`GH_CONFIG_DIR` pointed at an isolated dir, `GITHUB_TOKEN` popped) for
  `--requires-gh-write` IS implemented, matching PR #857 / issue #569's closure.
- `synlynk/doctor.py` — confirmed TC-6 (gh-auth preflight) IS implemented (`TC-6
  gh-auth` print line, `tc6_status` variable, docstring "TC-1..TC-6 compliance
  suite"), closing the doctor-preflight gap #701 described as missing.
- Issue #935's own second comment (2026-08-14, Nikhil, same day as filing) already
  root-caused the failure independently: all 3 non-clean jobs (job-d8c0de9f,
  job-ea123d9b, job-e273d565) share an identical `exit -1, 0 files touched` signature
  matching `_check_job_stall()` (`synlynk/dispatch.py:517`) exactly — a SIGKILL after
  the log file goes stale past `stall_timeout_minutes` (default 30). The comment
  explicitly retracts an earlier #577 (Codex sandbox) attribution as unconfirmed
  pattern-matching, not evidence from this run.
- `_check_job_stall()`'s escape hatch (lines 536-561) only recognizes evidence via
  `_inspect_worktree_git_state()` — local commits, dirty worktree, or remote pushes.
  A PR-review task (read plan → verify → test → `pr check` → post review → merge)
  produces **zero** git-state evidence until its very last step. The escape hatch
  structurally cannot fire for this task shape during the long verify/test phase.
- A same-day point-fix already landed: PR #939 ("fix: extend stall timeout for
  review dispatches", merged 2026-08-14T10:15:52Z) added
  `review_stall_timeout_minutes` (default 90) gated on `job.get("task_type") ==
  "review"` (`dispatch.py:527`).
- Confirmed `task_type` is a **manually-passed CLI flag** (`--task-type`,
  `cli.py:594`), never inferred from the dispatch prompt or from
  `--requires-gh-write`. `_classify_task_type()` in `synlynk/status.py` is a
  separate heuristic used only for cost estimation, not wired to the stall-timeout
  override.

## Conclusion

**Not a recurrence of the same bug, and not an incomplete fix of Problem 1 or
Problem 2 as #701 defined them.** Both cited epics held: GTV reconciliation and
gh-write identity fail-closing are verifiably present and correct in the current
codebase, and their originating issues (#569, #577) are closed. #935 is a **third,
structurally distinct failure mode** — premature-kill-by-stall-timeout — living in
a code path (`_check_job_stall`, pre-exit liveness detection) that neither epic
touched, because both were scoped to *post-exit* reconciliation (Problem 1) and
*environment/identity* correctness (Problem 2), not *pre-exit* liveness judgment.

The reason this reads as "the fix didn't hold" is that all three mechanisms
share one architectural flaw: **trusting an absence-of-signal proxy (dead PID,
stale log mtime, missing git diff) as evidence of task outcome, instead of
verifying real-world ground truth.** GTV fixed that flaw at the post-exit
reconciliation checkpoint. The stall-killer has the identical flaw at an earlier
checkpoint (mid-execution liveness) that was never in scope. The point-fix (PR
#939) treats the symptom (review tasks get killed) with a hardcoded task-type
string match and a wider timeout, not the underlying pattern (any task shape with a
long no-git-signal phase is vulnerable) — and depends on a human remembering to
pass `--task-type review`, the same "discipline not enforcement" gap already
flagged for GH-write routing elsewhere in this repo's CLAUDE.md.

## Decision
Treat #935 as a new problem (Problem 3: pre-exit liveness/stall-detection), not a
regression of #331/#579/#569/#577. Carry forward into Round 3 the question of what
a durable fix looks like, generalizing rather than special-casing further task
types.
