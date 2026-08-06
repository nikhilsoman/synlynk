---
title: "PR #731 — Synlynk UX 1.0: TUI + Vizor on Shared uxcore"
date: 2026-08-05
series: "Building the OS for Multi-Agent Development"
post: 99
pr: "#731"
merged: 2026-08-05
---

# 99: Synlynk UX 1.0 — TUI + Vizor on Shared uxcore

## Where we left off

In post #98 (PR #715), we analyzed the local-agent A/B test results and confirmed hardware limits were the gating factor. But in terms of user experience architecture, the system had reached a structural bottleneck. Prior to PR #731, Vizor was our sole visual HUD into repo state. Its internal data generator `generate_viz_data()` served as the implicit read path for web visualizations, but synlynk lacked a unified, testable UX core.

Specifically, there was no single write chokepoint, no Actor or role-based access control (RBAC) model, no feature-flag scoping, and no "Bring Your Own UX" (BYOUX) public interface. Terminal users had no live TUI, web users relied on ad-hoc HTTP handler routes directly calling `dispatch_agent`, and external extensions (such as chat notifications or external process monitors) had no event-stream interface to subscribe to. The goalpost was to unify both terminal and web interfaces on top of a shared, testable library kernel (`synlynk/uxcore.py`).

## What moved the goalpost

Implementation followed a straight execution of the approved design spec (`docs/superpowers/specs/2026-08-05-synlynk-ux-1.0-design.md`) and plan (`docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md`) without mid-stream strategic pivots. However, one key architectural decision shaped how the unified core functions:

Rather than having Vizor's HTTP server or the new curses TUI call `dispatch_agent` directly, all mutation operations (dispatching agents, approving PRs, killing jobs) were routed through a single internal chokepoint: `uxcore._execute_write()`.

This write chokepoint re-checks actor capabilities via `list_capabilities(actor)` before executing the underlying operation, and then appends a structured audit event to `.synlynk/events.jsonl`. Decoupling write execution from HTTP handlers and CLI dispatch loops is what made the reference Slack notifier and any future BYOUX consumer possible — third-party tools can consume structured events via `uxcore.subscribe()` without touching web handlers or parsing low-level subprocess stdout.

## What this PR shipped

PR #731 shipped the core foundation of Synlynk UX 1.0 across 18 modified files (+3251 lines, -201 lines), delivered via 12 dispatched implementation tasks across our multi-agent workgroup (Codex for CLI/plumbing, Grok for algorithmic surfaces, Agy for documentation/templates) plus a final regression-fix pass:

- **`synlynk/uxcore.py` (The Shared Core):**
  - Data accessors (`get_costs`, `get_gantt_data`, `get_jobs`, `get_fleet_state`) extracted out of Vizor's `generate_viz_data()`.
  - `Actor` and `Role` RBAC seams (`owner`, `member`, `viewer`), defaulting to `LocalActor` (`owner`).
  - `list_capabilities(actor)` manifest pattern mapping active feature flags and roles into capability lists.
  - Single write chokepoint `_execute_write(action, actor, **params)` handling dispatch, PR approval, and job termination while appending to `.synlynk/events.jsonl`.
  - `subscribe(event_types=None)` for live event tailing.
  - Static `FeatureFlags.is_enabled(flag, tier)` checks from `.synlynk/config.json`.
- **`synlynk/tui.py` (Terminal Surface):**
  - Curses-based terminal interface (`synlynk tui`) with 4 main panels: Fleet, Jobs, Costs, and Review.
  - Headless/pad-based render testing in `tests/test_tui_panels.py` requiring no live terminal.
- **`synlynk/viz.py` Rewire (Web Surface):**
  - Web routes refactored to delegate data fetching to `uxcore.get_*()` and write actions (dispatch/approve/kill) through `uxcore` write functions.
- **`synlynk/notifiers/slack.py` (Reference BYOUX Consumer):**
  - Minimal one-way Slack webhook notifier (`synlynk notify slack --webhook-url <url>`) tailing `uxcore.subscribe()`.
- **`docs/api/uxcore.md` (BYOUX Public Library Interface):**
  - Published public API documentation for external tools integrating with `uxcore`.
- **Command Taxonomy & Plumbing:**
  - Added `tui` to `synlynk/taxonomy.py` and regenerated CLI reference docs. `notify slack` is registered as a CLI subcommand but deliberately excluded from the taxonomy (it's a hook-triggered BYOUX consumer, not an orientation-gateway command).

### Lesson from the Final Regression Pass

The feature work was implemented across 12 individual dispatched tasks, each with task-level unit tests. However, when running the full test suite (`pytest`) before merging, three cross-cutting regressions surfaced:
1. A missing `'tui'` entry in `synlynk/taxonomy.py` caused taxonomy validation tests to fail.
2. An obsolete pre-rewire assertion in `tests/test_viz.py` was expecting direct `dispatch_agent` calls instead of `uxcore` dispatch.
3. `docs/reference/commands.md` was out of sync after registering the new CLI commands.

This served as an explicit reminder: task-scoped unit test passes are necessary but not sufficient — a full-suite regression run before branch completion remains mandatory.

## Brainstorm visuals used

No dedicated HTML visual companion was created in `docs/brainstorm/` for this specific UX 1.0 design spec. Prior art for Vizor's visual dashboard layout exists in `docs/brainstorm/bs21-vizor/`, which informed the original panel breakdown (Fleet, Jobs, Costs, Review) now mirrored 1:1 between the web interface and the new curses TUI.

## What this achieved on the path to autonomy

In our overarching arc to position synlynk as "the OS for multi-agent development", two user interfaces hand-rolling separate views into workspace state created maintenance overhead and inconsistent policy enforcement.

By consolidating both the TUI and Vizor behind `uxcore`, any future agent execution, governance check, or telemetry filter implemented in `uxcore` instantly applies across all user-facing surfaces. Furthermore, the introduction of `subscribe()` and `_execute_write` creates a clean, event-driven extension seam for external tools, autonomous notification relays, and multi-agent orchestrators.

## Next goalpost

With the BYOUX public interface established and validated by the reference Slack notifier, the next goalpost is exercising the `uxcore` seam with a second, non-Slack consumer (such as a webhook/relay consumer or the fleet-parity operability audit queued in project memory) to prove the abstraction cleanly generalizes beyond its first consumer.
