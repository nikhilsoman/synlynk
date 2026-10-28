---
title: "Vizor always-on Design Specification"
date: 2026-10-28
status: Accepted
author: "Grok (Home Conductor)"
goal: "goal-e3840370"
epic: "#2650"
milestone: "unscheduled (after v0.26.6)"
arc: "platform"
issue: "#2650"
---

# Vizor always-on

## Status

Accepted 2026-10-28. Nikhil signed off approach B on issue #2650 (comment 6460369007) with "go ahead". This cut does not bump VERSION, does not edit CHANGELOG, and does not cut a tag. v0.26.7 stays reserved for Jantt write-back.

Parent epic #2458 stays open. Memorable port list stays `[33333, 44444, 55555, 22222, 11111]`.

## Problem

v0.26.6 records a heartbeat only after `run_forever` is already inside its loop. The installed launchd unit starts `python -m synlynk.vizor_daemon` with cwd `~/.synlynk/vizor-daemon`. Importing `synlynk` calls `_project_root()` and raises the gh:#1831 `RuntimeError` because that directory is not a git checkout. `KeepAlive` restarts the crash. `probe_health` never runs. No `heartbeats.db` is written. `synlynk viz` only opens a browser when a pid is already alive.

The heartbeat row is not a supervisor. A dead process cannot restart itself by reading it.

## Decision

One machine-scoped daemon, installed from the interpreter that runs `synlynk viz --install` or `synlynk viz --ensure`. launchd (and systemd, where present) owns boot and crash restart. An external timer owns a stale beat, a missing beat, a clean stop, and a version or unit mismatch. Worktrees are clients of the port file. They do not get their own daemon.

## First cut

1. **Import.** When `SYNLYNK_VIZOR_DAEMON=1` or `sys.argv[0]` is `vizor_daemon.py` / `vizor_ensure.py` (including `python -m synlynk.vizor_daemon`, which sets argv0 to that file), skip `_project_root()`, skip the legacy import fan-out, and set `DB_PATH` to `os.devnull`. A later argv entry that only names the module does not qualify. Do not create or migrate a product `state.db`. Any other import in a non-git directory still raises the gh:#1831 error.
2. **Units.** Rewrite the launchd or systemd unit when the interpreter or package root changes. The daemon plist sets `SYNLYNK_VIZOR_DAEMON=1` and `PYTHONPATH` to `_synlynk_import_root()`. Reload with `bootout` (best effort) then `bootstrap`, then `kickstart -k`. Install a 60s `StartInterval` timer, label `com.synlynk.vizor-ensure`, program `python -m synlynk.vizor_ensure`, same env and cwd, no `RunAtLoad` (so the timer does not re-enter `install` during bootstrap).
3. **Heartbeat version.** Add `version TEXT` to `daemon_heartbeats` (`ALTER TABLE` when `PRAGMA table_info` lacks it). `upsert_beat`, `read_beat`, and the SSE heartbeat payload include it. The daemon writes `synlynk._constants.VERSION`.
4. **`synlynk viz --ensure`.** No-op when the unit text matches, the pid is alive, the beat status is `running`, and `version` matches. Otherwise rewrite the units and restart, unless the same reason already failed 3 times inside the last 10 minutes. Attempts older than 10 minutes drop out of that count. Tests monkeypatch launchctl. A healthy ensure does not call it.
5. **Stall watch.** A daemon thread waits on `stop_event` for the grace (default 120s) before it looks at the beat. It calls `os._exit(1)` only when the event is still unset and the beat is older than that grace. `run_forever`'s `finally` sets the event first, so a normal shutdown cannot kill the test process.
6. **Task fence.** Call sites pass `http://127.0.0.1:<port>/w/<slug>/overview.html` when the port file exists and `cwd` is inside a checkout. Otherwise the hub URL `http://127.0.0.1:<port>/`. No port file means no hint. `render_task_fence` does not read the port file and does not call launchctl.
7. **Log cap.** When `daemon.log` exceeds 1 MiB, keep the tail. `ensure` trims before it restarts so a crash loop cannot refill a 70 MiB log unchecked. The backoff above is what stops the timer from kickstarting the same failure forever.

## Out of scope

Hosted Vizor, Gantt `/events`, memorable port changes, retitling #2470, the release-docs git-diff flake, PyPI trusted publishing, and the VS Code `package.json` publish failure.
