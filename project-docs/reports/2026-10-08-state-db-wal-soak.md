# state.db WAL soak — 20–50 concurrent writers (gh:#2102)

Date: 2026-10-08  
Host: macOS, Python 3.14, SQLite via stdlib `sqlite3`  
Ledger: isolated temp `state.db` initialized through `synlynk._get_db` (full schema + WAL pragmas). Production `~/.synlynk` ledgers were not opened.

## Scenario

Repeatable testbed scenario `state_db_wal_soak`:

- N concurrent writers (20–50), each with its own SQLite connection
- Each op is one `BEGIN IMMEDIATE` job lifecycle: enqueue `daemon_jobs` → mark running → insert `job_evidence` → mark done → touch `stories.stage` (`cost_entries` stays on the `_insert_cost_row` contract)
- Concurrent readers SELECT job/cost/story aggregates
- Writers use `synlynk.wal_ledger.ensure_wal_pragmas` + `write_transaction`
- After the burst: `PRAGMA integrity_check`, `wal_checkpoint(FULL)`, reopen, integrity again

Run via:

```
pytest tests/test_state_db_soak.py
synlynk testbed run --scenario state_db_wal
synlynk testbed soak --scenario state_db_wal --writers 50
```

## Pass thresholds

| Metric | Threshold |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| Recovery reopen + checkpoint | ok |
| `journal_mode` | `wal` |
| Lock failure rate | ≤ 1% |
| Starved writers (0 commits) | 0 |
| Committed writes | 100% of expected |
| p99 write latency | ≤ 5.0s |

Failure modes recorded when they occur: `lock_contention`, `corruption`, `write_starvation`, `lost_writes`, `not_wal`, `latency_budget`.

## Results

### 24 thread writers × 12 ops (288 transactions) + 8 readers

| Metric | Value |
|---|---|
| Duration | 0.218s |
| Committed / expected | 288 / 288 |
| Lock errors | 0 (rate 0.0) |
| Starved writers | 0 |
| Integrity / recovery | ok / ok |
| journal_mode | wal |
| p50 / p95 / p99 / max latency | 0.08ms / 26.6ms / 111.8ms / 165.6ms |
| Read ops | 772 |
| Verdict | PASSED |

### 50 thread writers × 8 ops (400 transactions) + 8 readers

| Metric | Value |
|---|---|
| Duration | 0.366s |
| Committed / expected | 400 / 400 |
| Lock errors | 0 (rate 0.0) |
| Starved writers | 0 |
| Integrity / recovery | ok / ok |
| journal_mode | wal |
| p50 / p95 / p99 / max latency | 0.07ms / 103.3ms / 165.7ms / 273.5ms |
| Read ops | 1280 |
| Verdict | PASSED |

### 20 process writers (pytest `executor="process"`)

Pytest `test_wal_soak_process_executor_twenty_writers` passed on this host (spawn pool, 20 workers, 5 ops each). Integrity stayed `ok` with zero lock errors.

Spawn cannot re-import `__main__` from a stdin/heredoc driver; run process-mode soaks via pytest or `python -m`. That is a test-harness caveat, not a ledger defect.

### Negative control (DELETE journal, busy_timeout=1ms, connect timeout 0.05s)

`test_soak_without_wal_or_busy_timeout_captures_lock_failures` records `lock_contention` and/or `write_starvation` instead of passing silently. The harness reports gaps when WAL/busy-timeout protection is removed.

## Reliability gaps

None found on this host for the WAL production path at 20–50 concurrent writers: no lock failures after `write_transaction` retries, no integrity failures, no starved writers, no lost commits.

This does not prove fleet-scale behavior on a contended NFS volume, a multi-host shared ledger, or a 7GB fragmented shard (#1831 / #1926). Those remain separate tracks.

## How to reproduce

```
python3 -m pytest tests/test_state_db_soak.py -v
```
