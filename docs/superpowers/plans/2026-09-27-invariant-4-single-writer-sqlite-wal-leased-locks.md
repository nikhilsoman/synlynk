# Invariant 4 Implementation Plan: Single-Writer SQLite WAL Ledger with Leased Worktree Locks

**Issue:** [#1812](https://github.com/nikhilsoman/synlynk/issues/1812)  
**Epic:** [#1805](https://github.com/nikhilsoman/synlynk/issues/1805) (`goal-5be4eb8b`, `story-d3df3fbd`)  
**Spec:** `docs/superpowers/specs/2026-09-27-invariant-4-single-writer-sqlite-wal-leased-locks-design.md`  

---

## Tasks

- [ ] **Task 1: Implement `synlynk/wal_ledger.py` (WAL Pragmas & Write Transaction Serializer)**
  - Implement `ensure_wal_pragmas(conn)` setting `WAL`, `NORMAL` synchronous, `busy_timeout=30000`, and `foreign_keys=ON`.
  - Implement `write_transaction(conn, max_retries=10, initial_backoff=0.05, max_backoff=1.0)` context manager.
  - Implement `check_wal_health(db_path)`.
  - Unit tests in `tests/test_wal_ledger.py`.

- [ ] **Task 2: Implement `synlynk/worktree_lease.py` (Leased Worktree Locks)**
  - Define `worktree_leases` table schema in `synlynk/__init__.py` (and migration).
  - Implement `acquire_worktree_lease()`, `renew_worktree_lease()`, `release_worktree_lease()`, `audit_and_reclaim_stale_worktree_leases()`, and `get_active_worktree_lease()`.
  - Handle dead PID detection and expired TTL auto-stealing.
  - Maintain `.synlynk-lease.json` on-disk sync.
  - Unit tests in `tests/test_worktree_lease.py` and `tests/test_worktree_lease_concurrency.py`.

- [ ] **Task 3: Integrate WAL Serializer & Leased Worktree Locks into Core Dispatch & Jobs**
  - Integrate `ensure_wal_pragmas` into `_connect()` in `synlynk/__init__.py`.
  - Integrate lease acquisition in `_create_job_worktree()` in `synlynk/dispatch.py`.
  - Integrate lease release in `_reap_zombie_worktree()` and job lifecycle in `synlynk/jobs.py`.
  - Integrate stale lease audit into `synlynk/worktree.py`.
  - Export `wal_ledger` and `worktree_lease` in `synlynk/__init__.py` `_LEGACY_MODULES`.
  - Verify in `tests/test_dispatch.py`, `tests/test_jobs.py`, and `tests/test_worktree_clean.py`.

- [ ] **Task 4: Full Suite Verification, PR Creation & QA Review Merge**
  - Run full test suite (3,364+ tests) ensuring 100% pass rate.
  - Create PR closing Issue #1812 under branch `feat/agy/invariant-4-wal-ledger-leased-worktree-locks`.
  - Dispatch non-author QA reviewer (Codex) with `--requires-gh-write` to review and merge once CI is green.
