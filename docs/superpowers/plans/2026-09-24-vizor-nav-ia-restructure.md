# Vizor Navigation & Information Architecture Restructure Implementation Plan

**Goal:** Implement the approved design spec (`docs/superpowers/specs/2026-09-22-vizor-nav-ia-restructure-design.md`) under `goal-70317121` to modernize Vizor navigation, add the per-workspace Overview canvas and cross-workspace Activity Stream, organize views into structured categories (STATUS, TOPOLOGIES, PROJECTIONS, TELEMETRY), and replace the top menu bar with location breadcrumbs.

---

## 1. Scope & Architecture

### Sidenav Architecture (Two-Tier Native HTML `<details>` Accordion)
- **Tier 1 (Account Scope):**
  - `<details name="tier1" open>` for `PERSONAL` (teal/green header).
  - `<details name="tier1">` for `TEAM` (blue header, renders "Coming soon" stub).
  - `<details name="tier1">` for `ENTERPRISE` (blue header, renders "Coming soon" stub).
- **Tier 2 (Workspaces in Personal):**
  - One `<details name="workspace" {open}>` per registered workspace.
  - Header: workspace name, open stories badge count (`<span class="count-badge">N</span>`).
- **Tier 3 (Category-Grouped Views in Active Workspace):**
  - **STATUS**: Board (`board.html`), Gantt (`gantt.html`)
  - **TOPOLOGIES**: Architect Map (`tube.html`), Infra View (`infra.html`)
  - **PROJECTIONS**: Product (`product.html`), Logical (`logical.html`), World (`world.html`)
  - **TELEMETRY**: Effort & Cost (`effort.html`), Efficiency (`efficiency.html`), Observatory (`observatory.html`), Agent Roles (`roles.html`)

### Breadcrumbs & Corner Actions
- **Location Breadcrumb Bar:**
  - `Personal › <workspace> › <category> › <view>`
  - Clicking `Personal` navigates to the cross-workspace Activity Stream (`activity.html`).
  - Clicking `<workspace>` navigates to the Workspace Overview (`overview.html`).
- **Corner Actions:**
  - Settings icon slot (sub-project 2 placeholder).
  - FTUE replay icon slot (sub-project 4 placeholder).
  - Light/Dark/System theme switcher.

### New Canvas 1: Workspace Overview (`overview.html` / `generate_overview_html()`)
- **Alerts/Sentinel Banner:** Renders when active alerts exist in `.synlynk/sentinel.md`.
- **Stat Cards Row:** Active Goals, Open Stories, Running Jobs, 7-Day Burn/Cost.
- **Goal Progress Rollup:** Active GOVERNS goals with completion percentage bars.
- **Recent/Active Jobs Feed:** Last 5-8 jobs with agent badge, duration, status, and PR links.
- **Jump-to-View Shortcuts Grid:** 4-category cards linking directly to views.

### New Canvas 2: Tier Activity Stream (`activity.html` / `generate_activity_stream_html()`)
- Filter chips: Per-workspace toggle chips + per-type filter chips (`goal`, `story`, `epic`, `pr`, `job`).
- Chronological stream of activity cards across all registered workspaces.

---

## 2. Implementation Tasks

### Task 1: Overview Canvas Data Extraction & Generator
- Implement `generate_overview_html(data, port)` in `synlynk/viz.py`.
- Extract goals from `uxcore.get_goals()`, active stories count, running jobs from `daemon_jobs` table, and 7-day cost burn from `cost_entries`.
- Write `overview.html` in `viz_module._write_cache()`.

### Task 2: Activity Stream Data Extraction & Generator
- Implement `generate_activity_stream_html(data, port)` in `synlynk/viz.py`.
- Extract and format events from `events.jsonl`, `stories`, `goals`, `daemon_jobs`, and Git commits.
- Write `activity.html` in `viz_module._write_cache()`.

### Task 3: Sidenav Accordion & Master Shell Restructure
- In `generate_shell_html()`:
  - Construct 2-tier `<details name="tier1">` and `<details name="workspace">` HTML markup.
  - Group view links under category headers: `STATUS`, `TOPOLOGIES`, `PROJECTIONS`, `TELEMETRY`.
  - Render breadcrumb navigation bar at the top of the main iframe container.
  - Render top-right global corner icon row (Settings, Help/FTUE, Theme switcher).
  - Remove dead legacy 5-tab markup and `journeys.html` reference.

### Task 4: Daemon & Server Route Binding
- In `synlynk/vizor_daemon.py` and `synlynk/viz.py`:
  - Ensure `/w/<slug>/overview.html` and default workspace route point to `overview.html` as the initial view.
  - Ensure `/w/<slug>/activity.html` and `/activity.html` route properly.
  - Update default shell iframe `src` to `overview.html` (instead of `gantt.html`).

### Task 5: Unit & Integration Testing
- Add tests in `tests/test_viz_nav_restructure.py` verifying:
  - `generate_overview_html` generates stat cards, goal progress, and shortcuts.
  - `generate_activity_stream_html` generates filter chips and activity cards.
  - `generate_shell_html` includes `<details name="tier1">`, category groupings, and breadcrumb bar.
  - Routing in `vizor_daemon` correctly serves `overview.html` and `activity.html`.

---

## 3. Verification Commands
- `pytest tests/test_viz_nav_restructure.py tests/test_viz.py tests/test_vizor_daemon.py`
- `synlynk viz --uninstall && synlynk viz --install`
- `curl -s http://localhost:8721/w/synlynk/overview.html | grep "Stat Cards"`
- `curl -s http://localhost:8721/w/synlynk/activity.html | grep "Activity Stream"`
