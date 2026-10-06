---
title: "PR TBD — Completion oracle reads the PR the task actually named"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 252
pr: "TBD"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR TBD — Completion oracle reads the PR the task actually named

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs a dispatch to move from implementation to a trusted review
verdict on GitHub state alone. The GOVERNS velocity plan's role check landed
first. The completion oracle was the remaining reason a real review could look
like `insufficient_evidence`.

## Strategic Shifts in This PR (if any)

No strategy change. `--issue` stays the GOVERNS link. It is no longer allowed
to stand in for a different pull request named in the task.

## What This PR Shipped

- Dispatch stores `gh_write_target` as the PR named in the task when that
  number is not the `--issue` link, and records it on `daemon_jobs.cross_branch_pr`.
- The terminal check calls `gh pr view <N> --json reviews,commits,headRefName`
  and keeps events at or after the job's start time. A review-only job with an
  empty worktree completes from that review. A fix job that pushed onto another
  PR completes from a new commit on that PR.
- When the PR head is this job's own branch, or no cross-branch PR was
  recorded, completion still uses the local diff.
- Tests cover the #2056 mismatch (`--issue 2051` vs PR #2054), a fresh commit
  on another PR, and the unchanged in-worktree path.

Plan: `docs/superpowers/plans/2026-10-06-governs-velocity-unblock-plan.md` §1.
Design: `docs/superpowers/specs/2026-10-06-governs-velocity-unblock-design.md` §3.1.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

A review dispatch can be trusted when the review lands on the PR the task
named, without a manual `gh pr view` to overturn a false
`insufficient_evidence` verdict.

## Strategic Note: The Goal at the End of This PR

The next velocity items are reviewer-logged cost provenance and the GOVERNS
preflight warning. This PR does not merge itself; cross-harness review still
closes #2056.
