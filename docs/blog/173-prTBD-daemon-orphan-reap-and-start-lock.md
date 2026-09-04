---
title: "PR TBD — Daemon Orphan Reap and Start Lock (#349)"
date: 2026-09-04
series: "Building the OS for Multi-Agent Development"
post: 173
pr: "TBD"
merged: —
---

## The Broader Goal at the End of the Previous PR

Recent work hardened onboarding, heal/TPM autonomy, and ephemeral swarm execution. The broader goal remained containerized and OS-level agent sandboxing: credential masking and containment across every dispatch. That arc assumes the daemon is a trustworthy supervisor — if it dies, the workspace must still know which billed agent processes are alive and must not accidentally run two supervisors at once.

## Strategic Shifts in This PR

No strategic shift. This is a correctness fix for two daemon-lifecycle gaps filed as gh:#349: orphaned children that survive a daemon crash with nobody left to reap them, and a classic check-then-act race on `daemon start` / `watch start` that can double-dispatch the same queued job.

## What This PR Shipped

**Gap 1 — orphaned child after daemon death.** Daemon-launched jobs use `subprocess.Popen(..., start_new_session=True)`, so the agent process is not in the daemon's process group. Reconciliation (`_reconcile_daemon_jobs()`) previously ran only inside the daemon poll loop. If the daemon itself died, running rows stayed `status='running'` forever and the live billed process disappeared from `synlynk status` / `daemon status`.

Fix: `_synlynk_daemon_child_main()` now calls `SynlynkDaemon._reconcile_orphans_on_startup()` before entering `_run_loop()`. That path calls the shared `_reconcile_daemon_jobs()` logic (not a parallel judgment): still-alive PIDs stay `running` (adopted/monitored); dead PIDs settle through the existing GTV path (`timed_out` / `failed_unverified` / etc.). Parallel work on gh:#136 that extends the same reconciler therefore stays compatible.

**Gap 2 — concurrent start TOCTOU.** `WatchDaemon.start()` / `SynlynkDaemon.start()` checked `_is_running()` then later re-exec'd and wrote the pidfile. Two near-simultaneous starts could both pass the check.

Fix: exclusive `fcntl.flock(LOCK_EX | LOCK_NB)` on a sibling lockfile (`<pidfile>.lock`, still resolved via `_daemon_state_path()` / `_repo_common_dir()`). The parent holds the lock across spawn until the child publishes a live pidfile (or a short timeout); the child then holds the lock for its lifetime. If the lock cannot be acquired, the existing "already running" message is printed — same UX, race closed.

Tests cover: alive orphan adopted on child startup; dead orphan reaped to `timed_out`; concurrent `start()` threads produce a single spawn; direct lock-helper exclusivity.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

A crashed or OOM-killed daemon no longer leaves billed agent processes invisible until a human finds them in `ps`, and laptop wake / launchd `RunAtLoad` races can no longer start two job-dispatch loops against the same queue. That is table-stakes supervisor honesty for any sandboxing story that depends on the daemon as the containment boundary.

## Strategic Note: The Goal at the End of This PR

Same active goal — containerized and OS-level agent execution sandboxing — with one fewer way for the supervisor itself to lie about what is running. Keep gh:#136 (git-state cross-check in the same reconciler) and gh:#355 (HTTP handler) merges narrowly scoped so they do not fight this change.
