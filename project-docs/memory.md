# synlynk Memory

## Project Overview
- **Name:** synlynk
- **Description:** Multi-agent development orchestration and execution platform.
- **Languages:** Python
- **Directories:** bin, docs, project-docs, synlynk, tests, website

## Decisions
- **2026-09-24 [Vizor Master Goal Consolidation]:** Created canonical master goal `goal-e3840370` (*Consolidated Vizor Master Control Plane: Unified Interactive Web HUD, GOVERNS Lifecycle Board, Architectural Views, Onboarding Journey, and Hosted Fleet Radar*) to consolidate and track all past, present, and future Vizor stories across 7 GOVERNS lifecycle stages. 20 stories linked (6 done, 14 active/future). [@agy]
- **2026-09-24 [Vizor Readonly DB & Worktree Network Resilience]:** Projections in `viz_views.py` must never fail if SQLite connections are opened in read-only URI mode; in-memory extractions remain valid even if projection caching fails. `viz.py` worktree signals pass `gh_available=False` to eliminate hundreds of sequential network calls during view generation. [@agy]

## Architecture
- **Vizor Web HUD Architecture:** Modular client/server architecture with OS-supervised persistent daemon (`synlynk.vizor_daemon`), multi-workspace hub (`/`), 7-stage GOVERNS board (`board.html`), Option C dual-pivot timeline (`gantt.html`), 4 BS-6 architectural views (Product, Logical, Infra, World), and token-authenticated local API.

