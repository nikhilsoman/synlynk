---
title: "Daemon Jobs Learn the Same Ground Truth as CLI Dispatch"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 173
pr: "TBD"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

The Job Lifecycle Ground-Truth Verification epic (PRs [#126](https://github.com/nikhilsoman/synlynk/pull/126), [#127](https://github.com/nikhilsoman/synlynk/pull/127), and [#129](https://github.com/nikhilsoman/synlynk/pull/129)) established that a dispatched job's status must be checked against the work it actually left behind. The remaining goal was to make every execution engine obey that contract, including the daemon queue.

## Strategic Shifts in This PR

No strategic shift was needed. Issue #136 exposed a parity gap: the CLI reconciliation path had received the epic's isolation, git-state verification, and touched-file fixes, while daemon-dispatched jobs still used older state-only assumptions. This PR treats the two paths as one lifecycle contract.

## What This PR Shipped

Daemon jobs now persist `worktree_path` and `worktree_branch` in the SQLite `daemon_jobs` table. New databases receive the columns in the canonical schema, and existing databases receive guarded `ALTER TABLE` migrations following the repository's `PRAGMA table_info` pattern.

`dispatch_agent()` and `_dispatch_ready_jobs()` now write the per-job worktree metadata when a daemon job is launched. The subprocess already receives the isolated worktree as `cwd`; persisting that identity lets reconciliation survive daemon restarts without guessing from log paths.

When a daemon PID has disappeared and neither a raw wait status nor an exit sentinel is available, `_reconcile_daemon_jobs()` inspects the recorded worktree. Git activity produces the existing `failed_unverified` status instead of a false hard failure. Completion summaries use the real worktree touched-file list, preserving the same evidence used by the CLI path.

Regression tests cover missing-sentinel git evidence, isolated subprocess cwd and persisted metadata, and non-empty daemon touched-file summaries. The focused lifecycle selector and daemon reconciliation tests pass.

## Brainstorm Visuals Used

None — this work follows the approved lifecycle verification design contract.

## What This Achieved on the Path to Autonomy

The daemon can now recover truth after process loss or restart using the repository state that agents actually changed. Concurrent background jobs also have durable worktree identity, reducing cross-job interference and making their results inspectable instead of conflating queue bookkeeping with execution reality.

## Strategic Note: The Goal at the End of This PR

CLI and daemon dispatch now share the essential lifecycle guarantees: isolated execution, git-backed ambiguity detection, and evidence-backed file reporting. The next goalpost is operationally validating those guarantees across long-running daemon restarts and concurrent queue workloads.
