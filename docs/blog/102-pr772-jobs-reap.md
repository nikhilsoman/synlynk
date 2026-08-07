---
title: "PR #772 — jobs reap: Kill Zombie `running` Rows for Real"
date: 2026-08-07
series: "Building the OS for Multi-Agent Development"
post: 102
issue: 753
---

# `jobs reap` — Kill Zombie `running` Rows for Real

## Broader goal (end of previous PR)

PR #762 windowed `sentinel_crit` so lifetime `sentinel.md` history no longer kept platform ops RED. The scoreboard could see recent failures honestly — and immediately showed the next lie: hundreds of `daemon_jobs` rows stuck at `status=running` with dead PIDs.

## What moved the goalpost

A same-day ops triage reaped **482** zombies by hand (45 in the three main project DBs). STALL_NO_OUTPUT and HARNESS_INTERNAL_TIMEOUT killed processes and wrote CRITICAL sentinels but often **left the row running**. `_reconcile_daemon_jobs` also left dead PIDs as open-ended `unknown` (or skipped null PIDs). Manual SQL is not a product.

## What this PR ships

1. **`synlynk jobs reap`** — dry-run by default; `--apply` marks zombies `timed_out` / `exit_code=-9`; `--all-projects` walks every `~/.synlynk/projects/*/state.db`.
2. **Auto-reap on sentinel write** — when `_write_sentinel_alert` emits `STALL_NO_OUTPUT` or `HARNESS_INTERNAL_TIMEOUT`, parse `job-*` and flip still-running daemon rows immediately.
3. **Hardened `_reconcile_daemon_jobs`** — null PID and dead PID (including non-child processes) become `timed_out` instead of lingering `running` / vague `unknown`.
4. Helpers: `_pid_is_alive`, `mark_daemon_job_terminal`, `scan_zombie_running_jobs`, `apply_reap_zombies`, `auto_reap_job_from_sentinel`.
5. Tests for dry-run/apply, auto-reap via sentinel, CLI parser, and reconcile expectation update.

## On the long arc

Autonomous multi-agent dispatch needs a job table that matches process reality. Windowed sentinels (#751) fixed the alert log; `jobs reap` (#753) fixes the queue truth that platform ops L1 rates depend on.

## New goalpost

- Operators have a one-command hygiene path (`jobs reap --all-projects --apply`).
- Future STALL/TIMEOUT cannot recreate the 482-zombie pile without an auto flip.
- Still open: agy timeout root cause (#750), cost capture gaps (#752), full #701 epic.
