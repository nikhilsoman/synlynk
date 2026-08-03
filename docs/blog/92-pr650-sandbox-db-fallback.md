---
title: "PR #650 — Sandbox DB Fallback: Don't Crash When $HOME Is Read-Only"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 92
pr: "#650"
issue: "#648"
merged: —
---

## The Broader Goal at the End of the Previous PR

synlynk's project state lives at `~/.synlynk/projects/<md5>/state.db` so all worktrees of one repo share a single ledger on one machine. That design is correct for local orchestration. What it never fully accounted for is a *dispatched agent running inside its own sandbox*: different `$HOME`, often a read-only mount outside the workspace, and no copy of the orchestrator's `.synlynk/config.json` or DB.

Issue #648 made that gap a hard crash. A Codex review job in `cc-videoreframing` ran `synlynk status` and died with `sqlite3.OperationalError: unable to open database file`. Local `status`/`doctor` on the same machine were fine — so investigation time was burned re-checking a migration that was never broken.

## Strategic Shifts in This PR

None on the long arc. This is a reliability fix on the same theme as #645 (state that is real on one machine and absent/broken elsewhere): fail soft in sandboxes instead of looking like a corrupted install.

One nuance vs. the issue body's source snapshot: main already had an `OperationalError` fallback on `_get_db()` (from the #452-era rewrite). The remaining crash window was narrower but real — `os.makedirs` on a read-only `$HOME` raises plain `OSError(EROFS)`, which is *not* a `PermissionError` subclass, so the previous `except PermissionError` never fired. When the directory already existed, connect's `OperationalError` *was* caught — but with no warning, so a fresh empty local DB looked like silent data loss rather than "this machine has no project state."

## What This PR Shipped

1. **`_get_db()` catches `(OSError, sqlite3.OperationalError)`** — one branch covering EROFS/ENOSPC/`PermissionError` and "unable to open database file."
2. **One-line stderr warning on fallback** distinguishing "no project state found on this machine" from genuine corruption, and naming both the primary and fallback paths.
3. **Regression tests** (`tests/test_get_db_sandbox_fallback.py`): EROFS from makedirs, PermissionError, connect OperationalError, and re-raise when both primary and fallback fail.

Out of scope (called out in #648 suggestion 3, not implemented here): whether dispatched jobs should call DB-backed subcommands at all, or how sandbox config null-`org`/`repo` defaults should be provisioned. Those need a dispatch-harness design decision, not a quiet DB patch.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Agents that run `synlynk status` / `doctor` inside a sandbox no longer die with an opaque SQLite error that looks like a migration regression. They get a local empty DB plus an explicit warning. That keeps investigation on real product bugs instead of environment mismatches — the same failure-mode family as #645, closed as a crash instead of a silent no-op.

## The Goalpost at the End of This PR

Sandbox DB access is degrade-safe. Still open: deliberate policy for "should a dispatched job ever read/write project state," and provisioning `.synlynk/config.json` (or a read-only view of the orchestrator DB) into the sandbox when the intent is shared state rather than isolation.
