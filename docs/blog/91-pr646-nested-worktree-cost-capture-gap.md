---
title: "PR #646 — Fix Nested-Worktree Cost-Capture Gap"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 91
pr: "#646"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 (post #90) closed the loop on harness capability drift and regression classification. However, telemetry collection and cost tracking depend on reliably recording every subagent job's token usage in the central `state.db` at `~/.synlynk/projects/<hash-of-main-repo-root>/state.db`. Prior to PR #646, when an agent dispatched a job from within an existing job's git worktree, cost logging suffered from an isolated DB resolution bug.

## Strategic Shifts in This PR

Previously, DB path resolution (`_resolve_db_path`), migration state checking (`_is_migrated`), and project-docs directory resolution (`_synlynk_project_docs_dir`) relied on `git rev-parse --git-common-dir` or local CWD without absolute path formatting. When executing inside a nested git worktree, `git rev-parse --git-common-dir` could return relative paths or fail to correctly anchor to the main repository root. This caused cost accounting entries (`cost_entries`) to be written into an isolated, orphaned `state.db` instance inside the worktree instead of the shared primary repository ledger.

The strategic shift in this PR introduces `_project_root()` in `synlynk/__init__.py` using `git rev-parse --path-format=absolute --git-common-dir`. By resolving the git common directory with `--path-format=absolute` and deriving its parent directory (`..`), all path resolutions (DB path, migration markers, `.synlynk/project-docs` directory, and migration command paths) are strictly anchored to the shared main repository root across all git worktrees.

## What This PR Shipped

- **Shared Project Root Resolver** (`synlynk/__init__.py`): Added `_project_root()` and `_get_project_root()` using `git rev-parse --path-format=absolute --git-common-dir` to locate the absolute main repo root directory, falling back to CWD outside git.
- **Centralized DB & Path Resolution** (`synlynk/__init__.py`): Updated `_resolve_db_path()`, `_is_migrated()`, and `_synlynk_project_docs_dir()` to use `_project_root()`, guaranteeing all linked git worktrees share the same canonical `state.db` at `~/.synlynk/projects/<key>/state.db`.
- **Migration Path Anchoring** (`synlynk/db.py`): Updated `cmd_migrate` to resolve `.synlynk/config.json` and `.synlynk/.synlynk_migrated` against `_get_project_root()`.
- **Worktree Cost Capture Regression Test** (`tests/test_cost_ledger.py`): Added `test_update_costs_uses_shared_state_db_from_linked_worktree` which creates a linked git worktree, executes `update_costs()` from inside the worktree, and verifies that the cost row lands in the shared `state.db`.

## Brainstorm Visuals Used

None — standard bugfix addressing root-cause path resolution logic.

## What This Achieved on the Path to Autonomy

By anchoring state DB resolution and migration sentinel checks to the absolute git common parent directory, multi-agent dispatch pipelines operating across multiple concurrent git worktrees maintain 100% telemetry fidelity and shared cost ledger recording.

## Strategic Note: The Goal at the End of This PR

With cost capture reliably anchored across all worktree topologies, cost tracking and quota enforcement remain accurate regardless of how deeply nested subagent dispatches are spawned.
