---
title: "PR #TBD — BS-21 Vizor: Local Browser Workspace Dashboard"
date: 2026-07-03
series: "Building the OS for Multi-Agent Development"
post: 39
pr: "#TBD"
merged: status: open
---

# PR #TBD — BS-21 Vizor: Local Browser Workspace Dashboard

## The Broader Goal at the End of the Previous PR

By the end of v0.10.0, synlynk had crossed the daily-driver threshold. The install, migrate, release, and status commands were in place, the state database was the source of truth, and the CLI could now support a real workflow instead of a pile of one-off utilities. That got us through the "can I run this every day?" milestone.

The next question was sharper: after day 1, how do users come back to synlynk on day 2, day 3, and day 7? The gap was not another command. It was the absence of a visual surface, no ambient workspace awareness, and no fast way to understand the state of the multi-agent system at a glance.

## Strategic Shifts in This PR (if any)

Vizor started life as BS-6 `git-connectome`, a codebase dependency graph tool. That framing was useful, but during the brainstorm it became obvious that the real D1-D2 retention hook was not a graph viewer for its own sake. It was a local workspace dashboard that made synlynk feel present every time a user opened the browser.

That was the strategic shift: from an interesting utility to the primary ambient surface. The design work reflected that change. We iterated through five Gantt versions, then two tube map variants, before the layouts locked in. The result was not a single-purpose report, but a browser tab that could hold the workspace story together.

## What This PR Shipped

Vizor v1 shipped as a local-first browser dashboard implemented in `synlynk/viz.py`, with the whole surface generated from the workspace state and served locally.

What landed:

1. A new `synlynk/viz.py` module at roughly 3,500 lines, centered on `generate_viz_data()`, which reads `state.db` plus Vizor support files into one serializable data structure.
2. Database-backed data sources for `roadmap_arcs`, `roadmap_phases`, `stories`, `cost_entries`, telemetry JSON, and sentinel notes, so the dashboard reflects actual workspace state instead of a separate projection.
3. Six HTML generators, each returning a self-contained page with `window.VIZOR_DATA` embedded. The browser does not need an API server for view rendering.
4. `VizorHandler`, an `http.server` subclass that serves the generated `viz-cache/` directory and accepts `POST /note` for note persistence.
5. `_live_js()` polling every 60 seconds plus browser notifications, so the tab can update itself when workspace state changes.
6. A three-prompt FTUE flow that writes setup state to `synlynk/config.json` on first run.
7. The `synlynk viz` command with `--serve`, `--generate`, `--open`, and `--stop` flags.
8. Five primary views:
   - Gantt, with accordion drill-down, stage bars, pencil notes, and zoom-to-stage behavior.
   - User Journeys, with split-pane docs linked from `docs/journeys/*.md`.
   - Architect Map, rendered as a `vizor-tube.json` SVG tube map.
   - Effort & Cost, with SVG bar charts.
   - Efficiency, with agent cards, a sentinel timeline, and recent runs.
9. A note system where `POST /note` writes `viz-notes.json`, then injects those notes into the next `generate_context()` call. That makes Vizor annotations bidirectional: visual note to AI context, and AI context back into the workspace memory loop.
10. Twenty-one tests across `tests/test_viz.py` and `tests/test_viz_serve.py`, covering data extraction, rendering, empty states, note loading, and server behavior.
11. Brainstorm visual artifacts committed under `docs/brainstorm/bs21-vizor/`, including [viz-gantt-v5.html](../brainstorm/bs21-vizor/viz-gantt-v5.html) and [viz-tube.html](../brainstorm/bs21-vizor/viz-tube.html).
12. The local-first implementation path stayed intentionally simple: `state.db` reader -> HTML f-strings -> stdlib `http.server`, with no external dependencies and no remote rendering step.

## Brainstorm Visuals Used

The locked-in designs came from the BS-21 brainstorm set, especially:

- [viz-gantt-v5.html](../brainstorm/bs21-vizor/viz-gantt-v5.html)
- [viz-tube.html](../brainstorm/bs21-vizor/viz-tube.html)

Those were the key references after the five Gantt iterations and two tube map variants converged on the final layout language. The v5 Gantt direction established the right-aligned task labels, the drill-down interaction model, and the pencil-note affordance. The tube map reference established the station-weighting logic and the visual grammar for the architect view.
In the tube map, station sizing follows the connection count directly: `r = 4 + segs*2`, so denser hubs read as visually heavier nodes instead of flat labels.

## What This Achieved on the Path to Autonomy

Vizor v1 shipped as the primary D1-D2 retention surface.

That matters because a user who runs `synlynk viz` after installing it can now see the workspace state immediately: dreams, costs, agent health, live runs, and annotations. They do not need to read logs or query the database to answer the basic question, "What is happening in my workspace right now?"

This also makes the system easier for agents to inhabit. The dashboard is not a static report. It is a local ambient surface that can show state, accept notes, and feed those notes back into the next generation cycle. That closes the loop between observation and action.

## Strategic Note: The Goal at the End of This PR

The new goalpost is D3-D7 retention.

Next up:

1. Daily brief mode: `synlynk viz --brief`
2. Scan delta surfacing: what changed since the last Vizor run
3. v1.0 workspace FTUE: a guided loop that walks a new user through dispatch, observation, note-taking, and re-dispatch

Vizor now owns the day-2 return path. The next step is to make it the habit-forming surface for the rest of the week.
