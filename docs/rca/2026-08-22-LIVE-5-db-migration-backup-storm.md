# [LIVE-5] `_migrate_db()` copies the entire state DB on every connection, causing disk bloat and lock contention

**Date:** 2026-08-22
**Severity:** Sev1 — core product commands (`probe`, `dispatch`, `pr check`, and by extension any command opening the project state DB) intermittently fail with `sqlite3.OperationalError: database is locked`, with no workaround short of retrying
**Source:** Discovered by Claude (PM/review session) while diagnosing why `synlynk dispatch`/`synlynk pr check` were failing on `nikhilsoman/synlynk`'s own primary state DB during the qa-gate merge-gate-authority rollout (PR #1079, #1084)
**Status:** Root cause confirmed. Immediate symptoms locally remediated (see Remediation). Code fix not yet implemented (pending dispatch).

## Impact

Every `synlynk` command that opens the project state DB (`~/.synlynk/projects/<hash>/state.db`) — which is effectively all stateful commands: `probe`, `dispatch`, `pr check`, `jobs`, `status`, etc. — triggers `_migrate_db()` on connection. `_migrate_db()` unconditionally makes a full on-disk copy (`shutil.copy2`) of the state DB before running its (idempotent) schema statements, regardless of whether any schema change is actually pending.

On this machine, this produced **384 backup files totaling 1.8GB** in `~/.synlynk/projects/13267207/`, with timestamps spanning 2026-08-19 through 2026-08-21, several bursts only 5-6 seconds apart. During a `synlynk probe --harness grok` run (which internally dispatches a calibration-sweep sub-task, opening additional concurrent connections), the repeated concurrent `shutil.copy2()` + write activity produced:

```
sqlite3.OperationalError: database is locked
  File ".../synlynk/db.py", line 348, in _migrate_db
    conn.execute("UPDATE stories SET discipline = ... ")
```

This blocked `synlynk dispatch grok --base main` (Task 4 of the qa-gate merge-gate-authority stacked-PR sequence, docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md) at its preflight probe-data check, and separately blocked `synlynk pr check` outright.

A secondary, distinct bug compounded this: `_run_harness_rename_migration()` (`synlynk/db.py:293-298`) guards the `agent_reservations` → `harness_reservations` rename only on the *source* table existing, never checking whether the *destination* already exists. Something re-creates an empty `agent_reservations` table after a successful rename (likely `conn.executescript(_DB_SCHEMA)` at `db.py:318`, which runs immediately after the rename migration and appears to still declare `agent_reservations`), so the next connection's migration attempt collides:

```
sqlite3.OperationalError: there is already another table or index with this name: harness_reservations
```

This second bug is what first surfaced (`synlynk pr check`, `synlynk dispatch` preflight) before the backup-storm issue was found underneath it.

## Root cause

1. `_migrate_db()` (`synlynk/db.py:313-316`) calls `_snapshot_before_migration(conn)` unconditionally as its first line, on every single call:
   ```python
   def _migrate_db(conn: sqlite3.Connection) -> None:
       """Idempotent schema migrations. Adds tables/views if absent."""
       _snapshot_before_migration(conn)
       _run_harness_rename_migration(conn)
       ...
   ```
2. `_snapshot_before_migration()` (`db.py:301-310`) has no gate on whether a schema change is actually about to happen — it unconditionally `shutil.copy2()`s the entire DB file (skipping only trivial/empty DBs `<= 4096` bytes) and writes a uniquely-timestamped `.pre-migration-<ISO8601>.bak` file:
   ```python
   def _snapshot_before_migration(conn: sqlite3.Connection) -> str | None:
       """Copy a non-trivial on-disk DB before migration can alter its schema."""
       ...
       stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
       backup_path = f"{db_path}.pre-migration-{stamp}.bak"
       shutil.copy2(db_path, backup_path)
       return backup_path
   ```
3. `_migrate_db()` is called from `_get_db()` (`synlynk/__init__.py:1224`) on every new connection — i.e. on every CLI invocation, and on every sub-connection opened internally (e.g. `probe`'s calibration sweep dispatching a nested `dispatch_agent()` call, `synlynk/dispatch.py:2216`, which opens its own connection via `get_db_fn()`).
4. Because the snapshot step is unconditional rather than gated on "a migration is about to make a change," every command run — not just the first run after an upgrade — pays a full multi-MB file copy, and concurrent/rapid connections (as happens inside `probe`'s internal sub-dispatch) race on copying + writing the same source file, producing the `database is locked` failures.
5. Separately, `_run_harness_rename_migration()` (`db.py:293-298`) is not idempotent against its own destination table, causing the secondary `harness_reservations already exists` collision described above once `agent_reservations` gets re-created empty by the schema script that runs immediately after it in the same `_migrate_db()` call.

## Remediation (this session, local machine only)

- Diagnosed via direct `sqlite3` inspection of `~/.synlynk/projects/13267207/state.db`: confirmed `harness_reservations` held the correct current schema and all 276 real rows; `agent_reservations` was a stale, empty (0-row) duplicate.
- Dropped the empty stale `agent_reservations` table directly (data-only repair, not application code; explicit user approval obtained given it's a destructive operation on the shared state store).
- Archived (not deleted) all 384 `state.db.pre-migration-*.bak` files (1.8GB) into a dated subfolder `stale-migration-backups-archive-20260821T200443Z/` within the same project state directory, to stop ongoing lock contention while preserving them for audit/rollback if needed.
- This unblocks commands on this machine but does **not** fix the underlying code — the next connection after any real schema change (or possibly every connection, pending further read of `_snapshot_before_migration`'s trivia-size gate) will resume writing fresh `.bak` files and could re-hit the same lock contention under concurrent connections.

## Action items (not yet dispatched)

1. **Gate `_snapshot_before_migration()` on an actual pending change**, not unconditional-per-connection. E.g. compute/compare a schema version or hash before copying, or only snapshot once per process/session rather than once per connection.
2. **Fix `_run_harness_rename_migration()` idempotency**: guard the rename on `not _table_exists(conn, "harness_reservations")` in addition to the existing `_table_exists(conn, "agent_reservations")` check.
3. **Investigate why `agent_reservations` gets re-created after a successful rename** — likely `_DB_SCHEMA` in `synlynk/__init__.py` still declares `CREATE TABLE IF NOT EXISTS agent_reservations`, which should be removed/updated now that the canonical name is `harness_reservations`.
4. Add a retention/cleanup policy for `.pre-migration-*.bak` files (e.g. keep last N, or only snapshot before migrations that actually run a destructive `ALTER`/`DROP`) so this cannot recur even after the above fixes, in case some future migration path re-introduces frequent snapshotting.
5. Add a regression test asserting `_migrate_db()` run twice in a row on the same connection/DB produces zero additional `.bak` files and no errors (idempotency test), to catch this class of bug before it reaches production dev environments again.

## Prevention

The `_migrate_db()` docstring already claims "Idempotent schema migrations" — the actual code was idempotent for schema *changes* but not for the *side effect* of the snapshot step, which is a distinct property that wasn't tested. Future migration-related PRs should explicitly test "run the full migration path N times on an already-migrated DB, assert no errors and no unbounded side effects (files, rows, locks)," not just "schema ends up correct."
