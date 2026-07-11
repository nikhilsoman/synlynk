---
title: Vizor Architect Map v2 — Live Workspace Topology View
date: 2026-07-11
status: approved-pending-user-review
---

# Vizor Architect Map v2 — Live Workspace Topology View

## 1. Problem Recap: What's Wrong With the Current Architect Map

`generate_tube_html()` (`synlynk/viz.py:1391-1927`) renders Vizor's "Architect Map" tab as a
hand-drawn London Underground–style tube map. It has three structural problems:

1. **No live data source.** Station positions, line groupings, and colors all come from
   `.synlynk/vizor-tube.json` (`VIZ_TUBE_PATH`, `synlynk/viz.py:22`), a file that is 100%
   manually authored. Nothing in the codebase generates or updates it. If a repo is added,
   removed, or its relationships change, the map silently goes stale — there's no mechanism
   that would even tell you it's stale.
2. **Dead-end onboarding.** The empty-state UI (`synlynk/viz.py:1539-1578`) tells first-time
   users to run `synlynk viz --setup-tube` to create the file interactively. That command does
   not exist anywhere in `bin/synlynk.py` or `synlynk/__init__.py`. Every user who hits the
   empty state is stuck.
3. **Wrong scope for the metaphor.** The original design spec
   (`docs/superpowers/specs/2026-07-03-bs21-vizor-design.md:151-180`) is ambiguous about
   whether the map represents *code-level* architecture (imports, modules within one repo) or
   *workspace-level* topology (which repos exist and how they relate). The tube-map metaphor
   (stations = modules, lines = subsystems) reads as code-level, but synlynk's actual unit of
   work is the **workspace** — one or more repos tracked together via `cfg["repos"]`. This
   brainstorm confirmed the correct scope is workspace-level: **the map should answer "what
   repos make up this workspace, and how do they relate," not "what does the import graph of
   this one repo look like."**

## 2. Goal

Replace the static tube map with a view that:

- Is generated from data synlynk already tracks — no new manual-authoring step for the common
  case.
- Accurately reflects the current workspace: which repos exist (from `cfg["repos"]`), plus
  their declared relationships.
- Is interactively navigable: click a repo to see detail and take action, not just hover a
  tooltip.
- Supports high-level actions from the map itself (dispatch, jump to a repo's Gantt view, etc.)
  rather than being read-only.
- Stays within Vizor's existing constraints: self-contained HTML/CSS/JS per
  `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md` ("no external CDN dependencies"),
  and a sub-2-second generation time.
- Leaves room to add further visualization styles later without a rewrite.

## 3. Data Model

### 3.1 Nodes — repos

Nodes come from the existing, already-populated `cfg["repos"]` array in
`.synlynk/config.json` (schema: `{"path": abs_path, "name": basename, "stack_labels": [...]}`,
populated by the init wizard's `_wiz_screen_workspace_name_pick()` and maintained via
`synlynk scan --add/--remove`, `synlynk/__init__.py:~930-991`). No new data-collection step is
needed to enumerate nodes.

For each repo, the generator additionally derives:
- **GitHub URL** — from `git remote get-url origin` in that repo's path, parsed into an
  `https://github.com/<org>/<repo>` link (used for the drawer's "Open on GitHub" action).
- **Active dreams/agents count** — same source the Gantt view already reads for its per-repo
  summary, so the map and Gantt tab never disagree.

If `cfg["repos"]` is empty or absent (single-repo workspace, as in synlynk's own dogfood
config today), the map falls back to a single node representing the current repo — this
matches today's single-workspace usage and requires no special-casing in the renderer beyond
treating a 1-node graph as a valid (if visually trivial) case.

### 3.2 Edges — relationships between repos

Edges are stored in a new file, `.synlynk/vizor-workspace-map.json`, replacing
`vizor-tube.json`:

```json
{
  "edges": [
    {"from": "synlynk-website", "to": "synlynk-core", "type": "api-call"},
    {"from": "synlynk-core", "to": "tokq-bridge", "type": "shared-db"}
  ],
  "edge_types": {
    "api-call": {"label": "API Call", "color": "#0d9e87"},
    "shared-db": {"label": "Shared Data", "color": "#3b82f6"}
  }
}
```

Edges are **typed and color-coded** — every edge must reference a key in `edge_types`, and the
renderer colors each edge line by that type's `color`. This makes the graph legible at a glance
once a workspace has more than a couple of relationships (a legend lists each type once).

**Freshness mechanism — PR-driven, not manual audit.** Rather than either (a) a one-off
hand-authored file that immediately goes stale like today's `vizor-tube.json`, or (b) a full
static-analysis engine that infers relationships automatically (out of scope — no reliable
signal for "shared-db" or similar relationship types without per-project convention), edges are
maintained as a **new step in PR discipline**, parallel to the existing Blog Post Protocol:

> **Workspace Map Update** — For any PR that changes how one tracked repo relates to another
> (new API call between repos, new shared dependency, a relationship removed), update
> `.synlynk/vizor-workspace-map.json` in the same branch as that PR. Most PRs touch only one
> repo and don't need this step — it only applies when the PR's own description says it adds,
> removes, or changes a cross-repo relationship.

This is added to `CLAUDE.md` as a conditional protocol (like Blog Post Protocol, but
conditional rather than mandatory-every-PR), not built as CLI tooling — there's no reliable way
to detect "this PR changed a cross-repo relationship" mechanically, so it's a discipline note
for whoever (human or dispatched agent) writes the PR, not a generator step.

## 4. Layout — Force-Directed Node Graph

Of three layout styles compared during the visual brainstorm (auto-laid-out tube map, grid/
service catalog, force-directed node graph), **force-directed node graph** was selected: boxes
= repos, colored lines = typed edges, positions computed by a layout algorithm rather than
hand-placed coordinates. This is the standard shape for tools in this space (Backstage, Grafana
service maps), scales cleanly from a handful of repos to a few dozen, and avoids the tube map's
two-part engineering cost (auto-layout *and* 45°/90° line-routing rules).

**Implementation constraint:** no D3.js or other CDN dependency, per Vizor's self-contained-HTML
requirement. The layout is a hand-rolled deterministic spring-embedder (~60 lines of vanilla
JS):
- Nodes start at fixed positions on a circle (deterministic — same input always produces the
  same layout, no jitter between page loads).
- A fixed number of iterations (e.g. 200) applies pairwise node repulsion + edge-based
  attraction, then clamps to the canvas bounds.
- At realistic repo counts (single digits to low dozens), this converges to a readable layout
  well within the sub-2-second generation budget — the layout runs client-side in the browser
  on load, not during Python HTML generation, so it doesn't count against synlynk's own
  generation-time budget at all.

## 5. Interaction — Side Drawer

Clicking a node opens a **side drawer** (graph stays fully visible; a panel slides in from the
right), reusing the interaction idiom Vizor's Gantt view already has for its note-editing
drawer. This was chosen over inline-expand (fights for space once there are many repos) and a
modal overlay (loses spatial context — you can't compare two repos side by side while a modal
is open).

The drawer shows repo detail and four actions, all confirmed in scope:
1. **Dispatch to this repo** — opens the existing dispatch flow pre-scoped to the selected
   repo.
2. **Jump to this repo's Gantt view** — navigates to the Gantt tab filtered/scrolled to that
   repo.
3. **Show active dreams/agents at a glance** — inline summary in the drawer itself (dream
   count, agent count, last-commit time), no navigation required for a quick check.
4. **Open repo on GitHub** — external link using the derived GitHub URL from §3.1.

## 6. Sub-Views: Graph and File Tree, Extensible

Architect Map becomes a small view-switcher rather than one fixed visualization, in response to
the need for a more traditional, file-hierarchy-oriented view alongside the graph:

- **Workspace Graph** (default) — the force-directed node graph from §3-§5.
- **File Tree** — an IDE-style collapsible directory tree, one root per repo in
  `cfg["repos"]`. Sourced from `synlynk scan --deep`'s existing output
  (`_scan_full_repo()`, `synlynk/__init__.py:6260`), which already walks each repo's full
  source tree and writes file/symbol data to `state.db` and `project-docs/source-map.md`
  (`synlynk/__init__.py:6305-6306`). The tree view reads this existing data rather than doing
  its own filesystem walk at Vizor-generation time, keeping to Vizor's established principle
  of generating exclusively from `state.db` / `.synlynk/` rather than parsing project files
  directly. A repo that hasn't been deep-scanned yet shows a "run `synlynk scan --deep`" prompt
  in place of its tree, rather than an empty or broken tree.
- **Switcher** — a small tab/toggle local to the Architect Map tab itself (nested under
  Vizor's existing top-level Gantt / Journeys / Architect Map / Effort / Efficiency tab bar),
  not a new top-level tab.
- **Pinning** — the user's preferred sub-view persists to `.synlynk/config.json` under a new
  `vizor.architect_map_view` key (`"graph" | "tree"`), mirroring the existing
  `vizor.second_view` key already present in that config block (`synlynk/viz.py` config
  schema, `.synlynk/config.json`'s `vizor` object).
- **Extensibility** — sub-views are registered in a small internal id → render-function map
  inside `generate_tube_html()` (or its renamed successor), so a future third view (e.g. an
  infra/deployment topology view) can be added without restructuring the switcher or touching
  the graph/tree implementations.

## 7. Migration Notes

- `VIZ_TUBE_PATH` (`.synlynk/vizor-tube.json`) is replaced by `.synlynk/vizor-workspace-map.json`
  (§3.2). Existing `vizor-tube.json` files are not auto-migrated — the schemas are different
  enough (station x/y coordinates vs. typed edge list) that a straight conversion isn't
  meaningful; workspaces using the old manual file simply start from an empty edge list under
  the new one.
- The `synlynk viz --setup-tube` reference in the current empty-state UI and in
  `docs/superpowers/specs/2026-07-03-bs21-vizor-design.md` is removed. The new empty state (no
  `cfg["repos"]` and no edges) explains that the graph will show a single node for the current
  repo and that edges are optional/added via the Workspace Map Update protocol (§3.2) as
  relationships are introduced.
- `generate_tube_html()` is renamed to reflect the new scope — implementation plan will decide
  the exact function name (e.g. `generate_architect_map_html()`) and whether the view-switcher
  wraps both sub-view renderers or each sub-view is its own function called by a thin wrapper.

## 8. Out of Scope

- Automatic inference of edges from code (import analysis, API-call detection, etc.) — no
  reliable cross-language signal exists for this; deferred indefinitely, not just to a later
  phase.
- Code-level (intra-repo) architecture visualization (module/import graphs within a single
  repo) — this was the original tube-map's ambiguous secondary scope; explicitly out of scope
  for Architect Map, which is workspace-level only.
- Real-time/live-updating graph while Vizor is open (e.g. via websocket) — Vizor's existing
  refresh model (regenerate HTML on interval or on demand, per `vizor.refresh_interval_minutes`)
  is unchanged; the graph is only as fresh as the last generation.
