# GOVERNS: Rolling Out the Seven-Stage Vocabulary

**Date:** 2026-07-11
**PR:** TBD
**Branch:** `feat/governs-stage-rollout` → `main`

---

## The Goal at the End of the Previous PR

BS-8 (PR #146) gave synlynk a Business Goal layer above Dream/Story — an explicit outcome, success criterion, and deadline, with `goal_id` FKs on `stories` and `roadmap_arcs`, `cmd_goal_link`/`cmd_goal_status` rollups, and context injection so every dispatched agent sees the business outcome its task serves. That PR's blog post flagged the next goalpost explicitly: roll out the GOVERNS seven-stage vocabulary (`goal/open/visualize/execute/release/notify/sustain`) to replace the drifted six-value `dream/plan/work/ship/maintain/engage` cycle model — inconsistently already spelled `design`/`build` in places — across every surface that still spoke the old vocabulary.

---

## What Moved the Goalpost in This PR

Nothing shifted in scope — the plan (`docs/superpowers/plans/2026-07-11-governs-stage-rollout-plan.md`) was written and approved in full before dispatch. What changed was **how** it was dispatched, and it's the same lesson BS-8 already taught, applied more deliberately this time.

The GOVERNS plan document, like the BS-8 plan before it, lives only on `chore/sdlc-goal-design` — a docs-only branch that's never merged to `main` (per this project's docs-PR-separation policy). `synlynk dispatch` always branches a fresh worktree off `main`'s current HEAD, which means a dispatched agent has **zero path-based access** to that plan file, no matter how explicit the sync instructions are. This was misdiagnosed during BS-8 as "Codex won't follow git-sync instructions" — it's actually structural: the file isn't reachable from any branch the dispatch worktree can see.

For GOVERNS, this was treated as a known constraint from the start rather than discovered mid-plan: every dispatch prompt (Codex, Agy, Grok) embedded the plan's literal code — exact dicts, exact remap tables, exact test files, exact line-anchored instructions — directly in the `--task` text. No dispatch referenced the plan file by path.

One task (Task 1, the `hud.py` `CYCLES`/`CYCLE_COLOURS` rename) turned out to have already shipped separately as PR #144 before this plan's dispatch ran. Codex correctly detected the vocabulary was already in place and skipped re-doing it rather than reverting to the old values or duplicating the commit — confirmed by diff review, not just trusted.

---

## What Shipped

### Three parallel dispatches, one deliberate ordering rule

Given each of the seven remap surfaces was independently testable, the plan was split three ways by specialty (per CLAUDE.md's agent role table) and dispatched in parallel rather than sequentially:

| Agent | Job | Scope |
|---|---|---|
| Codex | `job-6cba8ca0` | Tasks 2, 3, 4, 6 — `LAUNCH_TASK_TEMPLATES`, `task_to_cycle`, `cycle_capability` migration, roadmap goal-tag parsing (CLI/backend plumbing) |
| Agy | `job-feab0107` | Task 5 — `fallback_roadmap` template's Business Goals section (templates/content) |
| Grok | `job-273bbb6f` | Task 7 — Vizor `generate_viz_data()` goals payload (data structures/JS-adjacent) |

All three landed clean commits with zero drift from the plan's exact specs on the first attempt — no redispatch needed this time, validating that embedding literal plan content up front (rather than discovering the need for it after a failed attempt) is the actual fix.

### `LAUNCH_TASK_TEMPLATES` — 15 templates remapped

Every template's `"cycle"` key moved from the old six-value vocabulary to one of the seven GOVERNS keys, e.g. `arch-review`: `dream` → `visualize`, `docs-audit`: `design` (drift) → `notify`, `a11y-audit`: `design` (drift) → `release`. The `lifecycle-setup` template's own prompt text and title/description were updated from "6-cycle" to "7-stage GOVERNS" framing so the vocabulary it *teaches* an agent matches the vocabulary the harness now enforces.

### `task_to_cycle` handoff routing — orphaned key resolved

```python
task_to_cycle = {
    "implement": "execute",
    "review": "execute",
    "plan": "open",
    "debug": "sustain",
    "test": "execute",
    "docs": "notify",
    "default": "execute",
}
```

`"review": "engage"` was an orphaned mapping — `engage` doesn't exist in the GOVERNS vocabulary. It now resolves to `execute`, since code review is a checkpoint inside the build/dispatch loop, not a separate stage.

### `cycle_capability` migration cleanup

```python
cycle_remap = {
    "dream": "goal", "design": "visualize", "plan": "open",
    "work": "execute", "build": "execute", "ship": "release",
    "maintain": "sustain", "engage": "execute",
}
for old, new in cycle_remap.items():
    conn.execute("UPDATE cycle_capability SET cycle=? WHERE cycle=?", (new, old))
```

This UPDATE-based remap runs after the pre-existing `DELETE FROM cycle_capability WHERE cycle IN ('design','build','sustain')` line, which was left in place unmodified — it becomes a no-op given the UPDATE now runs after it, but removing historical migration lines was out of scope for this plan.

### Roadmap goal-tag parsing — wires BS-8 into `migrate`

```python
goal_m = re.search(r'<!--\s*goal:(\S+)\s*-->', line)
goal_id = goal_m.group(1) if goal_m else None
```

`_parse_roadmap_md` now extracts `<!-- goal:goal-xxxxxxxx -->` tags from arc headers and strips them from the display title; the tag is wired into the `INSERT INTO roadmap_arcs` statement so imported arcs carry their goal link. This is the one task with a hard dependency on BS-8 (Task 2's `goal_id` column) — confirmed present on `main` before this dispatch ran.

### `init` template — Business Goals section (Agy)

The `fallback_roadmap` scaffold now includes a `## Business Goals` section between the version table and "Recent work", pointing new projects at `synlynk goal create` from their very first `roadmap.md`.

### Vizor payload — `goals` key (Grok)

`generate_viz_data()` now queries active goals and sets `data["goals"]`, following `viz.py`'s existing defensive `try/except Exception` convention used throughout the rest of that function for every DB-derived section — front-end rendering of a Goals panel is explicitly out of scope, flagged as a follow-up dispatch to Agy.

### Tests

6 new test files (`test_launch_templates.py`, `test_handoff_cycle_map.py`, `test_cycle_migration.py`, `test_goal_tag_parsing.py`, `test_init_business_goals.py`, `test_viz_goals.py`), plus an import-wiring regression test added to `test_migrate.py` by Codex per the plan's Step 6. Codex also fixed a pre-existing stale version-pin failure (`test_version_is_0100` → `test_version_is_0110`) it hit while running the full suite mid-task. Full suite: **900/900 passing.**

---

## Brainstorm Visuals

None — the seven-stage vocabulary and remap tables were settled in the GOVERNS design spec (`docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`) and this plan document, not visual brainstorming.

---

## What This Achieved

Every surface that spoke the drifted `dream/plan/work/ship/maintain/engage`/`design`/`build` vocabulary — HUD rendering, task-launch templates, agent-handoff routing, `init` scaffolding, `migrate` parsing, Vizor's data payload — now speaks one consistent seven-key language that maps directly to a `synlynk` command (`goal`, `open`, `viz`, `exec`/`dispatch`, `release`, notify convention, `repair`/`doctor`/`status`). Combined with BS-8, a roadmap arc tagged `<!-- goal:goal-xxxxxxxx -->` now carries its Business Goal link all the way from markdown import through to `roadmap_arcs.goal_id`.

Operationally, this PR is the first time the "embed literal plan content in the dispatch prompt" fix was applied proactively across three parallel agents from the start, rather than discovered reactively after a failed attempt (as it was mid-BS-8). All three dispatches landed clean on the first pass — the fix generalizes.

---

## The New Goalpost

With GOVERNS merged, both halves of the Business Goal SDLC model design spec are now live on `main`: the Business Goal layer itself (BS-8) and the seven-stage vocabulary that organizes work under it (GOVERNS). The `abstraction-level dev/team/enterprise mapping` sub-section of the original design spec's Part 3 was explicitly scoped out of the GOVERNS plan as a separate config/gating concern (`.synlynk/config.json` mode field) rather than a vocabulary rename — that's the next candidate for a brainstorm-to-plan cycle. Vizor's front-end Goals panel (surfacing the `goals` payload Task 7 now provides) is a smaller, more immediate follow-up dispatch to Agy.
