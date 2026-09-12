---
title: "PR titles that said Permissions and meant a real feature"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 179
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

The #1435 open-PR sweep closed a pile of `fix: ## Permissions (job-…)` siblings whose *code* had already merged. The remaining goalpost was the product bug that produced those titles: #1427 (and the same fingerprint on #1421).

## Strategic Shifts in This PR

None. The #1435 comment already named the mechanism: Agy dispatch prepends `## Permissions` plus a bullet list to the stored task, and auto-finalize takes `splitlines()[0]` as the PR title and body `Task:` line.

## What This PR Shipped

`_task_summary_line()` skips injected markdown sections (`## Permissions`, plus the other known dispatch headings) and their following list items, then uses the first remaining line. `_commit_subject_for_job` and `_maybe_open_worktree_pr` both use it. Agy still receives the permissions block first in the prompt (`test_dispatch_agent_injects_agy_permissions_header` unchanged).

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Reviewers can tell Agy auto-PRs apart without opening each one. Combined with the #1435 sibling closures, the `## Permissions` cluster should not grow.

## Strategic Note: The Goal at the End of This PR

#1427/#1421 closed. #1446 (pr-check sandbox write + pytest `-k`) is the remaining review-dispatch hygiene item.