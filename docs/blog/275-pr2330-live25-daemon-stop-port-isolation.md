---
title: "LIVE-25: the daemon wasn't crashing, a test was killing it"
date: 2026-10-15
series: "Building the OS for Multi-Agent Development"
post: 275
pr: 2330
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
type: pr
---
# LIVE-25: the daemon wasn't crashing, a test was killing it

The previous goalpost (PRs #2322/#2323/#2324/#2326/#2327) wired a hybrid interval+idle autonomy-pass trigger into the daemon's poll loop. That work is only useful if the daemon stays alive. Minutes after `synlynk daemon start`, it didn't — with zero log output and no traceback, which looked like a crash and undermined the autonomy-pass wiring directly.

## What changed

Filed as gh:#2329 (LIVE-25). Following `superpowers:systematic-debugging`'s Iron Law, no fix was attempted before root cause was confirmed.

**Root cause, confirmed via instrumentation, not inference.** A temporary `sigaction(SA_SIGINFO)` handler (plain Python `signal.signal()` doesn't expose a sender PID — only the kernel-level `siginfo_t.si_pid` does) captured the actual process that was terminating the daemon. It was `pytest -q`, running as a verification step inside an unrelated, concurrently dispatched job's own worktree.

**The mechanism.** `SynlynkDaemon.stop()` has a legitimate fallback for reclaiming an orphaned daemon when it can't resolve a `target_pid` from a pidfile or lock owner: it shells out to `lsof -ti :<port>` via `_find_pid_listening_on_port(self.HTTP_PORT)` and SIGTERMs whatever it finds. That lookup is system-wide and has no way to confirm the match is actually this daemon's own orphan — a sibling test (`test_daemon_stop_kills_orphaned_process_on_http_port` in `tests/test_daemon_liveness_1572.py`) already exercises this path correctly, binding an ephemeral port and monkeypatching `HTTP_PORT` away from the real default (27471) before calling `stop()`.

One test in `tests/test_control_plane_daemon_health.py` — `test_synlynk_daemon_stop_cleans_stale_lock_when_no_pidfile` — skipped that isolation. It constructed a bare `SynlynkDaemon()`, left `HTTP_PORT` at the real production default, and called `.stop()`. On a machine running a real synlynk daemon bound to 27471 (the normal case), any `pytest -q` collecting this file would find that real daemon via `lsof` and kill it — cleanly, with a plain SIGTERM, which is exactly why it looked like silent death rather than a crash. This explained every observed symptom: correlation with concurrently running dispatched jobs (their own verification step triggers it), and a daemon with no concurrent jobs surviving 22+ minutes idle.

**The fix.** This is a test-isolation bug, not a defect in `stop()`'s orphan-reclaim logic, which is intentional and otherwise correctly tested. `test_synlynk_daemon_stop_cleans_stale_lock_when_no_pidfile` now binds an ephemeral port and monkeypatches `daemon.HTTP_PORT` to it, mirroring the already-correct sibling test. A new regression test, `test_synlynk_daemon_stop_stale_lock_path_never_probes_real_default_http_port`, guards the invariant directly: it asserts the daemon instance's `HTTP_PORT` is isolated away from `SynlynkDaemon.HTTP_PORT` before `stop()`'s port-fallback path runs, with a docstring citing gh:#2329 and explaining why the port-reclaim mechanism itself must stay.

TDD was followed red→green: the new test failed first (`assert 27471 != 27471`) without the isolation line, then passed once it was added. Full `tests/test_control_plane_daemon_health.py` suite: 8 passed. Broader daemon-related check across `test_control_plane_daemon_health.py`, `test_daemon_liveness_1572.py`, and `test_synlynk.py -k daemon`: 47 passed, 502 deselected, nothing else broke.

## Goalpost

The autonomy-pass wiring from the previous PR cluster can now actually run unattended — the daemon no longer gets killed by an unrelated test suite's own verification step running elsewhere on the same machine. The next measurement is whether a daemon left running during normal dispatch traffic now survives indefinitely, the way the pre-fix idle-only runs already did.
