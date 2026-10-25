---
title: "gh:#2569 — capability_calibration_results.quality_verified migration gap — Implementation Plan"
date: 2026-10-24
status: approved
goal: "goal-9ef9a965"
epic: "#2458"
milestone: "v0.25.5"
arc: "governance"
issue: "#2569"
---

# gh:#2569 — capability_calibration_results.quality_verified migration gap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `capability_calibration_results.quality_verified` column repair unconditional (not gated behind the legacy schema-version check), so an already-migrated production database gets the column on next connect instead of crashing on `INSERT`.

**Architecture:** `synlynk/db.py`'s `_run_legacy_migration_and_repairs()` already has a proven, unconditional repair pattern for exactly this situation — the sibling `capability_ratings.quality_verified` column, added via `_add_column_if_missing()` just outside the `if migration_version < _DB_MIGRATION_VERSION:` gate. This plan adds one more call to that same helper, for `capability_calibration_results`, right next to the existing one. No new migration version, no change to the dead legacy ALTER at line ~1696 (left alone for genuinely fresh pre-v15 databases).

**Tech Stack:** Python 3 stdlib (`sqlite3`), pytest.

---

### Task 1: Add the unconditional repair call

**Files:**
- Modify: `synlynk/db.py:2338-2344`
- Test: `tests/test_migrate.py` (new test appended after `test_migrate_repairs_quality_verified_on_bootstrapped_schema`, currently ending at line 1085)

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_migrate.py`, immediately after `test_migrate_repairs_quality_verified_on_bootstrapped_schema` (after its `conn.close()` at line 1085):

```python
def test_migrate_repairs_calibration_results_quality_verified_on_bootstrapped_schema(tmp_path):
    """A current-version DB missing the column on capability_calibration_results
    is repaired on the next open, mirroring the capability_ratings repair above.
    This is the gh:#2569 regression: the column was only ever added inside the
    version-gated legacy block, so an already-migrated DB (user_version >=
    _DB_MIGRATION_VERSION) never got it and crashed on INSERT."""
    import sqlite3
    from synlynk.db import _DB_MIGRATION_VERSION, _migrate_db

    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)

    # Rebuild only capability_calibration_results from the bootstrapped schema,
    # simulating an older snapshot that predates quality_verified while
    # retaining every other table and the current user_version.
    columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(capability_calibration_results)")
        if row[1] != "quality_verified"
    ]
    quoted_columns = ", ".join('"' + column.replace('"', '""') + '"' for column in columns)
    conn.execute(
        "CREATE TABLE capability_calibration_results_legacy AS "
        f"SELECT {quoted_columns} FROM capability_calibration_results"
    )
    conn.execute("DROP TABLE capability_calibration_results")
    conn.execute(
        "ALTER TABLE capability_calibration_results_legacy "
        "RENAME TO capability_calibration_results"
    )
    conn.execute(f"PRAGMA user_version = {_DB_MIGRATION_VERSION}")
    conn.commit()

    _migrate_db(conn)

    result_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(capability_calibration_results)")
    }
    assert "quality_verified" in result_cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrate.py::test_migrate_repairs_calibration_results_quality_verified_on_bootstrapped_schema -v`
Expected: FAIL with `AssertionError: assert 'quality_verified' in {...}` (the column is absent — confirms the gap).

- [ ] **Step 3: Add the unconditional repair in `synlynk/db.py`**

In `synlynk/db.py`, find the existing block (currently lines 2333-2343):

```python
    # Keep this repair outside the schema-version gate.  A database can have
    # already reached the current version while a prior migration stopped
    # before adding this column (or while the schema was bootstrapped by an
    # older build).  In that state, the version-gated migration above is a
    # no-op and _get_db() must still repair the missing column.
    _add_column_if_missing(
        conn,
        table="capability_ratings",
        column="quality_verified",
        definition="INTEGER",
    )

    _migrate_onboarding_sessions(conn)
```

Replace it with (adds one more call, same comment rationale, before `_migrate_onboarding_sessions(conn)`):

```python
    # Keep this repair outside the schema-version gate.  A database can have
    # already reached the current version while a prior migration stopped
    # before adding this column (or while the schema was bootstrapped by an
    # older build).  In that state, the version-gated migration above is a
    # no-op and _get_db() must still repair the missing column.
    _add_column_if_missing(
        conn,
        table="capability_ratings",
        column="quality_verified",
        definition="INTEGER",
    )

    # Same gap as capability_ratings above, for the sibling column on
    # capability_calibration_results (gh:#2569): it was only ever added
    # inside the version-gated legacy block (see the dead ALTER near the
    # CREATE TABLE above), so it never reaches an already-migrated database.
    _add_column_if_missing(
        conn,
        table="capability_calibration_results",
        column="quality_verified",
        definition="INTEGER",
    )

    _migrate_onboarding_sessions(conn)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migrate.py::test_migrate_repairs_calibration_results_quality_verified_on_bootstrapped_schema -v`
Expected: PASS

- [ ] **Step 5: Run the full migration and capability-sweep test files to check for regressions**

Run: `pytest tests/test_migrate.py tests/test_db.py tests/test_capability_sweep.py -v`
Expected: all PASS (no existing test relies on this column being absent).

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_migrate.py
git commit -m "fix(db): repair capability_calibration_results.quality_verified unconditionally

Mirrors the existing capability_ratings.quality_verified repair. The
column was only ever added inside the version-gated legacy migration
block, so an already-migrated production DB never received it and
crashed with 'no column named quality_verified' on the first real
capability-sweep INSERT.

Fixes #2569"
```

---

## Self-Review Notes

- **Spec coverage:** Spec's "Fix" section (one `_add_column_if_missing` call, same location) → Task 1 Step 3. Spec's "Test" section (bootstrapped-schema regression test) → Task 1 Steps 1-2, 4, mirroring `test_migrate_repairs_quality_verified_on_bootstrapped_schema` exactly, minus the `DROP VIEW capability_scores` step since `capability_calibration_results` has no dependent view (confirmed via `grep -n "CREATE VIEW" synlynk/db.py`). Spec's "Out of scope" items are not touched by this plan.
- **Placeholder scan:** none — every step has literal code, exact file/line references, and exact pytest invocations.
- **Type consistency:** `_add_column_if_missing(conn, *, table, column, definition)` signature matches its existing definition at `synlynk/db.py:2349-2355`; the new call uses it identically to the existing `capability_ratings` call.
