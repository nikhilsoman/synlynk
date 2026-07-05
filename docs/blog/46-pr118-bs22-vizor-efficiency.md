# PR #118 — BS-22: Vizor Gets Its Eyes

**Date:** 2026-07-05
**PR:** [#118](https://github.com/nikhilsoman/synlynk/pull/118)
**Branch:** `feat/bs22-vizor-efficiency` → `main`

---

## The Goal at the End of the Previous PR

After the Live Job Observatory (BS-13, PR #117), synlynk could watch a live multi-agent fleet in real time — which agent was running, what it cost, how long it had been running. The next target was agent autonomy and permissions (BS-12). But before we locked in that scope, a smaller, unblocked improvement was ready to ship: making the Vizor **Efficiency tab** actually informative.

The Efficiency tab existed. It had agent cards. But it showed structural skeleton data without telling you anything meaningful about how work was actually being distributed across the team.

---

## What Moved the Goalpost in This PR

BS-22 was originally deferred because it consumed data from `eco.agents[agent].capacity` and `eco.cycle_capability` — keys that BS-16 (Ecosystem Status) was responsible for populating. But BS-16 shipped a safe `is_placeholder` fallback in `viz.py` that already modelled those keys with realistic dummy values. That unblocked BS-22 entirely: the Efficiency tab could be enriched immediately without waiting for live capacity telemetry.

The strategic priority also sharpened: with Developer Preview approaching, every partially-visible feature needed to be complete, not skeletal. A tab with agent cards and empty bars communicates "work in progress" to anyone who opens it. That's a bad first impression at exactly the wrong moment.

---

## What Shipped

### R/W/T Budget Bars on Agent Cards

Each agent card in the Efficiency tab now shows three utilisation bars: **Read**, **Write**, and **Test** budget consumption expressed as a percentage of `TIER1_CAPACITY`. This is the most direct answer to "is this agent loaded or idle?" visible at a glance.

Implementation: new `.rwt-section` and `.rwt-row` CSS classes in `generate_efficiency_html()` in `synlynk/viz.py`. Each bar renders as a percentage-width `div` inside a fixed-width track. Colours match the agent's theme (Claude blue, Agy green, Codex amber, Grok purple).

### Cycle × Agent Capability Matrix

Below the agent cards, a full `6 × 4` table shows which agent has **full**, **partial**, or **none** support for each of the six workflow cycles: `dream`, `plan`, `work`, `ship`, `maintain`, `engage`.

Each cell shows a badge: `.cap-full` (solid), `.cap-partial` (hatched), `.cap-none` (greyed). The matrix answers at a glance which agents can cover which phases of the work cycle — essential information when routing a new story.

Data source: `get_capability_level(agent, cycle, eco)` — a new function that resolves support level from the ecosystem data or the placeholder dict in order. Live data overrides placeholder; missing data renders as `none`.

### Per-Agent Radar Hexagon SVGs

Each agent card gets a `80×80 px` SVG radar hexagon with six axes (one per cycle). Axis score maps support level to a 0.0–1.0 scale: `full` → 1.0, `partial` → 0.5, `none` → 0.0. The polygon fills with the agent's theme colour at 30% opacity.

This gives an at-a-glance capability fingerprint per agent — two agents with the same total capacity but different cycle coverage are immediately distinguishable.

### Review Fixes Applied

A code review after the initial implementation caught three issues, all fixed before merge:

1. **Blocking:** The old SVG circles matrix hard-coded `support = "none"` for every cell when `is_placeholder=True`, contradicting the new text matrix which correctly showed the placeholder cycle data. Fix: removed the `is_placeholder` short-circuit.
2. **Warning:** CSS class `cap-{support}` was built from a raw DB string with no case normalisation. Added `.lower()` to prevent silent styling breaks from mixed-case DB values.
3. **Warning:** The third fallback block in `get_capability_level()` was dead code — both data sources use lowercase keys, so it never executed. Removed.

---

## What This Achieved

The Efficiency tab went from a structural placeholder to a genuine information surface. Any team member opening Vizor can now answer:

- Which agents are capacity-constrained right now?
- Which agents can cover the `ship` cycle vs. just `dream`?
- Which agent has the best cycle coverage breadth?

This matters for routing decisions when allocating new stories, and for understanding where bottlenecks form as the workgroup scales.

---

## The New Goalpost

With the Efficiency tab complete, the visible surface of Vizor is coherent for Developer Preview. The next — and larger — milestone is the **Agent Autonomy Bridge (BS-12, PR #119)**: permission grants, per-project harness config, agent handoff protocol, a doctor-guided fix wizard, and SOP codification across all directive files. That's the scaffolding for agents that can operate independently without requiring human intervention at every decision point.
