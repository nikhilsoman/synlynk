---
title: "daemon start stopped crying wolf about stale log lines"
date: 2026-10-15
series: "Building the OS for Multi-Agent Development"
post: 276
pr: TBD
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
type: pr
---
# daemon start stopped crying wolf about stale log lines

The previous goalpost (PR #2330 / LIVE-25) stopped an unrelated pytest run from SIGTERM-ing a healthy daemon via the shared HTTP port reclaim path. With the daemon actually staying up, soak testing immediately surfaced a different false alarm: `synlynk daemon start` printing `⚠ Failed to start daemon: SystemExit: 143` and `synlynk watch is also running`, then `synlynk daemon status` confirming a healthy process seconds later.

## What changed

Filed as gh:#2333. Root cause was two compounding bugs in `WatchDaemon.start()` (shared by `SynlynkDaemon`), plus a third stale-state check on the same start path:

1. **`_await_child_pidfile()` used a flat 2.0s cutoff.** Under load the re-exec child often published its pidfile just after that window, so `start()` took the failure branch even though the child came up fine.
2. **The failure branch tailed the entire append-only logfile.** A quiet successful spawn writes nothing new, so the last non-blank line from an old diagnostic session (here: leftover `SystemExit: 143` from the LIVE-25 investigation) was misreported as today's error.
3. **`SynlynkDaemon._prepare_start()` treated `watch.pid` existence as "watch is running".** A dead pidfile triggered the dual-poller warning with zero live watch processes.

**The fix.** Pidfile wait now polls with exponential backoff up to a 10s ceiling. Before spawning, `start()` records the logfile byte offset and only reads lines appended after that watermark; if nothing new appeared, it reports an honest readiness-timeout message. The watch check now requires a live PID (or live lock owner), matching `_health()` liveness rules.

**Tests.** New file `tests/test_daemon_start_false_failure_2333.py` covers: stale log not misreported on a silent failed wait; backoff past 2.0s; stale watch pidfile ignored; live watch pidfile still warns; only newly appended log bytes reported on a real failure. Related suites (`test_daemon_liveness_1572`, `test_control_plane_daemon_health`, `test_daemon_token_refresh`) stay green: 47 passed.

## Goalpost

Daemon start diagnostics now match reality: a late-but-successful child is waited for, stale log tails stay in the past, and a leftover `watch.pid` no longer claims a concurrent poller. Next soak pass can trust `Failed to start` as a real signal while the autonomy-pass loop from the prior PR cluster keeps running unattended.
