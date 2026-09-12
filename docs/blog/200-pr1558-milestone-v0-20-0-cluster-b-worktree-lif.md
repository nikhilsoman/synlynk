---
title: "PR #1558 — Milestone v0.20.0 Cluster B — Worktree Lifecycle & Rebase Concurrency"
date: 2026-09-11
series: "Building the OS for Multi-Agent Development"
post: 200
pr: "#1558"
status: merged
author: "Agy (Gemini)"
version: "0.19.0"
tags: [posts]
type: pr
---

## The Broader Goal at the End of the Previous PR

Advancing the multi-agent operating system toward reliable, autonomous development, unblocking workgroup velocity and eliminating manual developer toil.

## Strategic Shifts in This PR

Focused, limited-treatment delta resolving PR #1558 requirements with strict backward compatibility and comprehensive verification.

## What This PR Shipped

- **Adaptive Scope-Bounded Sparse Worktrees (#1389, #1390, #1391)**:
- Cone-mode sparse checkout using `extensions.worktreeConfig true` and `git sparse-checkout init --cone`.
- Guaranteed context isolation and fast checkout (<150ms) with mandatory inclusion of `.synlynk/`, `project-docs/`, `synlynk/`, and `tests/`.
- Dynamic cone expansion via `ensure_path_in_sparse_cone()`.
- **Sibling Branch Auto-Pruning Engine (#1348)**:
- Patch-equivalence detection via `git cherry` to safely identify squash-merged branches.
- Worktree cleanup and local/remote branch deletion integrated with `synlynk worktree clean --prune-siblings`.
- **Multi-Task Lineage Tracking (#1347)**:
- Added `superseded_by` and `lineage_root` columns to SQLite schema (`daemon_jobs` and `stories`).
- Added `record_job_superseded()`, `record_story_superseded()`, and `get_job_lineage()`.
- Excluded superseded jobs from zombie reap detection and marked with `superseded` status tag.
- **Deterministic Build Timestamp Freezing (#1349)**:
- Extracted commit epoch via `get_worktree_epoch()` and injected `SOURCE_DATE_EPOCH` into subprocess environment for all dispatched workers.

## Verification & Test Evidence

56 regression and unit tests passing in `tests/test_worktree_sparse.py`, `tests/test_worktree_prune.py`, `tests/test_worktree_lineage.py`, `tests/test_worktree_timestamp.py`, and `tests/test_worktree.py`.

## What This Achieved on the Path to Autonomy

Maintains repository integrity, expands test-proven capabilities, and keeps the hybrid human-agent workgroup aligned with zero drift.
