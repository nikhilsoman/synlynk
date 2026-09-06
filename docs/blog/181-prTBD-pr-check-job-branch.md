---
title: "pr check from a job branch that is not the PR"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 181
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

#1449 let review sandboxes run `synlynk pr check` without writing shared `todo.md`. The remaining hole was that the same command still failed closed on every dispatched reviewer: the job worktree is on `dispatch/<harness>/job-<id>`, not the PR branch, so `gh pr view` and `gh pr checks <branch>` cannot see CI.

## Strategic Shifts in This PR

None. #1432 already named the fix: do not depend on branch identity.

## What This PR Shipped

`_current_pr_number` still tries `gh pr view`, then looks up HEAD via `GET /repos/.../commits/{sha}/pulls`. `synlynk pr check --pr N` skips lookup. `_extract_verified_by_ci` / the QA gate use `gh pr checks <number>` when a PR number is known, so a `dispatch/codex/job-*` checkout of the same SHA sees the same CI as the PR branch.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Dispatched QA can run `synlynk pr check` from the job worktree and get a real CI verdict instead of "undeterminable — failing closed."

## Strategic Note: The Goal at the End of This PR

#1432 closed. Identity (#1436) is the remaining review-dispatch item: QA `actions:read` cannot rerun flaky CI, and merge jobs still classify as `review_posted` on the board.
