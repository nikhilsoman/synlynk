# BS-21: Vizor — Browser Workspace Dashboard
## Design Spec

**Date:** 2026-07-03  
**Session:** BS-21 (Nikhil + Claude)  
**Status:** Drafted — brainstorm visuals locked, pending implementation plan  
**Target:** v0.11.x — primary D1–D2 retention surface  
**Brainstorm visuals:** `docs/brainstorm/bs21-vizor/`

---

## Problem Statement

After `synlynk launch` runs a job, the user returns to a blank terminal. There is no surface that answers:

> What is the state of everything I'm building, right now, without running a command?

Developers who live in a browser tab alongside their terminal need a persistent visual snapshot — the kind of ambient awareness that a kanban board or CI dashboard gives, but scoped to a single local workspace and generated from local data. Without this, synlynk is a tool you invoke, not a workspace you inhabit.

The Vizor is that browser tab. It answers the question above and anchors the D1–D7 retention habit.

---

## Goals

1. Give the developer a persistent browser surface that shows the full state of their workspace — dreams, stage progress, costs, agent activity — without requiring a command.
2. Make it local-first: generated from `state.db`, served locally, no cloud required, works offline.
3. Be snappy: all data is already on disk. Generation is a read + render, not a network call.
4. Surface the note system as a write path back into the next generation run — not just a read dashboard.
5. Be the canonical D1–D2 retention hook: the tab developers open first when they sit down.

---

## Non-Goals

- No real-time job control (no pause/resume/dispatch from the browser)
- No public hosting or cloud sync of Vizor output
- No multi-workspace cross-machine view (single local workspace only in v1)
- No data persistence beyond what is already in `state.db` / `project-docs/`
- No replacement for `synlynk jobs` or `synlynk launch` — Vizor is read + annotate only

---

## Architecture

### Generation Pipeline

```
synlynk viz
    │
    ├── reads: state.db (roadmap, tasks, costs, agents, telemetry)
    ├── reads: .synlynk/config.json (workspace name, pilots, limits)
    ├── reads: .synlynk/viz-notes.json (sticky notes from previous sessions)
    │
    ├── generates: .synlynk/viz-cache/
    │       ├── index.html        (shell + left nav + tab router)
    │       ├── gantt.html        (Gantt view)
    │       ├── journeys.html     (User Journeys view)
    │       ├── tube.html         (Architect Map view)
    │       ├── effort.html       (Effort & Cost view)
    │       └── efficiency.html   (Efficiency / agent report card)
    │
    └── serves: python3 -m http.server <port> from viz-cache/
               opens browser automatically
```

All five views are generated in a single pass. Total generation time target: under 2 seconds for a workspace with 10 Dreams and 100 tasks.

### Local Server

A lightweight `python3 -m http.server` serves `viz-cache/` on a stable port (default: `synlynk viz --port 8721`). The port is written to `.synlynk/viz-meta.json` so the browser notification service can reference it.

The server is started in the background by `synlynk viz --serve`. Subsequent calls to `synlynk viz` regenerate the cache and send a browser notification; the open tab auto-reloads via a polling check on `viz-cache/manifest.json` (last-updated timestamp).

### Offline Capability

All HTML views are self-contained: inlined CSS, inlined JS, no external CDN dependencies. The tab continues to work after `synlynk viz --serve` is stopped; it just won't refresh until the next `synlynk viz` run.

### Data Read Path

The generator reads exclusively from `state.db` and `.synlynk/`. It does not parse `project-docs/` markdown files directly — those are already migrated into `state.db` by `synlynk migrate`. This keeps generation deterministic and fast.

### Note Write Path

When a user saves a note via the Vizor UI, the note is written immediately to `.synlynk/viz-notes.json` via a `POST /note` endpoint on the local server (not via the filesystem directly, to avoid CORS issues). On the next `synlynk viz` run, notes are read and injected into the generator's context as `<!-- note: ... -->` annotations in the generated HTML, and also surfaced to pilot agents via `.synlynk/context.md`.

---

## Views

### Shell (shared across all views)

A consistent shell wraps all five views:

**Left nav:**
- Workspace tree: workspace → repos (expandable, collapsible)
- View navigation: five named views with icons
- Theme switcher: Light / Dark / System (persisted to `localStorage`)
- User avatar + workspace name at footer

**View tabs:** top-level horizontal tab strip, one per view

**Status bar:** `● local · offline-ready` · workspace name · `updated N min ago`

---

### View 1: Gantt

**Purpose:** Timeline overview of all Dreams in the workspace, their SDLC stages, and task-level drill-down.

**Design (locked — see `docs/brainstorm/bs21-vizor/viz-gantt-v5.html`):**

- 10-column timeline grid (configurable: 4w / 10w / 26w)
- One row per Dream. Row shows: expand arrow, Dream name, agent stack, cost vs. estimate
- Stage bars positioned on the timeline using `stageStart` + `stageWidth` as fractions of the visible window. Stage colors: Dream=purple, Plan=blue, Work=green, Ship=orange, Maintain=indigo, Engage=pink
- In-progress stage bars animate (shimmer gradient) to signal activity
- Agent avatar badges (`C` Claude / `A` Agy / `Co` Codex / `G` Grok) on in-progress stage bars

**Drill-down (stage zoom):**
- Clicking a stage bar opens a drill section below that Dream row
- The drill section shows a zoomed timeline scoped to that stage's date window only — the N weeks of the stage expand to fill the full timeline width
- Task sub-rows in the drill show: agent avatar (left), task name right-aligned in label column, task bar positioned within the stage's zoomed window, agent avatar + actual cost on the right end of the task bar
- Smooth `max-height` expand/collapse animation (350ms)
- Clicking the same stage bar again, or clicking ✕, collapses the drill

**Note icon (SVG pencil):**
- Appears on hover on every row, stage bar, task bar, and summary card
- Color states: gray = no note, blue = informational, yellow = action tag (↺ redo / ⇄ reassign / ⏸ defer), red = urgent / blocked, green = resolved
- Clicking opens a modal: text input + action tag toggles + Save / Cancel
- Saved notes persist to `.synlynk/viz-notes.json` and appear as colored chips on the card

**Summary cards (below the Gantt):**
- Dreams in flight · Active agents · Total spend · Next ship date

---

### View 2: User Journeys

**Purpose:** For product/UX repos — show user flows and screen-by-screen journeys.

**Design:** Split-pane layout.
- Left: scrollable list of named journeys (e.g. "New patient onboarding", "Rx refill flow")
- Right: selected journey rendered as a screen flow — cards connected by arrows showing the sequence of screens/steps
- Each screen card shows: screen name, route/URL, description, agent responsible for implementation, SDLC stage badge
- Journeys are defined in `state.db` (journey_entries table, or parsed from a `docs/journeys/*.md` convention)

**FTUE setting:** On first open, the user is asked whether their project has user-facing UX. If yes, User Journeys is the default second tab. If no (backend, data pipeline, CLI tool), the Architect Map is shown instead. This preference is stored in `.synlynk/config.json` as `vizor_default_view: "journeys" | "tube"`.

---

### View 3: Architect Map

**Purpose:** Birds-eye structural view of the codebase/system — how components connect.

**Design (baseline — see `docs/brainstorm/bs21-vizor/viz-tube.html`):**

- London Underground tube map metaphor: colored lines = subsystem flows, stations = components/modules, interchanges = shared components touched by multiple flows
- All line routing at 0° / 45° / 90° only — no freehand curves
- Station size scales with connection count: terminal (1 segment) → smallest; major interchange (4+ segments) → largest. Formula: `r = base + segs × factor`
- The database / central state store is always the largest station, positioned where lines naturally converge
- Active stations (currently being worked on) show a glow filter and a slow pulse animation
- Agent avatar badges on stations currently assigned to an agent
- Hover tooltip on each station: name, which lines it belongs to, brief description
- Lines are auto-generated from `state.db` structural metadata OR defined manually in `.synlynk/vizor-tube.json`

**Line definition (v1: manual):** Users define lines in `.synlynk/vizor-tube.json`:
```json
{
  "lines": [
    {"id": "request", "name": "Request Line", "color": "#0d9e87", "stations": ["browser", "cloudfront", "nextjs", "api", "postgres"]},
    ...
  ],
  "stations": {
    "postgres": {"label": "PostgreSQL (RDS)", "desc": "Central data store.", "x": 600, "y": 280}
  }
}
```
Auto-generation from codebase imports is a v2 feature.

**FTUE:** If no `vizor-tube.json` exists, the Architect Map shows a placeholder prompt: "Define your architecture lines to unlock this view. Run `synlynk viz --setup-tube` to start."

---

### View 4: Effort & Cost

**Purpose:** Where is time and money going? Breakdown by Dream, agent, SDLC stage.

**Design:**
- Top: summary row — total spend, on-track Dreams, over-budget Dreams, total agent-hours
- Three panels:
  1. **By Dream** — horizontal bar chart: each Dream a bar, split into stage segments, color-coded by stage. Cost label on right end. Over-budget Drams shown in red.
  2. **By Agent** — donut or horizontal bars: spend and task count per agent (Claude / Agy / Codex / Grok)
  3. **By Stage** — breakdown of spend across SDLC stages across all Dreams (which stage is consuming the most budget?)
- All figures read from `cost_entries` table in `state.db`
- Actual vs. estimated comparison wherever estimates exist

---

### View 5: Efficiency / Agent Report Card

**Purpose:** How well is each agent performing? Catch loops, cost spikes, and quality signals.

**Design:**
- One card per agent with: avatar badge, name, tasks completed, tasks active, total spend, avg cost/task, success rate (exit code 0 / total runs), sentinel alerts triggered
- Traffic-light color coding: green = healthy, yellow = watch, red = flagged
- Bottom: Sentinel timeline — a compact timeline of all `sentinel.md` events (FLATLINE, SUCCESS_LOOP, COST_SPIKE, QUOTA_EXHAUSTED) across all agents, with timestamps and resolved/open status
- Reads from `telemetry.json` (per-run records) and `sentinel.md` (alert log)

---

## Note System

Notes are bidirectional: they annotate the current state AND inject intent into the next generation run.

**UI:**
- SVG pencil icon appears on hover on every card, row, stage bar, and station
- Click → modal with: `<textarea>` for note text + action tag toggles

**Action tags:**
- `↺ Redo stage` — marks this stage for re-execution on next pilot run
- `⇄ Reassign agent` — flags that the assigned agent should be swapped (user can specify in text)
- `⏸ Defer` — moves this task/stage out of the current sprint window

**Storage:** `.synlynk/viz-notes.json` — keyed by element ID (Dream ID, stage key, task ID, station ID)

**Injection:** On next `synlynk viz` run, notes are:
1. Rendered as colored chips on the relevant card (visual persistence)
2. Written to `.synlynk/context.md` under a `## Vizor notes` section (visible to pilot agents)
3. If action tags are set, a `## Pending actions from Vizor` section is appended to `context.md` with structured action items

**Note color states:**
- No note: gray pencil, hidden until hover
- Informational (text only, no tag): blue
- Action tag set: yellow
- Urgent / cost overrun / blocked: red
- Resolved: green

---

## Browser Notifications

Uses the Web Notifications API. On first load, the Vizor requests notification permission.

Notification triggers:
- `synlynk viz` run completes (new cache generated)
- Sentinel alert written to `sentinel.md`
- Job cost exceeds threshold (configurable in `.synlynk/config.json` as `vizor_notify_cost_usd`)
- Scheduled refresh complete (if pilot-driven schedule is configured)

The notification payload includes: workspace name, what changed, link to open the relevant view. Clicking the notification brings the Vizor tab to focus and navigates to the relevant view.

---

## Settings & Configuration

Stored in `.synlynk/config.json` under a `vizor` key:

```json
{
  "vizor": {
    "port": 8721,
    "default_view": "gantt",
    "second_view": "journeys",
    "refresh_interval_minutes": 15,
    "notify_on_refresh": true,
    "notify_cost_threshold_usd": 5.0,
    "theme": "system",
    "timeline_weeks": 10
  }
}
```

**Pilot-driven scheduled generation:** If `refresh_interval_minutes` is set, a pilot agent can trigger `synlynk viz` on schedule (via cron or the synlynk daemon). The Vizor tab polls `viz-cache/manifest.json` every 60s and auto-reloads when the `updated_at` timestamp changes.

---

## Command Interface

```bash
# Generate all views and open browser
synlynk viz

# Generate + start local server (background, stable port)
synlynk viz --serve

# Generate only (no server, no browser open)
synlynk viz --generate

# Open existing cache in browser without regenerating
synlynk viz --open

# Set up architecture lines interactively (creates vizor-tube.json)
synlynk viz --setup-tube

# Specify port
synlynk viz --serve --port 9000

# Stop the background server
synlynk viz --stop
```

---

## FTUE (First Use Experience)

On first `synlynk viz` run in a workspace:

1. **Prompt 1:** "Does this project have user-facing UX? (y/n)" → sets `vizor.second_view`
2. **Prompt 2:** "Enable browser notifications? (y/n)" → sets `vizor.notify_on_refresh`
3. **Prompt 3:** "Auto-refresh every N minutes? (15 / 30 / off)" → sets `vizor.refresh_interval_minutes`

These prompts only run once. Settings can be changed in `.synlynk/config.json` or via `synlynk viz --setup`.

---

## File Structure

```
.synlynk/
├── viz-cache/
│   ├── manifest.json       # {"updated_at": "ISO timestamp", "version": "..."}
│   ├── index.html          # shell, left nav, tab router
│   ├── gantt.html
│   ├── journeys.html
│   ├── tube.html
│   ├── effort.html
│   └── efficiency.html
├── viz-notes.json          # note content keyed by element ID
├── viz-meta.json           # {"port": 8721, "pid": 12345, "serving": true}
└── vizor-tube.json         # optional: manual architecture line definitions
```

---

## Theme System

All views share a single CSS token set:

```css
:root {
  --bg, --bg2, --bg3       /* surface levels */
  --text, --text2, --text3  /* text hierarchy */
  --border, --border2
  --accent, --accent-bg, --accent-dim
  /* SDLC stage colors */
  --s-dream-bg/bd/tx, --s-plan-*, --s-work-*, --s-ship-*, --s-maint-*, --s-engage-*
  /* Agent avatar colors */
  --ag-claude-*, --ag-agy-*, --ag-codex-*, --ag-grok-*
}
[data-theme="dark"] { /* all tokens overridden */ }
```

Theme is set via `document.documentElement.setAttribute('data-theme', resolved)`. Stored in `localStorage` as `vizor-theme`. System default resolves via `prefers-color-scheme` media query.

---

## Agent Assignment

Implementation is delegated per view:

| View | Agent | Rationale |
|------|-------|-----------|
| Shell + left nav | Agy | HTML/CSS layout |
| Gantt view | Agy | Gantt v5 design locked, Agy implements |
| User Journeys | Agy | Screen flow rendering, split-pane layout |
| Architect Map | Agy | SVG tube map, hand-crafted style (v1 baseline) |
| Effort & Cost | Codex | Data aggregation + chart rendering |
| Efficiency report | Codex | Telemetry aggregation, sentinel parsing |
| Note system backend | Codex | POST /note endpoint, viz-notes.json write path |
| `synlynk viz` command | Codex | CLI plumbing, generation pipeline, server management |

Claude: code review, dispatch prompts, architecture decisions, this spec.

---

## Open Questions

1. **Auto-generation from codebase:** Can the Architect Map auto-detect lines from import graphs / dependency trees in v1, or is manual `vizor-tube.json` enough?  
   → Decision: manual only in v1. Auto-detect is v2.

2. **Journey source of truth:** Do User Journeys read from a `docs/journeys/` convention or from a `journey_entries` table added to `state.db`?  
   → Decision: `docs/journeys/*.md` convention in v1 (simpler, no migration required). Table migration is v2.

3. **Multi-repo workspace:** Does `synlynk viz` generate one combined Vizor for all repos in a workspace, or one Vizor per repo?  
   → Decision: one combined Vizor per workspace in v1. Workspace tree in left nav shows per-repo breakdown.

4. **Note persistence across regenerations:** When `synlynk viz` regenerates the cache, do notes survive?  
   → Decision: yes. `viz-notes.json` is read-only by the generator (it reads and injects, never overwrites notes). Notes are cleared only when user explicitly marks them resolved and clicks "Archive resolved notes."

5. **Tab auto-reload mechanism:** Server-sent events vs. polling?  
   → Decision: polling `manifest.json` every 60s (simpler, no SSE server required for the Python http.server).

---

## Success Criteria

- Developer opens the Vizor tab first when sitting down to work — without being prompted
- A returning user on D2 can answer "what did I do yesterday and what's next" in under 10 seconds
- Generation completes under 2s for a 10-Dream, 100-task workspace
- Notes saved in the browser appear in `.synlynk/context.md` on the next `synlynk viz` run
- No cloud dependency: Vizor works fully offline after first generation
