# Invariant 4 Design Spec: Single-Writer SQLite WAL Ledger with Leased Worktree Locks

**Status:** Approved  
**Author:** Agy (Gemini) / Lead Architect  
**Date:** 2026-09-27  
**Issue:** [#1812](https://github.com/nikhilsoman/synlynk/issues/1812)  
**Epic:** [#1805](https://github.com/nikhilsoman/synlynk/issues/1805) (`goal-5be4eb8b`)  

---

## 1. Executive Summary & Thesis

In a concurrent multi-agent autonomous engineering fleet (where Codex, Agy, Claude, Grok, and daemon processes execute simultaneously across worktrees), multiple agents read and mutate state concurrently. 

**Invariant 4 Mandate:**
1. **Single-Writer SQLite WAL Ledger:** All SQLite connections must strictly enforce Write-Ahead Logging (`WAL`), normal synchronization, 30s busy timeout, and foreign keys. All mutating transactions must use a serialized `write_transaction` context manager with `BEGIN IMMEDIATE` and exponential backoff retry on contention.
2. **Leased Worktree Locks:** Every active worktree must be governed by an explicit lease lock (stored in the `worktree_leases` table in `state.db` and on-disk `.synlynk-lease.json`) with PID tracking, TTL expiration (default 15 minutes), heartbeat renewal, and autonomous stale lease reclamation.

---

## 2. Architecture & Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Synlynk Fleet Runtime                     │
│  (Codex, Agy, Claude, Grok, Background Daemons, TUI)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    ┌────────────────────┐          ┌──────────────────────┐
    │  wal_ledger.py     │          │  worktree_lease.py   │
    │  - ensure_pragmas  │          │  - acquire_lease     │
    │  - write_tx(retry) │          │  - renew_lease       │
    │  - wal_health      │          │  - release_lease     │
    └──────────┬─────────┘          │  - reclaim_stale     │
               │                    └──────────┬───────────┘
               ▼                               ▼
    ┌────────────────────┐          ┌──────────────────────┐
    │ state.db (WAL)     │◄─────────┤ worktree_leases table│
    │ - WAL mode pragma  │          │ & .synlynk-lease.json│
    │ - busy_timeout=30s │          └──────────────────────┘
    └────────────────────┘
```

### 2.1 `synlynk/wal_ledger.py`
- `ensure_wal_pragmas(conn)`: Enforces `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, `PRAGMA busy_timeout=30000;`, `PRAGMA foreign_keys=ON;`.
- `write_transaction(conn, max_retries=10, initial_backoff=0.05, max_backoff=1.0)`: Context manager executing `BEGIN IMMEDIATE` with exponential backoff on `sqlite3.OperationalError: database is locked`.
- `check_wal_health(db_path)`: Verifies WAL mode and sidecar health without acquiring exclusive locks.

### 2.2 `synlynk/worktree_lease.py`
- Schema:
  ```sql
  CREATE TABLE IF NOT EXISTS worktree_leases (
      worktree_id    TEXT PRIMARY KEY,
      job_id         TEXT,
      worktree_path  TEXT NOT NULL,
      leased_by      TEXT NOT NULL,
      pid            INTEGER NOT NULL,
      acquired_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      heartbeat_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      expires_at     TIMESTAMP NOT NULL,
      status         TEXT NOT NULL DEFAULT 'active'
  );
  CREATE INDEX IF NOT EXISTS idx_worktree_leases_status ON worktree_leases(status, expires_at);
  CREATE INDEX IF NOT EXISTS idx_worktree_leases_path ON worktree_leases(worktree_path);
  ```
- `acquire_worktree_lease(worktree_path, leased_by, job_id=None, duration_seconds=900, conn=None)`:
  - Checks existing lease. If active and held by living PID with `expires_at > now`, returns `acquired: False`.
  - If lease expired or PID dead (`os.kill(pid, 0)` fails), marks existing lease as `expired` and steals/acquires the lease.
  - Creates `.synlynk-lease.json` in the worktree.
- `renew_worktree_lease(worktree_path, leased_by, extend_seconds=900, conn=None)`: Heartbeat updater.
- `release_worktree_lease(worktree_path, leased_by, conn=None)`: Marks lease `released` and cleans lockfile.
- `audit_and_reclaim_stale_worktree_leases(conn=None)`: Autonomous recovery sweep.

### 2.3 Dispatch & Job Lifecycle Integration
- `dispatch.py`: Acquired during worktree provisioning (`_create_job_worktree`).
- `jobs.py`: Released upon job termination and zombie reaping (`_reap_zombie_worktree`).
- `worktree.py`: Audit command detects and reclaims stale leases.

---

## 3. Verification & Test Strategy
- `tests/test_wal_ledger.py`: Verifies WAL pragma application, concurrent multi-threaded write transactions without lock failures, and backoff retry under contention.
- `tests/test_worktree_lease.py`: Verifies lease acquisition, renewal, conflict rejection, dead PID stealing, and clean release.
- `tests/test_worktree_lease_concurrency.py`: Verifies multi-process concurrent lease racing and recovery.
- Full test suite run (`3,364+` tests) with 100% green pass rate.
