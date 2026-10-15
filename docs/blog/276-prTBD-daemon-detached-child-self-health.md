---
title: "gh:#2261 — Catch a dead detached daemon before the backlog stalls"
date: 2026-10-15
series: "Building the OS for Multi-Agent Development"
post: 276
pr: TBD
status: open
author: "synlynk team"
version: "0.25.2-dev"
tags: [posts]
type: pr
---
# gh:#2261 — Catch a dead detached daemon before the backlog stalls

The previous goalpost (PR #2324) fixed the immediate crash: daemon child entry points now always `chdir` into the canonical repo root, so a cleaned-up dispatch worktree can no longer delete the process's cwd out from under `_repo_common_dir()`. That stopped the recurrence of the Oct 3 dormancy crash. It did not close the supervision gap that let the daemon stay dead for ten days with no alert.

## What changed

`synlynk daemon start` still re-execs a detached child. launchd's own wrapper exits 0 as soon as that child is spawned, so `KeepAlive` never sees the later crash. PR #2324 made the child survive disposable worktrees; this PR makes the platform notice when it does not.

**Defense in depth on re-exec.** `_daemonize_via_reexec` now treats a disposable `/worktrees/` (or `.claude/worktrees/`) cwd as unsafe. It re-resolves through `_repo_common_dir(strict=True)` before `Popen`, and fails closed if the canonical root is itself disposable. `SYNLYNK_DAEMON_WORKSPACE_ROOT` is always set to the pinned cwd.

**Self-health-check.** `check_daemon_health()` (already called from `synlynk status`) now probes the synlynk daemon pidfile as well as the watch daemon:

- zombie pidfile → `CRITICAL` / `ZOMBIE_SYNLYNK_DAEMON`
- service unit installed but process stopped → `ERROR` / `DAEMON_DETACHED_DEAD` (the exact #2261 dormancy shape)

**Doctor liveness.** New `_hc_daemon_liveness` joins `HEALTH_CHECKS`: fail on zombie or installed-but-dead, warn when simply stopped with no unit.

## Tests

`pytest -q tests/test_daemon_token_refresh.py tests/test_daemon_supervision_discovery.py` — 37 passed, including disposable-cwd re-pin, synlynk start cwd pin, zombie/service-dead sentinel alerts, and doctor liveness cases.

## Goalpost

Daemon health for goal-bd5eaa14 now has both halves of the #2261 fix: the child cannot inherit a disposable worktree cwd, and status/doctor surface a dead detached child instead of silent dormancy. Remaining work on the autonomy arc is operational — keep a supervised daemon running and confirm `_autonomy_pass` keeps the backlog moving without manual CLI driving.
