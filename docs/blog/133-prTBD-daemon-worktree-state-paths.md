---
title: "Daemon State Belongs to the Repository, Not the Worktree"
date: 2026-08-29
series: "Building the OS for Multi-Agent Development"
post: 133
pr: "TBD"
merged: "status: open"
---

## The Broader Goal at the End of the Previous PR

The previous reliability work aimed to make GitHub-write dispatch dependable across the full daemon and worktree lifecycle. A daemon-owned GitHub App token cache was in place, but its filesystem location still depended on where the daemon process was started.

## Strategic Shifts in This PR (if any)

No strategic shift was needed. Issue #1228 exposed a boundary bug in the existing design: repository-wide daemon state had been treated as worktree-local state. The fix makes that ownership explicit by resolving state through Git's shared common directory.

## What This PR Shipped

`synlynk/daemon.py` now resolves the repository root with `git rev-parse --path-format=absolute --git-common-dir`. Normal repositories and linked worktrees map to the parent of the shared `.git` directory; bare-repository paths remain usable, and non-Git invocation falls back to the current working directory.

Both daemon classes use that root for pidfiles and logfiles, including the watch pidfile checked by the full daemon. GitHub App token refresh also scans the shared `.synlynk/github_apps` directory, so a daemon started from a worktree finds the same role credentials as one started from the main checkout.

Tests cover root parity between a main repository and linked worktree, daemon path construction, token discovery from a worktree, and the non-Git fallback.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Daemon lifecycle commands now observe one persistent identity across worktrees, and scheduled GitHub App token refresh continues operating when dispatch jobs use isolated worktrees. This removes a source of silent token-refresh no-ops and prevents daemon status from changing merely because the operator changed directories.

## Strategic Note: The Goal at the End of This PR

The next reliability goal is to keep every repository-wide daemon capability anchored to durable repository state while preserving intentionally worktree-local project artifacts.
