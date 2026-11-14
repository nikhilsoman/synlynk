# Fully-Derived Roadmap Implementation Plan (Approach C / v0.35.0)

**Date:** 2026-11-14  
**Author:** Agy (Home Conductor)  
**Spec Reference:** `docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md`  
**Master Roadmap Reference:** Issue #5247 (Phase 1 / Track 3)  
**Target Release:** `v0.35.0`

---

## 1. Goal & Architectural Overview

Eliminate structural roadmap drift by converting `roadmap_arcs` and `roadmap_phases` from hand-maintained SQLite tables into dynamic SQL VIEWs derived directly from `goals` and `decisions`:
1. Move roadmap identity (`arc_version`, `phase_title`, `roadmap_priority`) onto `goals`.
2. Materialize `roadmap_arcs` and `roadmap_phases` as SQL VIEWs with rollup status, min target dates, and aggregated decision notes.
3. Migrate `cost_entries` foreign keys from legacy tables to `goals(id)`.
4. Extend `decide --record` with `--arc`, `--phase`, and `--priority` as the single writer.
5. Deprecate manual `synlynk roadmap add/update` and `synlynk roadmap check`.

---

## 2. Tasks & Breakdown

### Task 1: Schema Migration & Derived Views (`synlynk/db_schema.py`)
- Add `arc_version`, `phase_title`, `roadmap_priority` to `goals` table schema definition and ensure migration adds missing columns.
- Define `CREATE VIEW IF NOT EXISTS roadmap_arcs` and `CREATE VIEW IF NOT EXISTS roadmap_phases` SQL definitions in `synlynk/db_schema.py`.
- Add helper `ensure_roadmap_views(conn)` ensuring view creation when opening database.
- **Tests:** `tests/test_roadmap_views.py` (validate schema, view query output, computed statuses, and notes grouping).

### Task 2: Foreign Key Migration & Backfill (`synlynk/roadmap_migration.py`)
- Implement `backfill_cost_entries_goals(conn)` mapping old `cost_entries.phase_id` to `goals.id`.
- Generate migration audit report on ambiguous candidate mappings.
- **Tests:** `tests/test_cost_entries_backfill.py` (test unambiguous and ambiguous resolution scenarios).

### Task 3: Decision Ratification Writer & CLI Cleanup
- Add `--arc`, `--phase`, `--priority` CLI arguments to `decide --record` in `synlynk/cli.py` and `synlynk/db.py`.
- Update `cmd_decide_record` to write placement metadata to the referenced goal row.
- Remove manual `synlynk roadmap add`, `synlynk roadmap update`, and `synlynk roadmap check` from taxonomy.
- Re-run `python3 scripts/generate_command_docs.py` to regenerate command docs.
- **Tests:** `tests/test_cli_roadmap_derived.py`, `tests/test_docs_sync.py`.

### Task 4: Version Bump, Release Notes & Verification
- Bump `VERSION` to `0.35.0`.
- Update `CHANGELOG.md` with `[v0.35.0]` section.
- Update `README.md` version badge and release notes.
- Verify `release --check-docs` and full test suite.
- Open PR, dispatch QA review, and merge.

---

## 3. Verification Commands
- `pytest tests/test_roadmap_views.py tests/test_cost_entries_backfill.py tests/test_cli_roadmap_derived.py tests/test_docs_sync.py -v`
- `python3 bin/synlynk.py release --check-docs --pr-mode`
- Full CI test matrix.
