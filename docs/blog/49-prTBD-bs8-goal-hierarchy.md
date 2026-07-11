# BS-8: The Business Goal Layer

**Date:** 2026-07-11
**PR:** TBD
**Branch:** `feat/bs8-goal-hierarchy` → `main`

---

## The Goal at the End of the Previous PR

v0.11.0 (BS-13 Observatory + BS-12 Agent Autonomy Bridge) completed the operational layer: dispatch, observe, diagnose, repair, and hand off, all from the CLI. What synlynk still lacked was a layer above the Dream/Story hierarchy that answered "why are we building this" in terms a founder or PM would recognize — an explicit Business Goal with an outcome, a success criterion, and a deadline, that stories and roadmap arcs could be traced back to.

That gap was surfaced during an rxcc roadmap gap analysis and formalized into the BS-8 design spec (`docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`), alongside a companion GOVERNS 7-stage rollout plan replacing the drifted `dream/plan/work/ship/maintain/engage` cycle vocabulary.

---

## What Moved the Goalpost in This PR

Two things shifted during implementation, not design:

**Execution-handoff conflict.** The `writing-plans` skill defaults to Claude executing plans directly (Subagent-Driven or Inline). CLAUDE.md locks Claude to PM/reviewer only — all implementation dispatches to Codex/Agy/Grok via `synlynk dispatch`. Resolved by treating `synlynk dispatch` itself as the execution mechanism: Claude authors dispatch prompts, reviews diffs for plan fidelity, and does git integration (never new-logic authorship).

**Dispatch strategy, mid-plan.** Task-by-task dispatch (one Codex call per plan task, review between each) was the initial approach. It surfaced a hard constraint: `synlynk dispatch` creates a fresh worktree/branch off `main`'s current HEAD every time — there's no flag to continue an existing branch. Codex was also given explicit `git fetch && git reset --hard` sync instructions across three escalating levels of directiveness and never once executed them, instead recreating prior tasks' work from scratch atop stale `main`. After manually reconciling this twice (Tasks 2 and 3), the overhead was flagged and the remaining tasks (4-7) were dispatched as one whole-plan call instead of four.

---

## What Shipped

### Schema (Tasks 1-2)

```sql
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     TEXT NOT NULL UNIQUE,
    outcome     TEXT NOT NULL,
    criterion   TEXT NOT NULL,
    deadline    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_contributions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id  TEXT NOT NULL REFERENCES goals(goal_id),
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    UNIQUE(goal_id, story_id)
);
```

`stories` and `roadmap_arcs` each get a nullable `goal_id` FK, added via the standard idempotent `_migrate_db()` ALTER pattern (`if col not in existing_cols: try: ALTER ...; except sqlite3.OperationalError: pass`). Nullable by design — a story with `goal_id IS NULL` is simply excluded from goal rollups, no separate `lane` column needed.

### CLI + Commands (Tasks 3-6)

```bash
synlynk goal create --outcome "..." --criterion "..." [--deadline YYYY-MM-DD]
synlynk goal list
synlynk goal link <story_id> --goal <goal_id> [--secondary]
synlynk goal status
```

`cmd_goal_link` distinguishes primary linkage (sets `stories.goal_id` directly) from secondary/cross-cutting contribution (`goal_contributions` row only, story's primary goal unchanged) — this lets a story serve one primary goal while still counting toward others.

`cmd_goal_status` is a no-arg rollup: for every active goal, prints story completion (`{done}/{total} done`), deadline, and linked roadmap arc versions.

### Context Injection (Task 7)

The single most-recent active goal is now injected as a `## Active Goal` section at the top of every generated `.synlynk/context.md`, so every dispatched agent sees the business outcome its task nominally serves, not just the next story title.

### Tests

10 tests added in `tests/test_goals.py`. Full suite: 887/888 passing (one pre-existing, unrelated version-pin failure).

---

## Brainstorm Visuals

None for this PR — the GOVERNS stage model and Business Goal shape were settled via `synlynk decide` multi-agent consensus and written directly into the design spec, not visual brainstorming.

---

## What This Achieved

BS-8 gives synlynk a traceable line from a founder-level outcome down to the story a dispatched agent is actually working on. Combined with the operational layer from v0.11.0, the loop is now: **why** (Goal) → **what** (Story/Arc) → **dispatch** → **observe** → **diagnose/repair**.

It also produced a concrete operational finding for this project's Claude-as-PM/dispatch-execution model: whole-plan dispatch with the plan's exact function signatures spelled out inline in the prompt is markedly more reliable than task-by-task dispatch with a sync instruction Codex won't follow. The first whole-plan attempt still drifted (wrong `cmd_goal_link`/`cmd_goal_status` signatures, a missing rollup, a reference to a nonexistent table) and had to be rejected and redispatched — pinning the plan's literal code in the prompt, rather than referencing the plan file by path, is what closed the gap.

---

## The New Goalpost

With BS-8 merged, the GOVERNS 7-stage rollout plan (`docs/superpowers/plans/2026-07-11-governs-stage-rollout-plan.md`) is next — it depends on BS-8 Task 2's `goal_id` column for its own roadmap goal-tag parsing task. Split across three agents: Codex takes the interdependent core-file renames (`hud.py`, `LAUNCH_TASK_TEMPLATES`, `task_to_cycle`, migration cleanup, roadmap tag parsing) as one whole-plan dispatch; Agy takes the `fallback_roadmap` template's Business Goals section; Grok takes the Vizor `generate_viz_data()` goals payload.
