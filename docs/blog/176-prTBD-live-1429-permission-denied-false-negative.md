---
title: "LIVE-1429 — The Classifier That Overwrote a Real Success"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 176
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

PR #1440 made every home harness a conductor, not just Claude: dual-mode directives, constitutional precedence of runtime context over static `*.md`, and `synlynk home`. The goalpost at the end of that PR was that Agy, Codex, and Grok could drive dispatch → PR → review from an interactive session. That only works if `synlynk jobs` tells the truth about those writes.

## Strategic Shifts in This PR

None on product shape. This is the sixth recurrence of the #1377 job-status false-negative class, filed as LIVE-1429 after the job that implemented #1414's own regression test (`job-be18ebe7`) printed `OK (exit 0)`, touched `tests/test_agent_cli.py`, opened PR #1415, and then persisted `daemon_jobs.status = permission_denied`.

The issue claimed `gh_write_verified=1`. The live row is more precise: `requires_gh_write=1`, `gh_write_verified=unknown`, `gh_write_target=pr:1414`. 1414 is the *issue*; the PR that landed is #1415. `gh pr view 1414` cannot resolve a pull request, so the verifier correctly returns unknown. That targeting bug is a follow-up, not this fix. The status lie is independent of it.

## What This PR Shipped

Root cause: `_reconcile_daemon_jobs` applies GTV (job would be `done`, exit 0), then unconditionally overwrites status to `permission_denied` if the log matches `_log_has_permission_denied_signature`. `_reconcile_jobs` (the jobs.json path) already refuses that overwrite when `_job_has_real_work_landed(git_state)`. The daemon path did not. `_reconcile_terminal_jobs_json` then refuses to repair an already-terminal SQLite row, so `jobs.json: completed` and `daemon_jobs: permission_denied` stay split.

The fix applies the same corroboration the jobs.json path uses, plus the GitHub verifier: a log-shaped denial is not terminal when git work landed or `gh_write_verified == "true"`. Genuine denials with neither corroboration still mark `permission_denied`.

Tests: daemon ignore-denial when git work landed; daemon ignore-denial when the write is verified; daemon still-denied without corroboration.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Home-conductor mode from #1440 will dispatch more gh-write jobs from non-Claude sessions. If those jobs keep landing real PRs while the job board says `permission_denied`, heal, QA, and auto-resume will treat successes as failures. This closes the sixth fingerprint of that class on the daemon path. Remaining: `gh_write_target` bound to the issue number as if it were the opened PR (`pr:1414` vs PR #1415).

## Strategic Note: The Goal at the End of This PR

`synlynk jobs` daemon status should not call a corroborated success a permission denial. Next: execute the 24-PR triage (#1435), then the reviewer-worktree `pr check` miss (#1432). Do not start more home-harness features until those land.