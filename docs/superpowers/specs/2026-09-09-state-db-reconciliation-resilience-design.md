# State DB Selection and Reconciliation Resilience (#1525)

**Status:** Implemented on the Codex task branch

## Decision

Automatic state-DB selection must validate write capability before returning a
connection. The validation uses `BEGIN IMMEDIATE` followed by `ROLLBACK`, so a
readable but inaccessible or read-only central database is rejected without
changing application data and the existing writable local fallback is tried.
An explicit `SYNLYNK_STATE_DB_PATH` remains authoritative and fail-fast.

The effective path is observable through `get_state_db_path()` and the
fallback warning. The configured canonical path is not overwritten, so later
diagnostics can distinguish intent from the path actually selected.

Reconciliation treats cost/telemetry and capability-rating writes as
best-effort per-job persistence. Failures are converted into structured
Sentinel alerts, with data-integrity failures retaining critical visibility;
the remaining job and command continue. Flat-file job reconciliation is locked
across concurrent callers to prevent lost updates.

## Non-goals

- No repair, migration, deletion, or replacement of live state databases or
  their WAL/SHM files.
- No silent fallback when an explicit override fails.
- No suppression of data-integrity failures; they remain Sentinel-visible.

## Verification

Focused tests cover inaccessible/read-only central state, writable fallback,
explicit override precedence, persistence failure isolation, continued job
operation, and concurrent reconciliation.
