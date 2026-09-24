# Vizor Navigation & Information Architecture Restructure

**Status:** Approved
**Date:** 2026-09-22
**Scope:** Sub-project 1 of the broader Vizor UX/IA overhaul (see "Related work" below). Covers items 1-5 of the originating review: workspace-first navigation, per-workspace overview canvas, accordion-style nav, category-grouped views, and breadcrumb navigation.

## Background

A review of Synlynk Vizor (`localhost:8721`) surfaced a broad set of usability and information-architecture issues. The originating request decomposed this into independently spec-able sub-projects, all to be tracked under one long-lived GOVERNS goal that stays open across multiple rounds of work:

1. **Navigation/IA restructure** (this spec) — workspace-first ordering, overview canvas, accordion nav, categorized views, breadcrumbs
2. Settings section (GitHub OAuth, harness OAuth, provider connections, backup/restore)
3. Gantt data-integrity/GOVERNS-terminology fixes, GitHub issue link-outs
4. FTUE onboarding guided walkthrough
5. Server persistence / full interactivity across currently-blank views

This spec covers only (1). The remaining sub-projects get their own brainstorm → spec → plan → build cycles.

Vizor today (`synlynk/viz.py`, 6,166 lines + `synlynk/viz_views.py`, 487 lines) is pure server-rendered Python/HTML — no JS framework, no build step. Every view is a full-page reload, cached to `.synlynk/viz-cache/*.html`. The current nav has Views as the first column and Workspaces as the second — backwards from how users actually navigate (pick a workspace first, then a view within it).

## Goals

- Workspaces become the primary, first-order navigation axis.
- Support the eventual Personal/Team/Enterprise account-scope tiers without building Team/Enterprise functionality now.
- Selecting a workspace immediately shows a useful overview (stats, goals, jobs, shortcuts) rather than an empty canvas.
- Views are grouped by type (Status/Topologies/Projections/Telemetry) instead of a flat list.
- Replace the current main-canvas menu bar with location-only breadcrumbs; global actions (settings, FTUE replay) move to a separate corner icon row.
- Add a cross-workspace Activity Stream as the root canvas for a tier, giving a "catch up on everything" surface.

## Non-goals

- Team/Enterprise functionality itself (workspaces, permissions, data model) — stubbed as "coming soon" only.
- The Settings page contents (sub-project 2).
- Gantt data/terminology fixes (sub-project 3).
- FTUE modal implementation (sub-project 4) — this spec only reserves a corner-icon slot for its trigger.
- Any JS-framework/SPA-shell rewrite of Vizor (evaluated and explicitly deferred — see "Approach" below).

## Approach

Vizor's existing architecture is pure server-rendered HTML with zero JS and no build step. Three implementation approaches were considered:

1. **Native HTML accordion, zero JS (chosen).** Use `<details name="...">` / `<summary>` with HTML5's native exclusive-accordion-group behavior (the `name` attribute ensures only one `<details>` in a group is open at a time, browser-native, no JavaScript). Clicking a workspace or view still triggers a normal full-page navigation, exactly as today.
2. **Vanilla JS accordion state.** Same visual result, hand-rolled JS state management. Rejected — only useful for animated transitions or non-default keyboard behavior, neither of which is required here.
3. **JS-driven shell with fetch-based view swapping.** A genuinely SPA-like persistent shell. Rejected for this spec as too large a scope increase (state management, history/URL sync, loading states); may be revisited as its own future sub-project if full-page-reload navigation becomes a real complaint.

Approach 1 was selected: it solves the stated requirements with minimal new surface area and fits the codebase's existing zero-build character.

## Design

### 1. Navigation structure & interaction model

Single left-nav column (~260-280px), replacing today's two-column Workspaces+Views split.

**Tier 1 — Account scope accordion:** `PERSONAL` / `TEAM` / `ENTERPRISE`, exclusive `<details name="tier1">` group (one open at a time).
- `PERSONAL` keeps the current green-tinted header styling (matches today's workspace rows).
- `TEAM` and `ENTERPRISE` get a distinct blue-tinted header to signal a different account scope. When expanded, each renders a static "coming soon" stub panel (icon + one-liner) instead of a workspace list — no dead links, no empty states pretending to be functional.

**Tier 2 — Workspace accordion**, nested inside the active `PERSONAL` tier: one `<details name="workspace">` per workspace, exclusive group (opening a new workspace auto-collapses the previous one). Each header shows the workspace name and an open-stories count badge (same figure as the "Open Stories" stat card on that workspace's Overview page).

**Tier 3 — Views, grouped by category**, rendered inline inside the expanded workspace `<details>` — always fully visible once the workspace is open, not a further collapsible level. Four fixed category headers:
- **STATUS** — Board, Gantt
- **TOPOLOGIES** — Architect Map, Infra View
- **PROJECTIONS** — Product, Logical, World
- **TELEMETRY** — Effort, Cost, Efficiency, Observatory

Category headers are static labels, not collapsible — this keeps real accordion interaction to two levels (tier, workspace), not three.

**Interaction model:** all accordion expand/collapse is native `<details>`/`<summary>`, instant client-side toggle, zero JS. Clicking a workspace header both opens that `<details>` and navigates to its Overview page (section 2) in the same click. Clicking a specific view link is a normal full-page navigation, same as today.

### 2. Workspace overview canvas

New page, `generate_overview_html()` in `synlynk/viz.py` (same pattern as `generate_board_html()`), rendered as the main-canvas content the instant a workspace is selected. This is the destination for the breadcrumb's `Personal / <workspace>` level.

Content, top to bottom, compact/single-screen:

1. **Alerts/sentinel banner** — thin strip, only rendered if `.synlynk/sentinel.md` has active alerts for this workspace; zero height when clean.
2. **Stat cards row** — Active Goals, Open Stories, Jobs Running, Burn (7d), sourced from `synlynk status --json`.
3. **Goal progress rollup** — compact list of active GOVERNS goals with mini progress bars, equivalent to `synlynk goal status`.
4. **Recent/active jobs feed** — last ~5-8 jobs (running + recently completed) with status and PR link where applicable, sourced from `synlynk jobs`.
5. **Jump-to-view shortcuts** — compact grid of the four category groups, so the overview doubles as a launcher even with the accordion collapsed.

Ordering rationale: alerts first (actionable/urgent), then "how are we doing" (stats), then "what's in motion" (goals → jobs), then "where do I go next" (shortcuts) last.

### 3. Breadcrumbs & corner icons

**Breadcrumb bar** replaces the current main-canvas menu bar entirely. Location-only, clickable at each navigable level:

`Personal › synlynk-core › Topologies › Architect Map`

- `Personal` — always present; not a link until Team/Enterprise are real destinations.
- Workspace (`synlynk-core`) — links to that workspace's Overview page.
- Category (`Topologies`) — plain text, not a link (categories are groupings, not routes).
- View (`Architect Map`) — current page, non-clickable (standard trailing-crumb convention).

On the Overview page itself, the breadcrumb is just `Personal › synlynk-core`. On the tier-root Activity Stream (section 4), it's just `Personal`.

**Corner icon row** — pinned top-right, separate from the breadcrumb trail, holding global non-location actions:
- Settings gear (contents are sub-project 2, out of scope here — this spec only reserves the slot)
- FTUE replay trigger (implementation is sub-project 4 — this spec only reserves the slot so the corner row doesn't need rework later)

No other corner-icon needs exist in current scope; none are speculatively added.

### 4. Activity Stream (tier-1 root canvas)

Shown when a tier (`PERSONAL` now; `TEAM`/`ENTERPRISE` later, once functional) is active but no workspace is selected — the "catch up on everything" surface across workspaces, and eventually across teams/enterprise. New page: `generate_activity_stream_html()`, same `generate_*_html()` → `_write_cache()` pattern as other views.

**Card content:** workspace tag, event type (goal/story/epic/PR/job), relative timestamp, one-line summary, link-out icons only (e.g. Gantt, GitHub/Job/Issue as applicable to the event type) — no comment/reaction affordance in v1 (explicitly deferred; would require new persistence for comments/threading, out of scope).

**Nesting:** a card with child events (e.g. an epic with story updates) shows those children indented one level directly beneath it, within the same card. No second level of nesting.

**v1 required features (all three, not deferred):**
- Per-workspace filter chips (all workspaces on by default)
- Per-type filter chips (goal/story/epic/PR/job, independently toggleable)
- Pagination / load-more (not infinite scroll, not an unpaginated fixed list)

**Data source:** aggregates across workspace `state.db` activity (goals/stories/epics), GitHub PR/issue events, and job telemetry — all data Vizor already reads elsewhere; no new external integration.

### 5. Data sourcing & implementation notes

- No new data sources: Overview stats (`synlynk status --json`), goal rollup, jobs feed (`synlynk jobs`), and Activity Stream all read existing `state.db` / telemetry / GitHub API surfaces already used elsewhere in `viz.py` / `viz_views.py`.
- New server-rendered pages: `generate_overview_html()` (per-workspace), `generate_activity_stream_html()` (per-tier). Both follow the existing generator → `_write_cache()` pattern.
- Dead code in the region this restructure touches gets cleaned up as part of the change rather than left to rot further: the vestigial 5-tab mockup (`viz.py:1745-1750`), the dead `journeys.html` cache entry (`viz.py:5028-5048`), and the dead gear icon markup (`viz.py:1734`) — since the new corner icon row replaces its intended function anyway.
- **Testing:** extend existing `viz.py` rendering tests to cover the two new page generators; manual verification via `synlynk viz` for accordion behavior (native `<details>`, nothing to unit-test there) and breadcrumb link correctness at each level.

## Related work

- Tracked under `goal-70317121` — a new long-lived GOVERNS goal covering the full Vizor UX/IA overhaul, created per the repo's Lifecycle checkpoint directive. The goal stays open across this and subsequent Vizor sub-projects (settings, Gantt fixes, FTUE, persistence).
- Existing narrower specs this restructure builds alongside, not replaces: `2026-07-11-vizor-architect-map-v2-design.md` (Architect Map graph internals), `2026-07-03-bs21-vizor-design.md` (original 5-view shell, now superseded in IA terms by this spec).
- Filed as its own tech-debt issue during this brainstorm, unrelated to this spec's scope but discovered while creating the goal: gh:#1742 — `identity_slug_from_config()` resolves the wrong product slug when invoked from a worktree with an explicit `repo_path`, which appears to have already caused several other spec-branch worktrees in this repo to silently fork into separate unregistered products instead of sharing the canonical `synlynk` state.db.
