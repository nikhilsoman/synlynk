---
title: "PR TBD — BS-13 Workspace HUD"
date: 2026-07-03
series: "Building the OS for Multi-Agent Development"
post: 41
pr: "TBD"
status: draft
---

## The Broader Goal at the End of the Previous PR

synlynk had live job tracking, dispatch, and daemon health, but no terminal-native workspace HUD. The only built-in views were split across command-line job tables and the browser Vizor surface. The missing piece was a compact, always-available terminal monitor for the 6-cycle SDLC model.

## Strategic Shifts in This PR

The HUD work tightened the product boundary around a clear split:

- `synlynk viz` stays the historical browser dashboard.
- `synlynk watch` becomes the live terminal HUD.

That separation matters because the HUD is not a replacement for Vizor. It is the fastest possible ambient surface for current workspace state, with keyboard navigation and zero dependencies.

## What This PR Shipped

This change introduced the first pass of the workspace HUD stack:

- `synlynk.dispatch_agent()` now records a `cycle` field in each job record.
- `synlynk/hud.py` adds `JobSnapshot` for read-only access to `.synlynk/jobs.json`.
- `FrameBuffer` provides a buffered ANSI diff renderer so only changed rows are re-emitted.
- `HUDRenderer` now owns the error and narrow-terminal states used by the terminal surface.
- `synlynk.cli.cmd_watch()` replaces the old watch-daemon subparser with a HUD loop, keyboard handling, alternate-screen rendering, and clean exit behavior.

The implementation stayed within the standard library. No `curses`, no `rich`, and no extra runtime dependency chain.

## Test Approach

I drove the change with focused tests for:

- dispatch job records carrying `cycle`
- `JobSnapshot` filtering and summaries
- buffered diff rendering behavior
- HUD error and narrow-width states
- `synlynk watch` missing-file handling

The regression slice for existing dispatch and job behavior stayed green after the changes.

## What This Achieved on the Path to Autonomy

This is a coordination primitive, not just a UI feature. The terminal now has a native view of live workspace state that can be refreshed, filtered, and navigated without leaving the shell. That makes the workspace itself feel persistent in a way that a command log never does.

The `cycle` field also gives the dispatcher and the HUD a shared vocabulary for lifecycle-aware routing. That is the basis for the later full HUD layout and live stream work.

## Strategic Note: The Goal at the End of This PR

The next step is to finish the richer layout components and live stream mode, then promote `synlynk watch` into a polished ambient control surface for the workspace.
