# SQLite WAL Soak Test — Design Spec

**Date:** 2026-10-11
**Issue:** gh:#2102 (P1, three-lens review P1-4)
**Story:** story-issue-2102
**Goal:** goal-adb60ccc (pillar 3 — fleet analytics / safe fleet scaling)

## Problem

No representative soak test exists showing `state.db` (SQLite WAL) stays reliable under 20–50 concurrent writers, the load level the dev-preview roadmap's Week 2-4 dispatch-wave volume will approach.

## Approach

A standalone pytest-marked soak test (`tests/soak/test_state_db_concurrent_writers.py`, run opt-in via `-m soak`, not in the default suite) that:

1. Creates an isolated temp SQLite DB (via `tempfile.mkdtemp()`), applies the project's real schema/migrations (reuse `synlynk.state_db` or equivalent migration entrypoint — whatever #1926's consolidated module exposes), never touches the real workspace `state.db`.
2. Spawns N worker threads/processes (parametrized 20 and 50) each performing a realistic mixed workload: insert a `cost_entries` row, insert/update a `capability_ratings` row, update a `daemon_jobs` row — mirroring real dispatch-cycle writes — in a loop for a fixed duration (e.g. 10s) or fixed iteration count.
3. Each worker records: attempt count, success count, `sqlite3.OperationalError` (lock/busy) count, and per-write latency.
4. After the run: verify DB integrity via `PRAGMA integrity_check`, assert no data corruption (row counts match expected), and assert the lock-failure rate is below a defined threshold (e.g. <1% with retry, 0% uncaught after WAL busy_timeout).
5. Emit a JSON report (`tests/soak/reports/<timestamp>-soak-report.json`) with the latency/failure stats — this is the "reproducible report" acceptance criterion, kept out of git (gitignored reports dir) but printed to stdout in CI/local runs too.

## Pass thresholds

- Zero DB integrity failures.
- Zero unrecoverable lock errors (a retry-with-backoff wrapper around writes is expected and acceptable; an error that survives 5 retries at increasing backoff is a failure).
- p95 write latency documented in the report (informational, not a hard gate — this is a baseline-establishing test, not a performance regression gate yet).

## Testing

The soak test *is* the deliverable — it has no separate "test of the test" beyond running it at both N=20 and N=50 and confirming it passes and produces a report. Mark it `@pytest.mark.soak` and exclude it from the default `pytest` invocation (add `soak` to any marker-exclusion config already used for slow/integration tests, following whatever pattern the project already uses for similar opt-in suites).

## Out of scope

- No changes to production `state.db` schema or write paths.
- No CI wiring to run this on every push (soak tests are opt-in/manual or nightly — add a comment noting that if/when CI integration is wanted, it's a separate follow-up, not this issue).
