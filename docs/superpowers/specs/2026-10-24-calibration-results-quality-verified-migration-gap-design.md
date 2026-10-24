# gh:#2569 — `capability_calibration_results.quality_verified` migration gap

**Status:** Approved pending Nikhil sign-off (small, bounded, already-scoped fix; root cause fully diagnosed — scaled down per the #2332 precedent for well-understood bug fixes).

## Problem

`capability_calibration_results.quality_verified` (added by #2171/#2172 for gh:#2170) is added inside `_run_legacy_migration_and_repairs()` (`synlynk/db.py:1694-1698`), which is gated by `migration_version < _DB_MIGRATION_VERSION` (`_DB_MIGRATION_VERSION = 15`). The canonical production `state.db` is already at `user_version = 28`, so this block — and the new column — never runs there. Confirmed today via a crashed capability-sweep attempt (`sqlite3.OperationalError: table capability_calibration_results has no column named quality_verified`).

The sibling column `capability_ratings.quality_verified`, added by the same PRs, correctly uses the unconditional `_add_column_if_missing()` repair at `synlynk/db.py:2338-2343`, outside the version gate. `capability_calibration_results` needed the identical treatment and didn't get it.

## Fix

Add one more unconditional repair call, directly beside the existing `capability_ratings` one:

```python
_add_column_if_missing(
    conn,
    table="capability_calibration_results",
    column="quality_verified",
    definition="INTEGER",
)
```

Location: `synlynk/db.py`, immediately after the existing block at line ~2343 (before `_migrate_onboarding_sessions(conn)`).

No change to the legacy-gated ALTER at line 1694-1698 — leave it for genuinely fresh/pre-v15 databases. This only adds the missing repair for already-migrated ones.

## Test

Add a regression test mirroring the existing coverage for `turn_usage_json`/`capability_ratings`: construct a DB connection with `user_version` already >= `_DB_MIGRATION_VERSION`, missing the `quality_verified` column on `capability_calibration_results`, run migration, assert the column now exists.

## Out of scope

- Does not touch gh:#2170's own remaining root-cause/backfill items — this is a distinct migration-placement bug, not the verifier-parsing issue #2170 was about.
- Does not re-run the interrupted grok/grok-4.7 sweep — that's a separate follow-up once this merges.
