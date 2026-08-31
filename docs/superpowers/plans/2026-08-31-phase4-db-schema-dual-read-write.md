# Superpower Implementation Plan — Phase 4: Database Schema Dual-Read / Dual-Write

**Goal:** Implement Phase 4 of the Harness vs. Workspace Agent Separation architecture (#1307 / `story-043eb9ee`), providing database schema migrations, dual-read / dual-write support across `daemon_jobs` and `cost_entries`, and dual-dimension cost reporting.

**Tracking Issue:** #1307  
**Tracking Story:** `story-043eb9ee`  
**Parent Issue:** #1198 / #1255  
**Spec Reference:** `docs/superpowers/specs/2026-08-30-harness-agent-separation-design.md`

---

## 1. Schema & Migration Changes

1. **`synlynk/__init__.py` (`_DB_SCHEMA`):**
   - `daemon_jobs`: add `harness TEXT`, `role TEXT`.
   - `cost_entries`: add `harness TEXT`, `agent_role TEXT`.
   - Indexes:
     - `idx_daemon_jobs_harness` on `daemon_jobs(harness)`
     - `idx_cost_entries_harness` on `cost_entries(harness)`
     - `idx_cost_entries_agent_role` on `cost_entries(agent_role)`

2. **`synlynk/db.py`:**
   - Bump `_DB_MIGRATION_VERSION` to `3`.
   - In `_migrate_db()`:
     - Add missing `harness` and `role` columns to `daemon_jobs`, backfilling `harness = agent`.
     - Add missing `harness` and `agent_role` columns to `cost_entries`, backfilling `harness = agent`.
   - In `_insert_cost_row()`:
     - Accept `harness` and `agent_role` arguments.
     - Dual-write `agent` and `harness` columns.
     - Write `agent_role`.
   - Add query functions:
     - `get_costs_by_harness(conn=None)`
     - `get_costs_by_agent_role(conn=None)`

3. **`synlynk/costs.py`:**
   - In `update_costs()`:
     - Accept optional `harness` and `agent_role`.
     - Forward both to `_insert_cost_row()`.

4. **`synlynk/dispatch.py`:**
   - In `dispatch_agent()`:
     - In job dictionary: set `"harness": agent`, `"role": resolved_agent_role`.
     - In `daemon_jobs` queries: write `harness` and `role` alongside `agent` and `agent_id`.

5. **`synlynk/jobs.py`:**
   - In `_reconcile_jobs()`:
     - Pass `harness` and `agent_role` to `update_costs()`.

---

## 2. Test Plan (TDD)

1. Migration v3 unit tests asserting `daemon_jobs` and `cost_entries` schema columns and backfills.
2. Cost recording tests asserting dual-dimension attribution.
3. Dispatch integration tests asserting `daemon_jobs` dual-write.
4. Regression suite passing 100%.
