# Fully-Derived Roadmap: Eliminating Structural Drift (Approach C)

**Date:** 2026-11-13
**Status:** Approved
**Roadmap entry:** Resolves the "Approach C" follow-up deferred at `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md:66` and `:137` ("deprecate manual `roadmap add/update` entirely, compute the rendered roadmap directly from `decisions`+`goals`+`stories` every time, eliminating the drift class structurally rather than detecting it"). No GitHub issue previously tracked this follow-up (confirmed via `gh issue list --search "Approach C"` — no match); one will be filed when this spec moves to the decide panel.

---

## Context

The drift-governance spec shipped this epic already built **detection**: `check_pr_roadmap_gate`/`synlynk roadmap check` compares the hand-maintained `roadmap_arcs`/`roadmap_phases` tables against `decisions`+`goals` and reports a `ROADMAP_DRIFT` sentinel when they diverge. It explicitly rejected building **elimination** in the same pass as "too large a table-architecture change to bundle with the governance fix."

This spec is that follow-up. Two forks were resolved directly with Nikhil before design work began:

1. **Phase origin:** a roadmap phase must strictly *derive from* — and only come into existence via — a ratified decision. Pre-ratification stubbing (today's `roadmap add` capability) is explicitly not preserved.
2. **Materialization:** `roadmap_arcs`/`roadmap_phases` become SQL VIEWs computed from `goals` (not stored tables with a single writer, and not new columns on `decisions` with a fully live join). Precedent: `capability_scores` (`synlynk/db_schema.py:643`) is already a `CREATE VIEW IF NOT EXISTS` in this codebase — this is not a novel SQLite pattern here.

Today's actual write surface, confirmed by reading the code rather than assuming: `cmd_roadmap_add`/`cmd_roadmap_update` (`synlynk/db.py`) are the human-facing writers; `doctor.py`'s `repair_roadmap_merge_parity()` and `governs_cli.py`'s placement commands also touch `roadmap_arcs`/`roadmap_phases`. Any design that claims "single writer" must account for all four, not just the two CLI commands.

---

## 1. Schema Change — Roadmap Identity Moves onto `goals`

`goals` (`synlynk/db_schema.py:452`) gains three new nullable columns, written exactly once, at the moment a decision ratifies the goal into the roadmap:

- `arc_version TEXT` — e.g. `"v0.29.0"`, matching `dec-7a2b0e91`'s version strings. No FK constraint (views can't be FK targets — see Section 4); validated by the writer code, not the schema.
- `phase_title TEXT` — e.g. `"Phase 1 — The Full-Stack Builder"`.
- `roadmap_priority INTEGER` — ordering within a phase. Named `roadmap_priority` rather than bare `priority` to stay unambiguous against any other priority concept elsewhere in the schema.

`goals.phase_id` (today's FK to `roadmap_phases.id`) is dropped — identity now lives inline on the goal row, so the indirection it provided is no longer needed.

This is additive (`ALTER TABLE goals ADD COLUMN ...`), the same risk class as the existing `phase_id`/`placement_status` migration already in this table's history.

## 2. Single Writer — the Decision-Ratification Path

`decide --record`'s existing goal-linking logic is extended: when a decision ratifies a goal and supplies `--arc`/`--phase`/`--priority` (new explicit CLI args — not scraped from free-text `synthesis`, which would be fragile), it writes `arc_version`/`phase_title`/`roadmap_priority` onto the goal row and flips `placement_status` to `'placed'`.

Everything else that wrote to the old tables is retired or folded in:

- `cmd_roadmap_add`/`cmd_roadmap_update` — **deleted**. There is nothing left to INSERT/UPDATE into (the names now resolve to views); removing the commands outright is correct rather than leaving them to fail confusingly at runtime.
- `doctor.py`'s `repair_roadmap_merge_parity()` — **retired**. Its entire reason for existing (two copies of the same data that can diverge) no longer exists once there is one underlying table. Replaced by a much cheaper advisory check: warn if any `placement_status='placed'` goal has a NULL `arc_version`/`phase_title` (should never happen if ratification is the only writer; costs nothing to check).
- `governs_cli.py`'s placement-adjacent write path — folded into the Section 2 ratification-writer change, not left as a second path.
- `synlynk roadmap check` (the drift gate shipped last epic) — **subsumed and retired**, not run alongside this. There is no second copy left to drift against. This is a direct, intended consequence of this spec, not a side effect to discover later.

## 3. The Views

```sql
CREATE VIEW roadmap_arcs AS
SELECT
  arc_version AS version,
  arc_version AS title,
  CASE
    WHEN MIN(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'shipped'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    ELSE 'planned'
  END AS computed_status,
  MIN(deadline) AS target_date,
  (SELECT GROUP_CONCAT(d.decision_text, ' / ')
     FROM decisions d WHERE d.goal_id IN (
       SELECT id FROM goals g2 WHERE g2.arc_version = goals.arc_version
     )) AS notes
FROM goals
WHERE placement_status = 'placed'
GROUP BY arc_version;

CREATE VIEW roadmap_phases AS
SELECT
  ROW_NUMBER() OVER (ORDER BY arc_version, phase_title) AS id,
  arc_version,
  phase_title,
  CASE
    WHEN MIN(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'shipped'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    ELSE 'planned'
  END AS computed_status,
  MIN(roadmap_priority) AS priority,
  (SELECT GROUP_CONCAT(d.decision_text, ' / ')
     FROM decisions d WHERE d.goal_id IN (
       SELECT id FROM goals g2
       WHERE g2.arc_version = goals.arc_version AND g2.phase_title = goals.phase_title
     )) AS notes
FROM goals
WHERE placement_status = 'placed'
GROUP BY arc_version, phase_title;
```

Caveat: `roadmap_phases.id` (the `ROW_NUMBER()` column) is **not stable** across data changes — it is a display-ordering convenience for `_generate_roadmap_md()`, not an identity. Nothing may hold onto it across requests; Section 4 retargets the one place that used to do so (`cost_entries`) onto `goals.id` instead, specifically to avoid depending on it.

Design choice worth naming explicitly: arc/phase `status` and `target_date` are **derived aggregates**, not new stored fields — status rolls up from constituent goals' own `status`, and `target_date` reuses the `goals.deadline` column that already exists (`MIN()` across the group). `notes` pulls from the ratifying decisions' own `decision_text`. This is not an accident of convenience — it means structural identity lives on `goals` and narrative justification lives on `decisions`, with no new field needed on either to carry something the other already expresses.

`_generate_roadmap_md()` queries `roadmap_arcs`/`roadmap_phases` by name exactly as it does today — views are transparent to this function, confirming the original Approach C claim that render logic itself needs no changes.

## 4. The Foreign-Key Problem — `cost_entries.epic_id`/`phase_id`

SQLite foreign keys cannot target a view. `cost_entries.epic_id REFERENCES roadmap_arcs(id)` and `cost_entries.phase_id REFERENCES roadmap_phases(id)` break the moment those names become views instead of tables.

**Resolution:** retarget both columns to `REFERENCES goals(id)` directly — the specific goal whose placement defines the arc/phase a cost entry was logged against. This is strictly more precise than pointing at a synthetic grouped view row, and it sidesteps the FK-to-view restriction entirely rather than working around it.

**Migration cost (real, named explicitly):** existing `cost_entries` rows with a non-null `phase_id`/`epic_id` need a one-time backfill to the corresponding `goals.id`. For each old `phase_id`, resolve to any placed goal sharing that phase's `(arc_version, phase_title)` — deterministically, lowest `goals.id` wins on ties — and emit a migration report listing every `phase_id` that mapped ambiguously (more than one candidate goal) for manual review rather than silently picking one. This is the single largest risk item in this spec; see Rollout below for how it's sequenced to stay reversible until verified.

## 5. CLI / Surface Changes

- `synlynk roadmap add` / `synlynk roadmap update` — removed from the CLI surface entirely (Section 2).
- `synlynk roadmap check` — removed; its job is structurally impossible to need now (Section 2).
- `synlynk roadmap` (render) — unchanged; queries the views by name.
- `decide --record` — gains `--arc`/`--phase`/`--priority` flags, documented as the only way a goal enters the roadmap.

## 6. Rollout

This is a real schema migration, not a purely additive one (dropping two tables and replacing them with views is invasive in a way "add three nullable columns" is not). Sequenced in two steps to keep a verification checkpoint before the irreversible cutover:

**Step 1 (dual-write, verify):** add the new `goals` columns and the new views *alongside* the existing `roadmap_arcs`/`roadmap_phases` tables (temporarily renamed, e.g. `roadmap_arcs_legacy`). Backfill every currently-placed goal's `arc_version`/`phase_title`/`roadmap_priority` from its existing `phase_id` linkage. Diff the new views' output against the legacy tables for every current row — any mismatch blocks the cutover and is investigated, not silently accepted.

**Step 2 (cutover):** once the diff is clean, drop the legacy tables, rename the views into the production names, run the `cost_entries` FK backfill from Section 4, delete `cmd_roadmap_add`/`cmd_roadmap_update`/`synlynk roadmap check`/`repair_roadmap_merge_parity()`.

No `observe`/`enforce` phase-in applies here the way it did for the drift gate — this is a schema swap, not a new blocking check, so the two-step dual-write/cutover sequence is the rollout safety mechanism instead.

---

## Deferred (explicitly out of scope for this spec)

- **`require_linked_goal_mode` interaction** — orthogonal to this spec; the 100%-GOVERNS-adherence gate keeps working unchanged against `goals`/`decisions` directly.
- **Multi-goal arcs with divergent `deadline` values** — `MIN()` is the chosen rule; no fancier reconciliation is built. Accepted as a known edge case.
- **Ambiguous `cost_entries` backfill rows** — resolved by manual review per the migration report (Section 4), not by an automated heuristic.
- **Filing the GitHub tracking issue** — happens when this spec moves to the decide panel, not resolved in this document.
- **Deleting the retired code** (`cmd_roadmap_add`, `cmd_roadmap_update`, `synlynk roadmap check`, `repair_roadmap_merge_parity()`) — named here as a consequence, but the actual deletion is an implementation-plan task, not performed by this spec.

---

## Testing / Rollout Criteria

- `tests/test_roadmap_views.py` — verifies the Section 1 schema migration, the Section 3 view SQL against hand-constructed `goals`/`decisions` fixtures (including the status-rollup and `notes` GROUP_CONCAT logic), and that `_generate_roadmap_md()` produces byte-identical output against the views vs. today's tables for a fixed fixture set.
- `tests/test_cost_entries_backfill.py` — the Section 4 migration script against a fixture with at least one deliberately ambiguous `phase_id` (two goals sharing an `(arc_version, phase_title)`), asserting the ambiguity is reported, not silently resolved.
- Step 1's dual-write diff (Section 6) is itself the primary pre-cutover test — run against the real `state.db`, not just fixtures, before Step 2 executes.
