---
goal: "goal-e3840370"
epic: "#2641"
milestone: "v0.26.6"
arc: "platform"
---

# v0.26.6 — Vizor daemon heartbeat, live SSE, and read-only sentinel inspection

**Status:** Proposed. Implementation is blocked until Nikhil signs off on this file.
**Authored:** 2026-10-28
**Author:** Grok, Mode A Home Conductor
**Base:** `origin/main` `92ec2ef7` (tag `v0.26.5`)
**Release:** v0.26.6, target tag date 2026-10-29
**Epic:** [#2641](https://github.com/nikhilsoman/synlynk/issues/2641)
**Parent:** [#2458](https://github.com/nikhilsoman/synlynk/issues/2458)
**Governing goal:** `goal-e3840370` (active). Ledger outcome stays the Vizor control plane. This release does not retitle the goal.
**Plan:** `docs/superpowers/plans/2026-10-29-vizor-platform-review-and-sentinel-monitoring.md`

This spec is the delta against code already on `main`. It does not re-commission the Vizor HUD, the port ladder, or the sentinel writer.

---

## 1. Decision

v0.26.6 adds three things:

1. A single heartbeat row for the machine-scoped Vizor daemon.
2. A localhost Server-Sent Events stream of that row, plus the active sentinel snapshot for one workspace.
3. A read-only inspection panel on the existing Overview canvas.

Signed off on 2026-10-28:

- Only `synlynk/vizor_daemon.py` writes the heartbeat. The watch daemon in `synlynk/daemon.py` keeps its existing `sre_heartbeat` telemetry and does not get a row.
- The panel does not write `sentinel.md`, does not write `state.db`, and does not run a reproduction command.
- Tracking is issue **#2641**, a sub-issue of **#2458**. **#2470** stays titled for the v0.26.2 autonomy gate. Its retitle is blocked by **#2635** and is not part of this release.
- Product code waits for sign-off. The tag date stays 2026-10-29.

The heartbeat database is **not** a workspace `state.db` migration. `vizor_daemon` is machine-scoped (`DAEMON_HOME`, default `~/.synlynk/vizor-daemon`) and must not attach its liveness to whichever repo happened to start it. The table lives in `DAEMON_HOME / "heartbeats.db"`.

---

## 2. What already shipped

Verified on `92ec2ef7`. These stay. This release does not rewrite them.

| Surface | Where | Contract that stays |
|---|---|---|
| Port ladder | `synlynk/viz/constants.py` | `MEMORABLE_VIZOR_PORTS = [33333, 44444, 55555, 22222, 11111]`. `find_available_vizor_port` falls through to `8721`. |
| Daemon home | `synlynk/vizor_daemon.py` | `PIDFILE`, `PORTFILE`, `LOGFILE` under `DAEMON_HOME`. `is_running()` uses `os.kill(pid, 0)`. |
| Poll | `poll_once` | One failure does not stop the next registered workspace. |
| Static alerts | `synlynk/viz/data.py`, `overview.py`, `efficiency.py` | Overview renders up to six active alerts. Efficiency counts them. Both read `.synlynk/sentinel.md` through `_iter_sentinel_alerts`. |
| Gantt relay client | `synlynk/viz/gantt.py` | `EventSource('/events')` listens for `goal_realigned` and `governs_stage_advanced`, and ignores failures. |
| Write auth | `synlynk/viz/server.py` | POST paths call `authorize_local_request`. GET does not. |
| Bind | `run_forever` | `127.0.0.1` only. |
| Sentinel format | `synlynk/sentinel.py` | Parsed fields are severity, code, message, first/last seen, occurrences, and `raw_line`. There is no separate reproduction-command field. |

---

## 3. What is still broken, and in scope

`run_forever` binds `port or DEFAULT_PORT` and does not call `find_available_vizor_port`. A taken `33333` raises from `HTTPServer` and launchd `KeepAlive` restarts that crash. The ladder exists and is unused on this path.

`run_forever` also starts a second listener when a live pid is already recorded. A dead pid is already treated as not running by `is_running()`, and the next successful start overwrites the pidfile. The hole is the live-pid collision and the failed bind.

This release fixes only that hole. It does not add or remove ports.

---

## 4. Heartbeat store

File: `DAEMON_HOME / "heartbeats.db"`.

Schema:

```sql
CREATE TABLE IF NOT EXISTS daemon_heartbeats (
    daemon_id TEXT PRIMARY KEY,
    pid INTEGER NOT NULL,
    harness TEXT NOT NULL,
    status TEXT NOT NULL,
    last_beat_at TEXT NOT NULL,
    cycle_count INTEGER NOT NULL,
    active_task TEXT
);
```

`daemon_id` is a uuid stored in `DAEMON_HOME / "daemon_id"`, created once per daemon home. It is not the pid.

`harness` is the literal `vizor` for every row this release writes. No other value is legal.

`status` is one of `running`, `stale`, `stopped`.

`last_beat_at` is UTC ISO-8601 with a `Z` suffix.

`active_task` is the workspace slug currently inside `poll_once`, or `idle` between cycles. It is not a story id and not a client-supplied path.

`cycle_count` increments by one when `poll_once` returns.

Stale rule, computed by readers and by the beat writer at the start of a cycle: `running` when the pid is alive and `last_beat_at` is newer than two poll intervals; `stale` when the pid is dead or the beat is older than that; `stopped` only when the process exits `run_forever` through its `finally` path. Default poll interval is 15 seconds, so the default stale window is 30 seconds.

There is one row. A new process with the same `daemon_id` updates that row. It does not insert history.

The beat writer catches its own SQLite and filesystem errors, logs one line, and does not fail `poll_once`.

---

## 5. SSE stream

New GET route on the Vizor HTTP server, both at the hub and under a workspace:

- `/api/daemon/stream`
- `/w/<slug>/api/daemon/stream`

Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Bind stays `127.0.0.1`. The route does not require the local write token. It does not accept a filesystem path. An unknown slug returns 404.

Event types:

- `heartbeat` — the single row, plus the current port from `PORTFILE`.
- `sentinel` — only on the workspace route. The payload is the active alerts for `WorkspaceContext.repo_path / ".synlynk" / "sentinel.md"`.

Each event is `event: <type>\ndata: <json>\n\n`. The server sends a comment line every poll interval when nothing changed, so proxies do not close the socket. A client disconnect ends that generator only.

This route is not `/events`. Gantt's relay client stays as it is. Implementing the governance relay is out of scope.

The Overview page subscribes with `EventSource` to the workspace stream and updates the heartbeat chip and the alert list without reloading the canvas. A failed `EventSource` leaves the server-rendered HTML in place.

---

## 6. Read-only inspection

Overview alert rows become buttons. Activating one opens a panel in the same page.

The panel shows severity, code, message, first seen, last seen, occurrences, active/resolved, and `raw_line`. The message is the reproduction text the emitter already wrote. The panel does not parse a shell command out of it and does not offer a Run control.

Data comes from the existing parser. `synlynk/viz/data.py` gains the fields the panel needs (`raw_line`, `occurrences`, `first_seen`, `last_seen`) and still does not write. Resolved rows stay out of the banner. The panel can show a resolved row only when the client already has that row from a snapshot that included it. This release does not add a history browser.

No new POST route. No call to `_write_sentinel_alert` or the sentinel clear helpers from Vizor.

---

## 7. View audit

The kickoff named seven views. The signed scope is to fill a hole only where a module exists and already loads the field. This audit is the result. No further population work is in this release.

| View | Module on `92ec2ef7` | Disposition |
|---|---|---|
| Overview | `synlynk/viz/overview.py` | In scope for the heartbeat chip and the inspection panel only. |
| Architecture | `synlynk/viz/architect.py`, `canvases.py` | Already rendered from the graph. No change. |
| Observatory | `synlynk/viz/observatory.py` | Already a module. No change. |
| GOVERNS Board | `synlynk/viz/board.py`, `GET /api/board` | Already a module. No change. |
| Efficiency | `synlynk/viz/efficiency.py` | Placeholder when economics data is absent is the correct empty state. No invented rows. |
| Models | none | Deferred. Do not add a page. |
| Settings | none. FTUE writes `.synlynk/config.json` from `cmd_viz` setup. | Deferred. Do not add a page. |

Gantt (`synlynk/viz/gantt.py`) is v0.26.7. This release does not edit it.

---

## 8. Out of scope

- Changing `MEMORABLE_VIZOR_PORTS` or the legacy `8721` fallback.
- Heartbeats for `synlynk/daemon.py`, relay, or dispatch workers.
- Ack, clear, triage writes, or schedule edits.
- Serving `/events` for Gantt.
- #1778 graphify refresh UI, #354 sentinel dedupe, #2500 pattern hardening, #2635 classifier regression.
- Hosted Vizor, auth changes, and any bind other than `127.0.0.1`.
- Version bump, CHANGELOG, and README. Those belong to the release PR after this work merges.
- Per-PR blog posts.

---

## 9. Tests

Test-first, against a temporary `DAEMON_HOME`. No launchd, no live port above the test's bound ephemeral port, no read of the operator's `~/.synlynk/vizor-daemon`.

- Migration creates the table and a second open is a no-op.
- A beat during `poll_once` sets `harness=vizor`, increments `cycle_count`, and stores the slug as `active_task`.
- A dead pid is reported `stale`. A clean `finally` writes `stopped`.
- `run_forever` uses `find_available_vizor_port` when the preferred port is taken, and returns without binding when `is_running()` is already true.
- The stream route emits one `heartbeat` event and, for a known slug, one `sentinel` event whose body matches a fixture `sentinel.md`.
- The Overview fixture contains the inspection fields and no Run control, no form, and no `fetch` POST.

---

## 10. Release sequence

1. This spec and the plan merge only after sign-off, as a docs PR, or they stay on the branch until sign-off and then fold into the implementation PR. They do not ride along with product code that Nikhil has not accepted.
2. One implementation PR from `feat/grok/v0266-vizor-heartbeat` or a successor branch cut from current `origin/main`.
3. Non-author review. Merge from the reviewer's headless job, not from this home session.
4. A separate release PR bumps `VERSION` to `0.26.6`, updates `CHANGELOG.md` and `README.md`, and flips the roadmap row. Human release authority stays required.
5. The rollup comment goes on **#2641** and **#2458**.
