# state.db Consolidation — Migrations Framework + Legacy Shard Cleanup

**Status:** Design (pending user review)
**Author:** Claude (PM/review role), via superpowers:brainstorming
**Related issue:** gh:#1926 (architecture roadmap item #7, `docs/strategy/2026-10-02-decide-panel-roadmap.md` §1 row 7)
**Unblocks:** gh:#1993 (capability report generation)
**Depends on (both closed):** gh:#1921 (state+worktree GC), gh:#1924 (dispatch_agent decomposition)

## Provenance and Re-scoping

gh:#1926's original body calls for "single workspace-owner DB, DAO + unit-of-work
transactions, migrations; SQLite becomes canonical, Markdown becomes a verified
generated export." Investigation during brainstorming found that most of this is
already built:

- `synlynk/product_store.py` already implements a single canonical, slug-keyed
  workspace DB path (`~/.synlynk/workspaces/<slug>/state.db`), resolved from
  `.synlynk/config.json`'s `identity_slug`. `migrate_state_db_if_needed()`
  already does a one-time promotion of a legacy per-repo DB into this canonical
  path using SQLite's online backup API (not a raw file copy, to avoid WAL-mode
  corruption).
- `synlynk/doctor.py`'s `_hc_product_state_db_leftover()` and `synlynk/fleet.py`'s
  `find_nested_product_state_dbs()` already detect and refuse nested/stray
  product state.db files — guard rails for this architecture already exist.
- The Markdown generators (`_generate_costs_md`, `_write_memory_md`,
  `_generate_roadmap_md`, `_write_devlog_file`, `_write_decision_record_md` in
  `synlynk/db.py`) already read from SQLite and write Markdown as output — they
  are not a second source of truth today.
- A direct query against the canonical DB
  (`/Users/nikhilsoman/.synlynk/workspaces/synlynk/state.db`) confirmed
  `cost_entries` (1,806 rows) and `capability_ratings` (1,901 rows) are
  populated and actively written by live dispatches, including rows from
  the same day as this investigation (story-issue-2056/2063/2064/2068).
  `pr_review_cycles` is non-null on ~20% of `capability_ratings` rows — this
  reflects that most PRs haven't finished review yet, not a capture gap, and
  is not evidence of a schema or write-path problem.

**Conclusion:** the "single workspace-owner DB" and "Markdown as verified
export" halves of #1926 are already satisfied by existing code. A DAO/
unit-of-work layer has no second data source to coordinate transactions
around, so it is not being added speculatively (YAGNI). This spec narrows
#1926's remaining real scope to the two items below, per explicit user
approval during brainstorming.

## Scope

**In scope:**
1. Replace `synlynk/db.py`'s monolithic `_migrate_db()` (lines 877-980) with a
   versioned, per-step migrations framework.
2. A dry-run-then-delete cleanup script for the gh:#1831 legacy shard debris
   (`~/.synlynk/projects/<cwd-hash>/state.db`, 11,384 files, 6.1GB, confirmed
   inert — no active writes since 2026-09-15).

**Out of scope (explicitly not reproposing):**
- DAO / unit-of-work transaction layer.
- Any rearchitecture of Markdown generation — already generated-from-SQLite.
- Any change to `cost_entries` / `capability_ratings` schemas.

## Component 1: Migrations Framework

### Problem

`_migrate_db(conn)` in `synlynk/db.py:877-980` is a single function gated by
`PRAGMA user_version < _DB_MIGRATION_VERSION`. Every schema change is appended
to the same function body as another `conn.executescript(...)` block or a
try/except-guarded `ALTER TABLE ... ADD COLUMN`. There is no way to test one
migration step in isolation, no record of which migration applied at which
version, and the function grows without bound.

### Design

- **New package `synlynk/migrations/`.**
- `synlynk/migrations/__init__.py` defines:
  ```python
  @dataclass(frozen=True)
  class Migration:
      version: int
      name: str
      up: Callable[[sqlite3.Connection], None]
  ```
- Each migration is its own module, e.g. `synlynk/migrations/m0001_initial.py`,
  `synlynk/migrations/m0002_add_harness_column.py`. Each module defines a plain
  `def up(conn: sqlite3.Connection) -> None: ...` function and exports
  `MIGRATION = Migration(version=N, name="...", up=up)`.
- `synlynk/migrations/runner.py` defines `run_pending_migrations(conn)`:
  - Reads `PRAGMA user_version`.
  - Iterates a static, explicitly-imported registry list of `Migration` objects
    (no dynamic directory scanning — keeps the chain greppable and import-safe).
  - For each migration with `version > current_version`, in ascending order:
    runs `migration.up(conn)` inside its own transaction, commits, then sets
    `PRAGMA user_version = migration.version`.
  - A failure mid-migration leaves `user_version` at the last successfully
    applied step; re-running `run_pending_migrations` is always safe to retry
    (same idempotency guarantee the current guarded-ALTER pattern provides,
    now scoped per step instead of globally).
- **Audit trail:** migration 1 creates (if not already present) a
  `migration_history` table: `version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT`.
  The runner inserts a row after each successful migration. This is audit-only,
  not used for control flow (`PRAGMA user_version` remains the source of truth
  for what's pending) — it exists so "when did column X get added" is
  answerable without `git blame` archaeology.
- **Migration of existing code:** the current `_migrate_db` body is split
  mechanically into discrete numbered migrations along its existing logical
  blocks (initial table creation, the harness-rename migration, each per-table
  `ALTER TABLE` guard). This is a decomposition, not a behavior change — no
  migration's SQL content changes, only its packaging. `_migrate_db()` itself
  becomes a thin wrapper: `def _migrate_db(conn): run_pending_migrations(conn)`,
  preserving the existing call site so no other module needs to change.

### Testing

Each migration file gets a corresponding test that seeds an in-memory SQLite
DB at `user_version = version - 1` (via a shared test helper that runs all
prior migrations), calls `run_pending_migrations`, and asserts the resulting
schema (new tables/columns exist, old data is preserved). This is the direct
unlock this component provides: today, testing migration N requires running
the entire chain from version 0; after this change, each step is independently
testable.

## Component 2: gh:#1831 Legacy Shard Cleanup

### Target

`~/.synlynk/projects/<cwd-hash>/state.db` — 11,384 files, 6.1GB. gh:#1831's own
body confirms these are dead: no active writes since 2026-09-15, because the
CWD-hash-keyed project directory naming bug that created them is already fixed
by `product_store.py`'s slug-keyed canonical path.

### Script: `scripts/cleanup_legacy_project_shards.py`

A one-off remediation script (not installed as a `synlynk` subcommand — this
is a single-use cleanup, not a recurring operation).

1. **Scan:** glob `~/.synlynk/projects/*/state.db`, recording path, size in
   bytes, and `mtime` for each.
2. **Safety check per shard:** compare `mtime` against a cutoff date, default
   `2026-09-16` (one day after the confirmed-inert date in gh:#1831),
   overridable via `--cutoff-date YYYY-MM-DD`. Any shard with `mtime` at or
   after the cutoff is excluded from deletion and reported separately — this
   guards against the "confirmed inert" assumption being wrong for any single
   shard that turns out to have been touched more recently.
3. **Dry-run (default, no flag needed):** prints a summary — total shard
   count, total bytes, oldest/newest mtime among scanned shards — and writes
   the full candidate-for-deletion file list to a report file. No filesystem
   mutation occurs in this mode.
4. **`--execute`:** required to actually delete. Deletes only shards that
   passed the mtime safety check in step 2. Shards skipped by the safety check
   are never deleted by this script, regardless of `--execute`.
5. **Final report (both modes):** count and total bytes that would be/were
   freed, count and list of shards skipped by the safety check with reasons.

No archival step is used here: the Archive-Before-Branch-Removal standing
policy applies to branches/worktrees carrying unmerged work; these are dead
cache shards with no active writes for three weeks, confirmed by #1831 itself,
not in-progress work.

## Non-Goals / Explicitly Deferred

- Rebuilding `cost_entries`/`capability_ratings` write paths — confirmed
  healthy via direct query during this brainstorm; no issue found.
- A `synlynk capability report` command itself — that's gh:#1993's scope, and
  remains blocked on this spec landing (its own stated dependency).
- Any change to the canonical-path resolution logic in `product_store.py` —
  already correct; not touched by this spec.
- **Tokq bridge convergence.** The existing `tokq-bridge.md` memory/spec
  (decided 2026-06-06, `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md`
  §3.1/§3.2) defines a `capability` memory-unit type sourced directly from
  this same capability-ratings data, opt-in-publishable to the Tokq
  marketplace once Tokq Alpha reactivates. That is a distinct, unstarted
  product integration — not a dependency of this spec and not something this
  spec adds code for. The only implication for this spec: once the
  migrations framework in Component 1 touches the `capability_ratings`
  table's schema, treat its current shape (columns, meaning of `agent`,
  `model_version`, `quality`, etc.) as a stable public contract, since it is
  the seed of that future attestation ledger — don't rename/restructure
  those columns casually in a later migration without checking
  `tokq-bridge.md`'s Gap 2 mapping first.

## Testing Plan (summary)

- Migrations: per-migration unit test seeded at `version - 1`, asserting
  resulting schema (see Component 1 Testing above).
- Cleanup script: unit tests using a temp directory populated with fake shard
  files at varying mtimes, asserting dry-run reports counts/bytes correctly
  and leaves files untouched, and that `--execute` deletes only shards older
  than the cutoff while leaving newer ones in place.
