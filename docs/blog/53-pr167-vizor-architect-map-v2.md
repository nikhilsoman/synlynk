# Architect Map v2 — From Static Tube Map to Live Workspace Graph

**Date:** 2026-07-12
**PR:** TBD
**Branch:** `chore/vizor-architect-map-v2-design` → `main`

---

## The Goal at the End of the Previous PR

BS-21 shipped Vizor as a local browser dashboard with five tabs, one of which — Architect Map —
rendered a hand-drawn, London Underground–style "tube map" of the workspace. It looked good in a
screenshot, but it had three structural problems that surfaced almost immediately in dogfooding:

1. **No live data source.** Every station position, line grouping, and color came from
   `.synlynk/vizor-tube.json`, a file nothing in the codebase ever generated or updated. Add a
   repo, remove a repo, change a relationship — the map silently went stale with no signal that
   it had.
2. **Dead-end onboarding.** The empty state told first-time users to run `synlynk viz --setup-tube`
   to create the file interactively. That command didn't exist anywhere in the codebase. Every
   user who hit the empty state was stuck with no path forward.
3. **Wrong scope for the metaphor.** The tube-map visual language (stations = modules, lines =
   subsystems) reads as code-level architecture, but synlynk's actual unit of work is the
   *workspace* — one or more repos tracked together via `cfg["repos"]`. The map needed to answer
   "what repos make up this workspace and how do they relate," not "what does the import graph
   of one repo look like."

A revisit-and-redesign brainstorm (issue-tracked as #10) confirmed the fix wasn't a patch to the
tube map — it was a full swap to a different visualization metaphor built on data synlynk
already tracks.

---

## What Moved the Goalpost in This PR

The brainstorm compared three layout styles: an auto-laid-out tube map, a grid/service catalog,
and a force-directed node graph. Force-directed won — it's the standard shape for this problem
space (Backstage, Grafana service maps), it scales from a handful of repos to a few dozen without
redesign, and it avoids the tube map's two-part engineering cost (auto-layout *and* 45°/90°
line-routing rules). No visual companion session was used for this round — the three options were
differentiated well enough in text/diagram form during brainstorming.

One scope narrowing happened mid-plan, caught during the plan's own self-review rather than left
as a silent gap: the design spec's side-drawer action #3 ("show active dreams/agents at a glance")
originally implied dream count, agent count, *and* last-commit time, sourced from "the same place
the Gantt view already reads." But nothing in the codebase attributes a story to a specific repo —
`stories` has no `repo_path` column, and adding one wasn't part of this plan's approved scope. The
plan was updated in place (Task 8) to ship the smaller, honest version: real active-dream count
for single-repo workspaces (today's dogfood case), `0` for every repo once a workspace has 2+ repos
(no attribution signal exists yet to split credit). Agent count and last-commit time are deferred,
not silently dropped — they need the same `repo_path` plumbing this task deliberately didn't add.

---

## What Shipped

Eight tasks, executed via Subagent-Driven Development (fresh Codex dispatch per task, two-stage
review — spec compliance then code quality — before each merge), landing eight commits on
`chore/vizor-architect-map-v2-design`:

### Data model (Task 1–2)

- `_load_workspace_repos(config)` / `_repo_github_url(repo_path)` — nodes come straight from the
  existing `cfg["repos"]` array; GitHub URLs are derived from each repo's `git remote get-url
  origin`, not stored anywhere new.
- `.synlynk/vizor-workspace-map.json` replaces `vizor-tube.json` — typed, color-coded edges
  (`{"from", "to", "type"}` + an `edge_types` legend), loaded via `_load_workspace_map()`.
  Freshness isn't automated (no reliable cross-language signal exists to infer "this PR added an
  API call between repos") — it's a new conditional line in `CLAUDE.md`'s protocol list instead:
  update the edges file when a PR's own description says it changed a cross-repo relationship.
- `_query_repo_file_tree()` — a new `synlynk/__init__.py` DB helper reading the file/symbol data
  `synlynk scan --deep` already writes to `state.db`, reused rather than re-walking the filesystem
  at Vizor-generation time.

### Rendering + routes (Task 3–4)

- New POST routes: `/dispatch` (repo-scoped dispatch trigger) and `/architect-map/view-pref`
  (persists the graph/tree sub-view choice to `.synlynk/config.json`'s `vizor.architect_map_view`
  key).
- `generate_tube_html()` renamed to `generate_architect_map_html(data, port)` and rewritten end to
  end — 611 lines of hand-crafted SVG tube-rendering logic deleted, replaced by a 160-line HTML
  shell: graph/tree switcher tabs, legend, empty SVG canvas, side-drawer markup.

### Interaction (Task 5)

- A hand-rolled force-directed layout in ~60 lines of vanilla JS (`layoutGraph`) — no D3, no CDN
  dependency, matching Vizor's self-contained-HTML constraint. Nodes start on a circle at
  deterministic positions; 200 iterations of pairwise repulsion (inverse-square, strength 4000)
  plus edge-based attraction (distance × 0.01) converge to a stable layout, clamped to a 900×620
  canvas. The simulation runs client-side on page load, so it costs nothing against Vizor's own
  sub-2-second generation budget.
- Clicking a node opens a side drawer (reusing the Gantt view's existing slide-in idiom) with four
  actions: dispatch to that repo, jump to its Gantt view (via `postMessage` cross-frame nav), open
  on GitHub, and — as of Task 8 — an active-dream count.

### File tree sub-view (Task 6)

- `renderTree()`/`renderTreeNode()` render an IDE-style collapsible directory tree per repo,
  sourced entirely from `_query_repo_file_tree()` — no filesystem walk at render time. A repo with
  no deep scan yet shows a "run `synlynk scan --deep`" prompt instead of an empty tree.

### Cleanup (Task 7)

- The dead `--setup-tube` references were removed from the original BS-21 design spec, replaced
  with a pointer to this design doc. The `Workspace Map Update Protocol` — the conditional,
  PR-triggered edge-file update rule described above — was added to `CLAUDE.md` immediately after
  the Blog Post Protocol section, following the same "conditional, not mandatory-every-PR" pattern.

### Drawer dream count (Task 8)

- Wired the scoped-down active-dream count described above into both `_base_data()`'s
  `workspace.repos` list and the drawer's rendered HTML.

One subagent execution hiccup worth noting for the record: Task 5's implementer job hit a
transient `git commit` lock error mid-run (never reproduced afterward — most likely a race with
another worktree's cleanup happening at the same wall-clock moment) and left its work uncommitted.
A nested fix job, dispatched from inside the stalled job's own worktree, both resolved the commit
and fixed a genuine logic bug caught in manual code-quality review: an inverted `!window.
_treeRendered` condition that would have made `renderTree()` permanently unreachable from the tab
switcher. Both issues were folded into one final commit rather than left as a base-plus-patch pair.

All 940 tests pass (up from 934 pre-PR). Zero remaining references to `generate_tube_html`,
`tube_config`, or `--setup-tube` anywhere in `synlynk/` or `tests/`.

---

## Progress Toward the Long-Arc Goal

The long-arc goal is full autonomous multi-agent dispatch — Claude as PM/reviewer, implementation
entirely delegated. This PR is a clean instance of that model working end to end at real scope:
eight tasks, eight fresh Codex dispatches, two-stage review on each, one nested fix-job precedent
reused a second time without needing new process. Vizor itself — the dashboard this PR improves —
is the operator's window into that same fleet, so making its workspace-topology view actually
trustworthy is not a side quest; it's sharpening the tool used to supervise the thing this whole
project is building toward.

---

## New Goalpost

Architect Map now tells the truth about the workspace as `.synlynk/` and `state.db` already know
it, with a conditional discipline (Workspace Map Update Protocol) keeping the edge data from going
stale the way `vizor-tube.json` silently did. The next open thread on this surface is the deferred
`repo_path` attribution work — a `stories`/`repo_path` column (or equivalent) that would let the
drawer's dream count (and eventually agent count, last-commit time) work correctly for multi-repo
workspaces instead of falling back to zero. That's explicitly out of scope here and not yet
ticketed; it's the natural next brainstorm once a real multi-repo dogfood workspace exists to
validate against.
