---
title: "Daemon detached children leave disposable worktrees and check their own pulse"
date: 2026-10-15
series: "Building the OS for Multi-Agent Development"
post: 276
pr: TBD
status: open
author: "synlynk team"
version: "0.25.2"
tags: [posts]
type: pr
---
# Daemon detached children leave disposable worktrees and check their own pulse

The previous goalpost (PR #2330 / LIVE-25) stopped unrelated pytest runs from SIGTERM-ing a live daemon via a shared HTTP port. That restored a daemon that could stay up — but gh:#2261 still described a quieter failure mode: a detached child that had been re-exec'd from inside a disposable dispatch worktree, then died days later when Worktree Hygiene deleted that cwd, with launchd never noticing because its supervised wrapper had already exited 0.

## What changed

This PR closes the remaining #2261 surface that PR #2324's unconditional child-main `chdir` did not cover:

1. **`_daemonize_via_reexec` remaps disposable cwd.** If the invoking shell or the requested `cwd` sits under `worktrees/` (or `.claude/worktrees/`), the spawn resolves the shared git common dir via `_canonical_repo_root_from` *before* detaching, then pins both `Popen(cwd=…)` and `SYNLYNK_DAEMON_WORKSPACE_ROOT` to that persistent root. A disposable path that cannot resolve raises instead of launching a child that will later crash on deleted cwd.

2. **Detached-child self-health check.** Each poll tick, a child with `_SYNLYNK_DAEMON_CHILD=1` runs `_self_health_check()` (live `getcwd` + `git rev-parse --git-common-dir`). On failure it cleans pidfile/start/lock identity and returns from `_run_loop` so an outer KeepAlive or a later `daemon start` can recover, instead of looping into `_refresh_github_tokens` / `_repo_common_dir` crashes.

3. **`start()` returns bool; CLI exits 1 on failure.** `WatchDaemon.start()` / `SynlynkDaemon.start()` now return `True` when the child is healthy (or already running) and `False` when the pidfile never becomes live. `synlynk daemon start|restart` raises `SystemExit(1)` on `False` so supervised wrappers that key off a failed exit can react.

4. **`check_daemon_health` covers SynlynkDaemon zombies.** The existing watch-daemon ZOMBIE_DAEMON path now also alerts when `daemon.pid` exists but the process is dead.

Regression coverage lives in `tests/test_daemon_token_refresh.py` (disposable remap, cwd-gone and git-gone health checks, run-loop exit + identity cleanup, `start()` False path, SynlynkDaemon zombie alert). Daemon-focused suites: 51 passed.

Supersedes the stale open PR #2264 (same intent, based on pre-#2324/#2327 main and would have regressed the unconditional child-main chdir and autonomy-pass wiring).

## Goalpost

With cwd pinning (#2324), autonomy-pass wiring (#2327), LIVE-25 test isolation (#2330), and this detached-child self-health path, the daemon side of goal-bd5eaa14 is ready for an unattended soak: `synlynk daemon status` should stay healthy across worktree create/delete cycles, and a dead detached child should either exit cleanly for KeepAlive or surface as ZOMBIE_DAEMON rather than silently starving the backlog→schedule→dispatch pipeline.
