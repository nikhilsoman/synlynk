---
title: "PR #117 — Live Job Observatory"
date: 2026-07-05
series: "Building the OS for Multi-Agent Development"
post: 45
pr: "#117"
merged: 2026-07-05
---

## The Broader Goal at the End of the Previous PR

While the workspace HUD (PR #106) provided a terminal-native dashboard for monitoring the 6-cycle SDLC model, it only tracked local repo executions. The long-arc goal of synlynk is **autonomous multi-agent dispatch** across multiple repositories and agents. To make this legibility possible, we needed a unified operator panel: a read-only, near real-time live board displaying running jobs across all repos in a single workspace.

## Strategic Shifts in This PR

The introduction of the Live Job Observatory shifts synlynk from a single-repository task runner into a multi-repository operator panel. For the first time, operators can see all active, queued, and completed jobs across different repositories grouped by repo and execution stage. 

Instead of jumping between directories or tracking separate terminal windows, the Observatory aggregates telemetry and statuses into a singular model. This is the strategic foundation that makes multi-repo, multi-agent collaboration legible, giving the human controller (or supervising orchestrator agents) a high-level view of the entire fleet.

## What This PR Shipped

This PR delivers the complete data, CLI, and web UI layers for the Live Job Observatory:

- **`synlynk/observatory.py`**:
  - `build_job_observatory_snapshot()`: Pulls job logs and telemetry entries to build a comprehensive, structured snapshot of workspace activity.
  - `_merge_telemetry()`: Merges and aggregates input/output token counts, request rates, and costs across all active and historical jobs.
  - `_job_repo_fallback()`: Resolves repository names from Git origin URLs when not explicitly declared in job configurations.
- **`synlynk/hud.py`**:
  - `render_observatory_panel()`: Groups active jobs by repository and execution stage (e.g., `running`, `queued`, `done`, `failed`), displaying runtime ages, accrued costs, and token consumption statistics.
- **CLI & TUI (`synlynk watch --live`)**:
  - Refined the terminal HUD to render the Live Observatory panel directly beneath the HUD header.
- **Web Interface (`synlynk viz`)**:
  - Added the **Observatory** tab to the local browser dashboard.
  - Generates `observatory.html` in the Viz cache.
  - Configured 10-second auto-refresh polling of `observatory-snapshot.json` to keep the UI live.
- **Review Cycle Adjustments**:
  - During the R1/R2 review cycles, we resolved a critical telemetry crash risk when loading malformed JSON.
  - Cleaned up a redundant column in the unified job board layout to optimize screen space.

## Brainstorm Visuals Used

- `docs/brainstorm/bs13-workspace-hud/` — Brainstorming materials for the workspace HUD, which directly informed the design of the Observatory's grid layout and grouping mechanisms.

## What This Achieved on the Path to Autonomy

In a fully autonomous multi-agent ecosystem, agents will spawn subagents, delegate tasks across different repositories, and coordinate parallel pipelines. Without a unified ledger and observability panel, this behavior would quickly become an unmanageable black box.

The Live Job Observatory solves the legibility problem. It provides:
1. **Fleet Legibility**: Clear visualization of which agent is running which task, in what repo, at what cost.
2. **Cost Attribution**: Unified telemetry rollup summing total cost, total requests, and total input/output/context tokens across the workspace.
3. **Execution Age Tracking**: Highlighting runtimes to quickly surface stuck processes or execution stalls before they drain token quotas.

## Strategic Note: The Goal at the End of This PR

With the Live Job Observatory shipped, synlynk has the instrumentation required to monitor complex, multi-agent operations. The next focus is **agent autonomy, permissions, and handoffs (BS-12)**. We need to define the protocol for how agents ask for permission to run commands, how they manage their capability ratings, and how they hand off context-crossing stories to other specialists in the workgroup.
