# Vizor Gets a Goals Panel

**Date:** 2026-07-11
**PR:** TBD
**Branch:** `feat/vizor-goals-panel` → `main`

---

## The Goal at the End of the Previous PR

GOVERNS (PR #149) rolled out the seven-stage vocabulary across HUD, launch templates, agent-handoff routing, `init` scaffolding, and `migrate` parsing, and — via Grok's Task 7 — wired `data["goals"]` into `generate_viz_data()`. That blog post explicitly named the gap: Vizor had a `goals` payload with nowhere to render it, and named it as the immediate next dispatch to Agy.

---

## What Moved the Goalpost in This PR

Nothing — this is the named follow-up, dispatched and scoped exactly as flagged. The one addition: since Vizor has no separate template files (all HTML/CSS/JS for the Gantt dashboard lives as Python string literals inside `synlynk/viz.py`), the dispatch prompt had to point Agy at specific line ranges and existing idioms to mirror (`renderDream`, `openDrills`/`openNote` toggle patterns, `escapeHtml`) rather than describing the feature in the abstract.

---

## What Shipped

### A 5th stat card + collapsible panel

`generate_gantt_html()`'s existing `srow` (4 stat cards: Dreams in flight, Active agents, Total spend, Next ship) gets a 5th card, "Business Goals," showing the active-goal count and click-to-expand a collapsible panel below the row:

```js
function renderGoals() {
  const activeCount = goals.filter(g => String(g.status || '').toLowerCase() === 'active').length;
  ...
  if (!goals.length) {
    goalsBody.innerHTML = `<div class="empty-state">... synlynk goal create --outcome "..." --criterion "..." ...</div>`;
    return;
  }
  goalsBody.innerHTML = goals.map(renderGoal).join('');
}
```

Each goal renders outcome (bold), criterion (secondary text), an optional deadline, and a status badge — `renderGoal()` mirrors `renderDream()`'s structure and reuses the file's existing `escapeHtml()` helper. `toggleGoalsPanel()` follows the same open/collapse CSS-max-height idiom already used elsewhere in the file rather than introducing a new one. `renderGoals()` is called from inside the existing `renderDreams()` update cycle (both the empty-dreams early-return path and the normal path), so goals refresh in step with everything else on the dashboard rather than on a separate timer.

### Tests

`tests/test_vizor_goals_panel.py` — two cases: goal data renders the expected DOM ids and content (`goal-count`, `goal-sub`, `goals-panel`, outcome/criterion/deadline text), and an empty `goals: []` list renders the CLI-pointing empty state. Full suite: **909/909 passing** (up from GOVERNS' 900 — 9 new cases including these 2 plus 7 already added by the GOVERNS work).

---

## Brainstorm Visuals

None — this was a small, concretely-scoped follow-up dispatch with exact line anchors and existing UI idioms to mirror, not a new design decision.

---

## What This Achieved

Business Goals (BS-8) are now visible end-to-end: `synlynk goal create` → `goals` table → `generate_viz_data()` → Vizor's Gantt dashboard. A user can see their active outcomes and success criteria without leaving the same screen they're already watching for dream/stage progress.

---

## The New Goalpost

Vizor's Gantt view now surfaces both execution state (dreams/stages) and intent (business goals) side by side. The next open thread, raised separately by the user during this session: revisit the Architect Map (tube map) view — the hand-crafted SVG approach locked in during BS-21 isn't yet confirmed as the right visualization, and needs a brainstorming pass before any redesign work is dispatched.
