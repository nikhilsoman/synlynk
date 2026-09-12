---
title: "LIVE-1429 leftovers — the verifier still could not see the write"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 177
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

PR #1441 stopped `_reconcile_daemon_jobs` from overwriting a corroborated `done` with `permission_denied`. LIVE-1429 closed. The goalpost was: job status should match GitHub ground truth for gh-write jobs.

## Strategic Shifts in This PR

#1441 was necessary and not sufficient. The review and merge dispatches for #1441 itself proved it:

- `job-1c68bfd4` posted an APPROVED review as `synlynk-synlynk-qa[bot]` and still stored `gh_write_verified=false` / `permission_denied`.
- `job-be622768` squash-merged #1441 and stored `gh_write_expect=pr_open` / `gh_write_verified=unknown`.
- `job-be18ebe7` (the original LIVE-1429 job) stored `gh_write_target=pr:1414` for an issue, while the PR was #1415.

Those are verifier contract bugs, not classifier overwrites. Filed as #1442 plus two fingerprints found while checking whether #1441 actually closed the class.

## What This PR Shipped

1. **#1442.** When `expect=pr_open` and `gh pr view N` cannot resolve a pull request, search PRs `linked:issue-N` created after `since` (optional author match).
2. **Author login.** GraphQL `login` is `synlynk-synlynk-qa`; stored expect_author is `synlynk-synlynk-qa[bot]`. Compare after stripping a `[bot]` suffix.
3. **Naive `since` is local wall time.** `daemon_jobs.started_at` has no offset. Treating it as UTC made a 03:54Z review look older than a 09:19 IST start.
4. **Expect order.** Check merge before "opens a PR". Prompts that say `Do not open a new PR` after a merge instruction no longer classify as `pr_open`.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

#1441 made a success stay `done` when corroboration exists. This PR makes corroboration actually fire for the three gh-write shapes we just ran (open a new PR for an issue, post a review, merge a PR). Without it, `synlynk jobs` still trains operators to ignore the board.

## Strategic Note: The Goal at the End of This PR

Job-status truth for gh-write is one cluster: classifier guard (#1441) + target/expect/author/time (#1442 and this PR). Next P0 is still the 24-PR triage (#1435), after this lands.