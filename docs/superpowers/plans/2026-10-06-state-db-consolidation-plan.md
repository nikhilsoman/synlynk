# state.db Consolidation — Migrations Framework + Legacy Shard Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `synlynk/db.py`'s unbounded, untestable `_migrate_db()` with a versioned migrations framework usable for all future schema changes, and ship a safe dry-run-then-delete cleanup script for the 11,384 dead legacy per-project `state.db` shards from gh:#1831.

**Architecture:** Two independent components, each landing as its own commit sequence and dispatchable separately.

- **Component 1 (migrations framework):** New `synlynk/migrations/` package with a `Migration` dataclass, a `run_pending_migrations(conn)` runner driven by `PRAGMA user_version`, and a `migration_history` audit table. **Deviation from the design spec's literal wording, decided during planning:** the spec called for "mechanically splitting the existing monolithic `_migrate_db` body into discrete numbered migrations along its existing logical blocks." Investigation while writing this plan found that body is ~1072 lines (`synlynk/db.py:877-1968`), not ~100 as originally estimated, and it is not a clean linear sequence — it has an `if/else` branch (the `else` arm runs `_migrate_governs_tenancy`/`_normalize_org_domain_drift` when a DB is already at the current version) plus unconditional post-gate repair logic (`cost_entries.turn_usage_json` backfill, `_migrate_onboarding_sessions`) that always runs regardless of version. Retyping or hand-splitting that body into 15 separate files risks silent transcription errors with no way to diff-verify correctness. Instead: the existing function is **renamed in place** to `_run_legacy_migration_and_repairs` (a pure rename, zero behavior change, mechanically verifiable via `git diff` showing only the `def` line changed), and `_migrate_db()` becomes a 3-line wrapper that calls the renamed legacy function followed by `run_pending_migrations(conn)`. Versions 1-15 remain permanently owned by the legacy function; the new framework governs only future migrations (version 16+), which is exactly where the "each step independently testable" benefit actually matters going forward. No existing test changes behavior or assertions.
- **Component 2 (shard cleanup):** Standalone `scripts/cleanup_legacy_project_shards.py`, no dependency on Component 1 or on `synlynk/db.py` internals — pure filesystem scan/report/delete over `~/.synlynk/projects/*/state.db`.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `dataclasses`, `pathlib`, `argparse`, `glob`, `os`) — matches the project's existing zero-dependency constraint. `pytest` for tests, matching existing `tests/test_db_migration.py` conventions.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/migrations/__init__.py` | Defines the `Migration` dataclass. Nothing else — kept minimal so it's safe to import from anywhere without pulling in sqlite3 call machinery. |
| `synlynk/migrations/runner.py` | Defines `MIGRATIONS: list[Migration]` (the static registry, empty until a real v16+ migration is ever added) and `run_pending_migrations(conn)`, which creates `migration_history` if absent, reads `PRAGMA user_version`, and applies any registered migration with `version > current_version` in ascending order. |
| `synlynk/db.py` (modified) | Rename `_migrate_db` → `_run_legacy_migration_and_repairs` at line 877. Add new `_migrate_db(conn)` wrapper immediately after it. Add one import line near the top: `from synlynk.migrations.runner import run_pending_migrations`. |
| `tests/test_migrations_framework.py` | New tests for the `Migration` dataclass and `run_pending_migrations` runner, using a synthetic in-test migration (never touches the real `MIGRATIONS` registry or real schema). |
| `tests/test_db_migration.py` (modified) | Add one new test confirming `_migrate_db` still produces a working, current-version DB post-rename (regression guard for the Component 1 change), and that `migration_history` exists afterward. |
| `scripts/cleanup_legacy_project_shards.py` | Standalone CLI script: scan, safety-check, dry-run report, `--execute` delete. |
| `tests/test_cleanup_legacy_project_shards.py` | Tests using `tmp_path` with fake shard files at varying `mtime`s. |

---

## Component 1: Migrations Framework

### Task 1: `Migration` dataclass

**Files:**
- Create: `synlynk/migrations/__init__.py`
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrations_framework.py
def test_migration_dataclass_has_expected_fields():
    from synlynk.migrations import Migration

    def up(conn):
        pass

    m = Migration(version=16, name="example", up=up)
    assert m.version == 16
    assert m.name == "example"
    assert m.up is up
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_framework.py::test_migration_dataclass_has_expected_fields -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/migrations/__init__.py
"""Versioned schema-migration framework for synlynk's state.db.

Migrations numbered 1-15 are owned by the legacy consolidated migration in
synlynk/db.py (`_run_legacy_migration_and_repairs`), preserved verbatim for
safety. This package governs migration 16 onward.
"""
from dataclasses import dataclass
from typing import Callable
import sqlite3


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrations_framework.py::test_migration_dataclass_has_expected_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/__init__.py tests/test_migrations_framework.py
git commit -m "feat(migrations): add Migration dataclass"
```

### Task 2: `run_pending_migrations` runner — empty registry case

**Files:**
- Create: `synlynk/migrations/runner.py`
- Test: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrations_framework.py (append)
def test_run_pending_migrations_creates_history_table_when_registry_empty(tmp_path):
    import sqlite3
    from synlynk.migrations.runner import run_pending_migrations

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 15")
    run_pending_migrations(conn)

    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    assert row is not None
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 15
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_framework.py::test_run_pending_migrations_creates_history_table_when_registry_empty -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/migrations/runner.py
"""Runner for versioned migrations numbered 16 and above.

Versions 1-15 are applied by synlynk.db._run_legacy_migration_and_repairs
before this runner is ever called — see synlynk/migrations/__init__.py.
"""
import sqlite3
from datetime import datetime, timezone

from synlynk.migrations import Migration

# Static, explicitly-imported registry. Append future Migration entries here
# in ascending version order — no dynamic directory scanning.
MIGRATIONS: list[Migration] = []


def _ensure_migration_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS migration_history (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )


def run_pending_migrations(conn: sqlite3.Connection) -> None:
    _ensure_migration_history_table(conn)
    conn.commit()

    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    pending = sorted(
        (m for m in MIGRATIONS if m.version > current_version),
        key=lambda m: m.version,
    )
    for migration in pending:
        migration.up(conn)
        conn.execute(f"PRAGMA user_version = {migration.version}")
        conn.execute(
            "INSERT INTO migration_history (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrations_framework.py::test_run_pending_migrations_creates_history_table_when_registry_empty -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat(migrations): add run_pending_migrations runner with empty registry"
```

### Task 3: `run_pending_migrations` — applies a pending migration and is retry-safe

**Files:**
- Modify: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrations_framework.py (append)
def test_run_pending_migrations_applies_pending_migration_in_order(tmp_path, monkeypatch):
    import sqlite3
    from synlynk.migrations import Migration
    from synlynk.migrations import runner

    applied = []

    def up_16(conn):
        conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY)")
        applied.append(16)

    def up_17(conn):
        conn.execute("ALTER TABLE widgets ADD COLUMN name TEXT")
        applied.append(17)

    monkeypatch.setattr(
        runner,
        "MIGRATIONS",
        [
            Migration(version=17, name="add_widgets_name", up=up_17),
            Migration(version=16, name="create_widgets", up=up_16),
        ],
    )

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute("PRAGMA user_version = 15")
    runner.run_pending_migrations(conn)

    assert applied == [16, 17]
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 17
    cols = {row[1] for row in conn.execute("PRAGMA table_info(widgets)")}
    assert cols == {"id", "name"}
    history = conn.execute(
        "SELECT version, name FROM migration_history ORDER BY version"
    ).fetchall()
    assert history == [(16, "create_widgets"), (17, "add_widgets_name")]

    # Re-running is a no-op (retry-safety).
    runner.run_pending_migrations(conn)
    assert applied == [16, 17]
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations_framework.py::test_run_pending_migrations_applies_pending_migration_in_order -v`
Expected: FAIL — `assert applied == [16, 17]` fails because `MIGRATIONS` was empty before monkeypatch took effect, or ordering assertion fails if sort-by-version isn't applied. (If Task 2's implementation is correct, this should actually PASS already since sorting by version is already implemented — this step exists to prove the behavior with explicit out-of-order registry input, not to drive new code.)

- [ ] **Step 3: Confirm implementation already satisfies this** (no code change expected)

The `runner.py` from Task 2 already sorts `pending` by `m.version` and only applies `version > current_version`, which is retry-safe since after the first run `current_version == 17` and nothing in `MIGRATIONS` has `version > 17`. If this test fails, re-check Task 2's `run_pending_migrations` for an ordering or filter bug before changing anything else.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrations_framework.py::test_run_pending_migrations_applies_pending_migration_in_order -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_migrations_framework.py
git commit -m "test(migrations): verify ordering and retry-safety of run_pending_migrations"
```

### Task 4: Rename `_migrate_db` to `_run_legacy_migration_and_repairs`, add thin wrapper

**Files:**
- Modify: `synlynk/db.py:877`
- Modify: `tests/test_db_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_migration.py (append)
def test_migrate_db_delegates_to_legacy_function_and_runner(tmp_path, monkeypatch):
    """Regression guard for the Component 1 rename: _migrate_db must still
    bring a fresh DB to the current version AND leave a migration_history
    table behind (proof run_pending_migrations actually ran)."""
    import sqlite3
    from synlynk import db

    db_path = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    conn = db._get_db()

    assert conn.execute("PRAGMA user_version").fetchone()[0] == db._DB_MIGRATION_VERSION
    history_row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    assert history_row is not None
    assert hasattr(db, "_run_legacy_migration_and_repairs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_migration.py::test_migrate_db_delegates_to_legacy_function_and_runner -v`
Expected: FAIL with `AttributeError: module 'synlynk.db' has no attribute '_run_legacy_migration_and_repairs'`

- [ ] **Step 3: Rename the function and add the wrapper**

In `synlynk/db.py`, at line 877, change:

```python
def _migrate_db(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    migration_version = conn.execute("PRAGMA user_version").fetchone()[0]
```

to:

```python
def _run_legacy_migration_and_repairs(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations for versions 1-15. Adds tables/views if
    absent. Frozen in place — see synlynk/migrations/ for version 16+."""
    migration_version = conn.execute("PRAGMA user_version").fetchone()[0]
```

**Do not touch any other line inside the function body** (lines 878-1968 stay byte-for-byte identical). Then, immediately after the function's closing (after line 1968, before the blank line at 1969), insert:

```python


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Thin entry point: legacy versions 1-15, then the versioned runner
    for version 16+. See synlynk/migrations/runner.py."""
    _run_legacy_migration_and_repairs(conn)
    run_pending_migrations(conn)
```

Add the import near the top of `synlynk/db.py`, alongside the other `from synlynk...` imports already present in the file (search for `^import sqlite3` or the existing top-level import block and add this line next to it):

```python
from synlynk.migrations.runner import run_pending_migrations
```

- [ ] **Step 4: Verify the rename introduced no body changes**

Run: `git diff synlynk/db.py`
Expected: the diff shows exactly one changed `def` line (plus its docstring), one new import line, and one new 6-line function appended after the renamed function's closing line. No other line in the old function body appears in the diff. If any other line shows as changed, revert and redo Step 3 more carefully — this must be a pure rename, not a rewrite.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_db_migration.py::test_migrate_db_delegates_to_legacy_function_and_runner -v`
Expected: PASS

- [ ] **Step 6: Run the full existing migration test suite to confirm no regression**

Run: `pytest tests/test_db_migration.py tests/test_migrate.py tests/test_cycle_migration.py tests/test_onboarding_db_migration.py -v`
Expected: all PASS, unchanged from before this task (these tests call `db._migrate_db(conn)` by name, which still exists and still produces identical end-state behavior).

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py tests/test_db_migration.py
git commit -m "refactor(db): rename _migrate_db to _run_legacy_migration_and_repairs, add versioned-runner wrapper"
```

---

## Component 2: gh:#1831 Legacy Shard Cleanup

### Task 5: Scan and safety-check logic

**Files:**
- Create: `scripts/cleanup_legacy_project_shards.py`
- Test: `tests/test_cleanup_legacy_project_shards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cleanup_legacy_project_shards.py
import os
import time


def _touch_with_mtime(path, mtime_ts):
    path.write_text("not a real sqlite file, just needs to exist")
    os.utime(path, (mtime_ts, mtime_ts))


def test_scan_shards_finds_all_state_db_files(tmp_path):
    from scripts.cleanup_legacy_project_shards import scan_shards

    projects_root = tmp_path / "projects"
    (projects_root / "abc123").mkdir(parents=True)
    (projects_root / "def456").mkdir(parents=True)
    _touch_with_mtime(projects_root / "abc123" / "state.db", time.time() - 86400)
    _touch_with_mtime(projects_root / "def456" / "state.db", time.time() - 86400)

    shards = scan_shards(projects_root)

    assert len(shards) == 2
    assert {s.path.parent.name for s in shards} == {"abc123", "def456"}


def test_is_safe_to_delete_rejects_shards_newer_than_cutoff(tmp_path):
    from scripts.cleanup_legacy_project_shards import is_safe_to_delete
    from datetime import date

    old_path = tmp_path / "old_state.db"
    _touch_with_mtime(old_path, time.mktime(date(2026, 9, 1).timetuple()))

    new_path = tmp_path / "new_state.db"
    _touch_with_mtime(new_path, time.mktime(date(2026, 9, 20).timetuple()))

    cutoff = date(2026, 9, 16)

    assert is_safe_to_delete(old_path, cutoff) is True
    assert is_safe_to_delete(new_path, cutoff) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup_legacy_project_shards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.cleanup_legacy_project_shards'`

- [ ] **Step 3: Write minimal implementation (scan + safety check only)**

```python
# scripts/cleanup_legacy_project_shards.py
"""One-off remediation for gh:#1831: delete dead legacy per-project state.db
shards under ~/.synlynk/projects/*/state.db. These predate product_store.py's
slug-keyed canonical DB path and have had no active writes since 2026-09-15
(confirmed in gh:#1831). Not installed as a synlynk subcommand — single-use.

Usage:
    python3 scripts/cleanup_legacy_project_shards.py                 # dry run
    python3 scripts/cleanup_legacy_project_shards.py --execute        # delete
    python3 scripts/cleanup_legacy_project_shards.py --cutoff-date 2026-09-20
"""
import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DEFAULT_CUTOFF_DATE = date(2026, 9, 16)
DEFAULT_PROJECTS_ROOT = Path.home() / ".synlynk" / "projects"


@dataclass
class Shard:
    path: Path
    size_bytes: int
    mtime: datetime


def scan_shards(projects_root: Path) -> list[Shard]:
    shards = []
    for db_path in projects_root.glob("*/state.db"):
        stat = db_path.stat()
        shards.append(
            Shard(
                path=db_path,
                size_bytes=stat.st_size,
                mtime=datetime.fromtimestamp(stat.st_mtime),
            )
        )
    return shards


def is_safe_to_delete(path: Path, cutoff: date) -> bool:
    mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
    return mtime < cutoff
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup_legacy_project_shards.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/cleanup_legacy_project_shards.py tests/test_cleanup_legacy_project_shards.py
git commit -m "feat(cleanup): scan legacy shards and apply mtime safety check"
```

### Task 6: Dry-run report (default mode, no mutation)

**Files:**
- Modify: `scripts/cleanup_legacy_project_shards.py`
- Modify: `tests/test_cleanup_legacy_project_shards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cleanup_legacy_project_shards.py (append)
from datetime import date


def test_dry_run_reports_counts_and_leaves_files_untouched(tmp_path, capsys):
    from scripts.cleanup_legacy_project_shards import run_cleanup

    projects_root = tmp_path / "projects"
    (projects_root / "old1").mkdir(parents=True)
    (projects_root / "old2").mkdir(parents=True)
    (projects_root / "recent").mkdir(parents=True)
    _touch_with_mtime(projects_root / "old1" / "state.db", time.mktime(date(2026, 8, 1).timetuple()))
    _touch_with_mtime(projects_root / "old2" / "state.db", time.mktime(date(2026, 8, 15).timetuple()))
    _touch_with_mtime(projects_root / "recent" / "state.db", time.mktime(date(2026, 9, 20).timetuple()))

    report_path = tmp_path / "report.txt"
    result = run_cleanup(
        projects_root=projects_root,
        cutoff=date(2026, 9, 16),
        execute=False,
        report_path=report_path,
    )

    assert result.deletable_count == 2
    assert result.skipped_count == 1
    assert result.deleted_count == 0
    assert (projects_root / "old1" / "state.db").exists()
    assert (projects_root / "old2" / "state.db").exists()
    assert (projects_root / "recent" / "state.db").exists()
    assert report_path.exists()
    report_text = report_path.read_text()
    assert "old1" in report_text
    assert "old2" in report_text
    assert "recent" in report_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup_legacy_project_shards.py::test_dry_run_reports_counts_and_leaves_files_untouched -v`
Expected: FAIL with `ImportError: cannot import name 'run_cleanup'`

- [ ] **Step 3: Implement `run_cleanup`**

Append to `scripts/cleanup_legacy_project_shards.py`:

```python
@dataclass
class CleanupResult:
    deletable_count: int
    deletable_bytes: int
    skipped_count: int
    deleted_count: int
    deleted_bytes: int


def run_cleanup(
    projects_root: Path,
    cutoff: date,
    execute: bool,
    report_path: Path,
) -> CleanupResult:
    shards = scan_shards(projects_root)
    deletable = [s for s in shards if is_safe_to_delete(s.path, cutoff)]
    skipped = [s for s in shards if not is_safe_to_delete(s.path, cutoff)]

    deleted_count = 0
    deleted_bytes = 0
    if execute:
        for shard in deletable:
            shard.path.unlink()
            deleted_count += 1
            deleted_bytes += shard.size_bytes

    lines = [
        f"Legacy shard cleanup report ({'EXECUTED' if execute else 'DRY RUN'})",
        f"Cutoff date: {cutoff.isoformat()}",
        f"Scanned: {len(shards)} shard(s)",
        "",
        f"Deletable ({'deleted' if execute else 'would delete'}): "
        f"{len(deletable)} shard(s), {sum(s.size_bytes for s in deletable)} bytes",
    ]
    for shard in deletable:
        lines.append(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)")
    lines.append("")
    lines.append(f"Skipped (newer than cutoff, never deleted by this script): {len(skipped)} shard(s)")
    for shard in skipped:
        lines.append(f"  {shard.path} (mtime={shard.mtime.isoformat()}, {shard.size_bytes} bytes)")

    report_path.write_text("\n".join(lines) + "\n")

    return CleanupResult(
        deletable_count=len(deletable),
        deletable_bytes=sum(s.size_bytes for s in deletable),
        skipped_count=len(skipped),
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup_legacy_project_shards.py::test_dry_run_reports_counts_and_leaves_files_untouched -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/cleanup_legacy_project_shards.py tests/test_cleanup_legacy_project_shards.py
git commit -m "feat(cleanup): add dry-run report generation"
```

### Task 7: `--execute` actually deletes only safe shards

**Files:**
- Modify: `tests/test_cleanup_legacy_project_shards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cleanup_legacy_project_shards.py (append)
def test_execute_deletes_only_shards_older_than_cutoff(tmp_path):
    from scripts.cleanup_legacy_project_shards import run_cleanup

    projects_root = tmp_path / "projects"
    (projects_root / "old1").mkdir(parents=True)
    (projects_root / "recent").mkdir(parents=True)
    old_path = projects_root / "old1" / "state.db"
    recent_path = projects_root / "recent" / "state.db"
    _touch_with_mtime(old_path, time.mktime(date(2026, 8, 1).timetuple()))
    _touch_with_mtime(recent_path, time.mktime(date(2026, 9, 20).timetuple()))

    report_path = tmp_path / "report.txt"
    result = run_cleanup(
        projects_root=projects_root,
        cutoff=date(2026, 9, 16),
        execute=True,
        report_path=report_path,
    )

    assert result.deleted_count == 1
    assert not old_path.exists()
    assert recent_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup_legacy_project_shards.py::test_execute_deletes_only_shards_older_than_cutoff -v`
Expected: PASS already — Task 6's `run_cleanup` implementation already handles `execute=True` correctly. If it fails, the bug is in the `if execute:` block added in Task 6; fix there before proceeding.

- [ ] **Step 3: Confirm, no code change expected**

Re-read `run_cleanup` from Task 6: the `if execute:` branch only iterates `deletable` (already filtered by `is_safe_to_delete`), so `recent_path` is never a candidate. This test exists to pin that guarantee with an explicit regression test, not to drive new code.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup_legacy_project_shards.py::test_execute_deletes_only_shards_older_than_cutoff -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cleanup_legacy_project_shards.py
git commit -m "test(cleanup): pin --execute deletes only shards older than cutoff"
```

### Task 8: CLI entry point (`argparse` wiring + `main()`)

**Files:**
- Modify: `scripts/cleanup_legacy_project_shards.py`
- Modify: `tests/test_cleanup_legacy_project_shards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cleanup_legacy_project_shards.py (append)
def test_parse_args_defaults():
    from scripts.cleanup_legacy_project_shards import parse_args

    args = parse_args([])
    assert args.execute is False
    assert args.cutoff_date == date(2026, 9, 16)
    assert args.projects_root == Path.home() / ".synlynk" / "projects"


def test_parse_args_overrides():
    from scripts.cleanup_legacy_project_shards import parse_args

    args = parse_args(["--execute", "--cutoff-date", "2026-10-01"])
    assert args.execute is True
    assert args.cutoff_date == date(2026, 10, 1)
```

Add `from pathlib import Path` to the test file's imports if not already present (it is, via the dataclass import in Task 5 — verify before adding a duplicate).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cleanup_legacy_project_shards.py::test_parse_args_defaults -v`
Expected: FAIL with `ImportError: cannot import name 'parse_args'`

- [ ] **Step 3: Implement `parse_args` and `main`**

Append to `scripts/cleanup_legacy_project_shards.py`:

```python
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete shards that pass the safety check. Default is dry-run.",
    )
    parser.add_argument(
        "--cutoff-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=DEFAULT_CUTOFF_DATE,
        help="Shards with mtime at or after this date are never deleted. Default: 2026-09-16.",
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=DEFAULT_PROJECTS_ROOT,
        help="Root directory to scan for */state.db shards.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("legacy_shard_cleanup_report.txt"),
        help="Where to write the summary report.",
    )
    args = parser.parse_args(argv)
    args.projects_root = args.projects_root.expanduser()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run_cleanup(
        projects_root=args.projects_root,
        cutoff=args.cutoff_date,
        execute=args.execute,
        report_path=args.report_path,
    )
    mode = "EXECUTED" if args.execute else "DRY RUN"
    print(f"[{mode}] scanned shards under {args.projects_root}")
    print(f"  deletable: {result.deletable_count} shard(s), {result.deletable_bytes} bytes")
    print(f"  skipped (newer than cutoff): {result.skipped_count} shard(s)")
    if args.execute:
        print(f"  deleted: {result.deleted_count} shard(s), {result.deleted_bytes} bytes")
    print(f"  full report: {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cleanup_legacy_project_shards.py -v`
Expected: all PASS (7 tests total across Tasks 5-8)

- [ ] **Step 5: Commit**

```bash
git add scripts/cleanup_legacy_project_shards.py tests/test_cleanup_legacy_project_shards.py
git commit -m "feat(cleanup): add CLI entry point with --execute/--cutoff-date/--report-path"
```

---

## Self-Review

**Spec coverage:**
- Component 1 "new package `synlynk/migrations/`" → Tasks 1-2.
- Component 1 "migration_history audit table" → Task 2 (`_ensure_migration_history_table`).
- Component 1 "retry-safe, ascending order" → Task 3.
- Component 1 "`_migrate_db()` becomes a thin wrapper... preserving the existing call site" → Task 4. The literal "mechanically split along existing logical blocks" instruction is explicitly superseded in the Architecture section above, for the reasons given (1072-line non-linear body, transcription risk) — this is a documented scope adjustment, not a silent gap.
- Component 2 scan/safety-check/dry-run/`--execute`/report → Tasks 5-8, matching the design spec's five numbered steps exactly (scan, safety check per shard, dry-run default, `--execute` required flag, final report in both modes).

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate error handling" strings appear in any task. Every code step is complete, runnable code, not a description of code.

**Type consistency:** `Migration.up: Callable[[sqlite3.Connection], None]` (Task 1) matches every `up_16`/`up_17` test fixture's signature (Task 3). `Shard` (Task 5) and `CleanupResult` (Task 6) field names are used identically across Tasks 5-8 (`path`, `size_bytes`, `mtime` / `deletable_count`, `deletable_bytes`, `skipped_count`, `deleted_count`, `deleted_bytes` — no renamed fields anywhere downstream). `run_cleanup`'s keyword arguments (`projects_root`, `cutoff`, `execute`, `report_path`) match `main()`'s call in Task 8 exactly.

---

## Execution Note

Components 1 and 2 touch disjoint files and have no data or import dependency on each other — they can be dispatched to two different workers in parallel, or executed sequentially in either order.
