---
title: "Vizor request thread and render heartbeat"
date: 2026-10-30
status: Accepted
author: "Grok (Home Conductor)"
goal: "goal-e3840370"
epic: "#2650"
milestone: "unscheduled (after v0.26.6)"
arc: "platform"
issue: "#2650"
---

# Vizor request thread and render heartbeat

## Status

Accepted 2026-10-30. Nikhil signed off the diagnosis in the home session: stop the heartbeat stream from occupying the only request thread, and stop a long render from being treated as a dead daemon. This cut does not bump VERSION, does not edit CHANGELOG, and does not cut a tag.

## Problem

Overview opens `EventSource` on `/w/<slug>/api/daemon/stream`. `serve_daemon_stream` holds that socket and pings every poll interval. `run_forever` serves with `http.server.HTTPServer`, one request at a time. While that stream is open, `board.html` and every other view sit in the accept queue. The shell has already set the breadcrumb, and the iframe keeps the Overview document.

Separately, `poll_once` writes the heartbeat before each workspace and then calls `refresh_workspace`. One render of the synlynk cache takes longer than the 120s stall grace. `_watch_for_stall` calls `os._exit(1)`. launchd starts the process again about every four minutes.

## Decision

1. `make_httpd` returns `ThreadingHTTPServer` (`daemon_threads` is already true on that class). An open stream no longer blocks the next request. `run_forever` uses `make_httpd`.
2. `keep_render_beat` pumps the same running beat while `refresh_workspace` is on the stack, at `min(grace/4, 30s)`. The pump stops when the render returns, or after `RENDER_LIMIT_S` (30 minutes, `SYNLYNK_VIZOR_RENDER_LIMIT_S`). Past that limit the stall watch still exits, so a wedged render is not immortal.
3. A stale beat with no live render still calls `os._exit(1)`.

## Out of scope

The workspace refresh `TypeError` (`NoneType` divided by `int`), hosted Vizor, Gantt `/events`, the memorable port list, VERSION, and the release tag.
