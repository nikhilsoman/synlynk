---
title: "PR #113 — BS-22 Vizor Efficiency Tab"
date: 2026-07-04
series: "Building the OS for Multi-Agent Development"
post: 43
pr: "#113"
merged: 2026-07-04
---

## The Broader Goal at the End of the Previous PR

With PR #110 (BS-16), the harness gained a comprehensive instrument panel inside the SQLite data layer and the terminal output of `synlynk status`. However, this capacity data was trapped inside the terminal and JSON serializers. 

The broader target was to integrate this data into the browser-based workspace dashboard—**Vizor** (`synlynk viz`). For Vizor to serve as a complete project management and orchestration dashboard, it needed to present not just a history of what happened (Gantt and Cost views), but a forward-looking representation of whether the agent fleet is structurally prepared for the next task.

## Strategic Shifts in This PR

Vizor is evolving from a retrospective event logger into a **predictive scheduler dashboard**. 

Before PR #113, the *Efficiency* tab in Vizor displayed post-hoc metrics: success rates, run times, and token cost curves. By enriching the dashboard with BS-16 capacity and capability data, the user is now presented with a clear visual representation of fleet readiness. It answers the critical orchestration question: *If I dispatch a Work or Ship task right now, which agent has the budget, version alignment, and cycle capability to execute it?*

## What This PR Shipped

This PR bridged the database status tables to the browser UI and resolved multiple critical bugs caught during the integration:

- **Enriched Vizor Efficiency Tab (`synlynk/viz.py`)**: Added multiple frontend components built with vanilla CSS and inline SVG elements:
  - **Headless Efficiency Banner**: Shows a large multiplier (e.g., `2.4x`) comparing headless run efficiency against interactive session baselines, complete with skeleton placeholder states.
  - **Fleet Header Card**: Displays the current active dispatch mode pill (e.g., `Mode: daily-grind` or `Mode: autopilot`) and the attached count badge (`3/4 attached`).
  - **Capacity Progress Bars**: Visualizes read, write, tool, and context budgets for all four primary agents (Claude, Agy, Codex, Grok) as relative progress bars normalized against the highest value in the fleet.
  - **Cycle Capability Matrix**: Renders a visually clean matrix showing support levels for all 6 SDLC phases using custom inline SVGs (green filled circles for `full` support, orange half-filled circles for `partial` support, and empty circles for `none`).
- **Stable CLI Subprocess Integration**: Wired `viz.py`'s data extraction pipeline to query `synlynk status --json` as a stable contract, decoupled from terminal-formatting layouts.
- **HarnessSnapshot Utility (`synlynk/hud.py`)**: Implemented the `HarnessSnapshot` class to mirror `JobSnapshot`. It provides a clean, read-only interface to extract `harness_status` records from `state.db` for the terminal monitor.

### Three Key Bugs Fixed in This PR

- **UNIQUE Constraint Migration Crash (`synlynk/db.py`)**: A previous migration attempt by Agy attempted to rename cycle values (e.g. renaming `plan` to `design`, `work` to `plan`). Because of overlapping names, this triggered SQLite `UNIQUE constraint failed` errors during migrations. This was fixed by removing the renames, keeping the original cycle names (Dream, Plan, Work, Ship, Maintain, Engage) clean.
- **Cycle Capability All-None Fallback Bug (`synlynk/status.py`)**: `_compute_cycle_capability()` was reading `row["support"]` (the BS-16 column, which was NULL for old migrated rows) and failing to fall back to `row["supported"]` (the original column). This resulted in all capabilities displaying as `none` for existing rows. Corrected the conditional logic to fall back to `row["supported"]`.
- **Status Command Crash**: Resolved an edge-case crash in the status CLI where incomplete telemetry or empty tables would crash during rendering.

## Test Approach

We added 7 comprehensive tests in `tests/test_vizor_efficiency.py` validating the HTML generator and API endpoints:
- Verifying the presence of the headless efficiency banner, capacity bars, and capability matrices in the rendered Vizor template.
- Asserting correct handling of placeholder states when database records are missing.
- Ensuring `generate_viz_data()` correctly extracts and packs the `ecosystem` dictionary.

## What This Achieved on the Path to Autonomy

By rendering fleet capacity and cycle capability directly on the visual dashboard, we have created a human-in-the-loop audit screen for the autonomous dispatch loop:
1. **Fleet Readiness at a Glance**: Users can visually audit which agents are suffering from version drift (warning badges) or are missing capabilities for specific SDLC phases.
2. **Predictive Budget Auditing**: With capacity bars, developers can see if their local token limits are near exhaustion before launching a large-scale story decomposition.
3. **Robust Migration Path**: Fixing the UNIQUE constraint bug secures the migration path from older versions of synlynk, ensuring state is preserved across releases.

## Strategic Note: The Goal at the End of This PR

Now that Vizor displays fleet capability and the status checks are live, we must address the robustness of the dispatch loop itself. As agents are upgraded (e.g. Agy moving from version 1.0.0 to 2.0.0), CLI flags change. We need the dispatch loop to be self-aware of these changes—triggering preflight gate failures if an agent's CLI contract has drifted, and resolving the resulting "TC-2" dispatch failures.
