---
title: "PR #867 — Daemon Jobs Ground-Truth Verification (Epic A1)"
date: 2026-08-09
series: "Building the OS for Multi-Agent Development"
post: 110
issues: "331,579"
---

# Daemon Jobs GTV — Stop Lying About Success

## Broader goal

Epic A1: `daemon_jobs` status must match process + git reality so operators stop hand-verifying every dispatch.

## Problem

`_reconcile_daemon_jobs` reaped dead PIDs but wrote summaries with **0 files** and treated missing exit as bare `timed_out`/`unknown` even when the worktree had commits — #579/#331. GTV lived only on the legacy JSON job store.

## Shipped

1. **GTV on daemon reconcile** — inspect worktree git state; classify:
   - remote-only activity → `done` / exit 0  
   - local activity, no exit → `failed_unverified` + files  
   - no activity → `timed_out` -9  
2. **Summaries include real `files_touched`** (not always `[]`).  
3. **Ops** — `zombie_running` count + finding when status=running and PID dead/null.

## Next

A2 cost completeness (#752); A3 home/headless (#740).
