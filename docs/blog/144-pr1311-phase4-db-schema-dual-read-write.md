---
title: "PR #1311 — Harness vs. Agent Separation Phase 4: Database Schema Dual-Read / Dual-Write"
date: 2026-08-31
series: "Building the OS for Multi-Agent Development"
post: 144
pr: "#1311"
issue: "#1307"
status: open
---

# PR #1311 — Harness vs. Agent Separation Phase 4: Database Schema Dual-Read / Dual-Write

## The Broader Goal

Following the architecture established in `docs/superpowers/specs/2026-08-30-harness-agent-separation-design.md`, synlynk distinguishes two distinct concepts that were previously conflated under the `agent` column:
1. **Compute Harnesses:** The execution runtimes (`claude`, `codex`, `grok`, `agy`, `local`).
2. **Workspace Agents:** The organizational charter roles (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`).

Phase 4 (Issue #1307 / Story `story-043eb9ee`) migrates synlynk's persistent database schema and query surfaces to support this distinction while maintaining 100% backward compatibility via dual-read and dual-write semantics.

## What Was Missing & Root Cause

Previously:
- `daemon_jobs` and `cost_entries` only stored an `agent` column. When a job was dispatched for role `dev` on harness `codex`, the database recorded `agent="codex"`, discarding or entangling the role dimension.
- Cost aggregation functions could only group by `agent`, preventing cost breakdowns along the two real axes: compute runtime spend vs. team function / role spend.
- Schema migrations needed to gracefully handle existing SQLite ledgers and linked worktrees without locking contention.

## What Shipped

1. **Database Schema & Version 3 Migration (`synlynk/db.py`, `synlynk/__init__.py`):**
   - Bumped `_DB_MIGRATION_VERSION = 3`.
   - Added `harness TEXT` and `role TEXT` columns to `daemon_jobs`.
   - Added `harness TEXT` and `agent_role TEXT` columns to `cost_entries`.
   - Executed backfill migrations (`UPDATE ... SET harness = agent`) and created dedicated indexes (`idx_daemon_jobs_harness`, `idx_cost_entries_harness`, `idx_cost_entries_agent_role`).
   - Added `get_costs_by_harness()` and `get_costs_by_agent_role()` query helpers.
   - Updated `_insert_cost_row()` with dual-write semantics and role fallback lookups from `stories` or `daemon_jobs`.

2. **Dispatch & Jobs Layer Dual-Write (`synlynk/dispatch.py`, `synlynk/jobs.py`, `synlynk/costs.py`):**
   - Added `_ensure_daemon_job_harness_columns()` for resilient runtime migrations across linked worktrees.
   - Populated `harness` and `role` across `daemon_jobs` (INSERT / UPDATE) and in-memory job dictionaries.
   - Forwarded `harness` and `agent_role` through `update_costs()`, `_reconcile_jobs()`, `_reconcile_daemon_jobs()`, and `_ensure_daemon_job_cost_entry()`.
   - Unified connection management in `dispatch_agent()` to eliminate SQLite lock contentions during single-threaded capability sweeps and quota gating.

3. **Comprehensive Tests:**
   - Added migration tests in `tests/test_migrate.py`.
   - Added cost entry schema and insertion tests in `tests/test_cost_ledger.py`.
   - Added dispatch persistence tests in `tests/test_dispatch.py`.
   - Verified full repository test suite: **2405 passed, 2 skipped**.
