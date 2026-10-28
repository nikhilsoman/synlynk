---
goal: "goal-e3840370"
epic: "#2641"
milestone: "v0.26.6"
arc: "platform"
---

# Plan: v0.26.6 Vizor heartbeat, SSE, and read-only sentinel inspection

**Status:** Accepted 2026-10-28. Implement the tasks below. Do not cut the v0.26.6 tag in this PR.
**Goal:** `goal-e3840370`
**Epic:** [#2641](https://github.com/nikhilsoman/synlynk/issues/2641)
**Parent:** [#2458](https://github.com/nikhilsoman/synlynk/issues/2458)
**Release:** v0.26.6
**Authored:** 2026-10-28
**Branch:** `feat/grok/v0266-vizor-heartbeat`
**Worktree:** `.worktrees/feat-grok-v0266-vizor`
**Base:** `92ec2ef7`

Do not dispatch implementation tasks and do not edit `synlynk/` until Nikhil accepts the spec. One implementation PR follows. The version bump and release notes are a later release PR.

Each task is test-first. Tests point `SYNLYNK_VIZOR_DAEMON_HOME` at a temporary directory. They do not read or write `~/.synlynk/vizor-daemon`.

## Task 1 — Heartbeat database

Files: new `synlynk/viz/heartbeats.py`, new `tests/test_vizor_heartbeats.py`.

- `open_heartbeats(home: Path)` creates `heartbeats.db` and the table in spec section 4.
- A second open does not raise and does not add a second table.
- `daemon_id(home)` creates `daemon_id` once and returns the same uuid.
- `upsert_beat(...)` replaces the single row. `harness` other than `vizor` raises `ValueError`.
- `read_beat(home)` returns the row plus a computed status using the stale window.

## Task 2 — Beat writer on the poll loop

Files: `synlynk/vizor_daemon.py`, `tests/test_vizor_daemon.py`.

- At the start of a cycle, mark the row `stale` when the recorded pid is dead.
- Around each slug inside `poll_once`, set `active_task` to that slug.
- When `poll_once` returns, set `active_task` to `idle` and increment `cycle_count`.
- `run_forever`'s `finally` writes `status=stopped` before the process returns.
- A SQLite error in the writer is logged and does not change `poll_once`'s per-slug results.

## Task 3 — Dead pid and failed bind

Files: `synlynk/vizor_daemon.py`, `tests/test_vizor_daemon.py`, existing `tests/test_vizor_memorable_ports.py` stays green without edits unless an import path forces one.

- If `is_running()` is true, `run_forever` logs the existing pid and port and returns before `HTTPServer`.
- Otherwise the bind port is `find_available_vizor_port(preferred or DEFAULT_PORT)`.
- Do not change `MEMORABLE_VIZOR_PORTS`.
- Test the taken-preferred-port case with two local sockets, not by binding 33333 on the operator machine.

## Task 4 — SSE route

Files: `synlynk/viz/server.py` and the workspace handler in `synlynk/vizor_daemon.py`, new `tests/test_vizor_daemon_stream.py`.

- GET `/api/daemon/stream` emits one `heartbeat` event and then a comment heartbeat.
- GET `/w/<slug>/api/daemon/stream` also emits one `sentinel` event from a fixture file under that workspace's repo.
- Unknown slug returns 404.
- A `?path=` query is ignored. The route never opens a client-supplied path.
- The test client is `http.client` against an ephemeral `127.0.0.1` port. No browser.

## Task 5 — Overview inspection panel

Files: `synlynk/viz/data.py`, `synlynk/viz/overview.py`, a focused test beside the existing overview tests.

- Extend the alert dict with `raw_line`, `occurrences`, `first_seen`, and `last_seen` from the parser. Keep the current severity normalization.
- Render each active banner row as a button that opens a panel with those fields.
- The generated HTML contains no `method="post"`, no `/api/sentinel/clear`, and no control whose label is Run.
- Subscribe the page to `/w/<slug>/api/daemon/stream` and update the chip and list. On `EventSource` error, leave the server-rendered HTML.

## Task 6 — Audit freeze

No new view modules.

- Do not add Models or Settings pages.
- Do not edit `synlynk/viz/gantt.py`, `architect.py`, `observatory.py`, `board.py`, or `efficiency.py` in this PR.
- The implementation PR description links spec section 7 as the population audit. That section is the deliverable.

## Done when

- `pytest tests/test_vizor_heartbeats.py tests/test_vizor_daemon.py tests/test_vizor_daemon_stream.py tests/test_vizor_memorable_ports.py` passes.
- `pytest tests/test_four_point_attribution.py` passes.
- `synlynk pr check` from the implementation worktree passes before review.
- Reviewer is a different harness and model. Merge stays inside that reviewer's headless job.
