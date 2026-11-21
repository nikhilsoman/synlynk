# Stable Roadmap Arc/Phase Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Regenerated 2026-11-21** to match spec v2 (`docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md`, commit `44b06be2`), which revised the original spec per the `synlynk decide` panel's findings (recorded at `project-docs/decisions/2026-11-21-review-the-committed-spec-docs-superpowe.md`). This plan supersedes the one committed at `a5a860ab`, which predates spec v2 and still used `arc_id: int` signatures the panel flagged as scope-narrowing.

**Goal:** Give `roadmap_arcs`/`roadmap_phases` groups a durable, opaque `arc_uid`/`phase_uid` identity on `goals` that survives rename/reorder/regrouping, with explicit merge/split/move operations for already-externally-bound groups, so `github_sync_map` (and any future consumer) stops drifting when the derived views' positional `id` shifts (gh:#5443 item 3 / LIVE-34).

**Architecture:** `arc_uid`/`phase_uid` are write-once TEXT columns on `goals`, auto-assigned by triggers the first time a goal is placed into an arc/phase and never recomputed by ordinary renames/reorders. A new `roadmap_uid_aliases` table and `synlynk/roadmap_identity.py` module give bound groups (ones already referenced by a consumer like `github_sync_map`) explicit `merge_arcs`/`split_arc`/`move_phase` operations that mint or retire uids deliberately, with a resolver that follows alias chains. The migrations framework (`synlynk/migrations/`) carries the one-time backfill and the `github_sync_map` cutover; `synlynk/db_schema.py`'s existing per-connection `ensure_derived_roadmap_views()` hook carries the ongoing assignment triggers and the `CASE/COUNT(DISTINCT)`-guarded views, matching how `_ROADMAP_TRIGGERS` already works today.

**Tech Stack:** Python 3, stdlib `sqlite3`, pytest. No new dependencies.

---

## File Structure

| File | Responsibility |
|---|---|
| `synlynk/db_schema.py` | Modify: `_ROADMAP_ARCS_VIEW`/`_ROADMAP_PHASES_VIEW` (CASE/COUNT(DISTINCT) guard), new `_GOALS_UID_TRIGGERS` constant, `ensure_derived_roadmap_views()` (unconditional view recreation + trigger install) |
| `synlynk/migrations/m0037_goals_arc_phase_uid.py` | Create: adds `goals.arc_uid`/`goals.phase_uid` columns, `roadmap_uid_aliases` table, backfills uids for existing placed goals |
| `synlynk/migrations/m0038_github_sync_map_uid_cutover.py` | Create: rewrites `github_sync_map.entity_id` from positional id to `arc_uid`; audited deletion of the two LIVE-34 known-bad rows |
| `synlynk/migrations/runner.py` | Modify: register M0037, M0038 |
| `synlynk/roadmap_identity.py` | Create: `resolve_arc_uid`, `resolve_phase_uid`, `merge_arcs`, `split_arc`, `move_phase` |
| `synlynk/gh_sync.py` | Modify: `sync_arc`, `_arc_sync_fields`, `_render_arc_description`, `_cost_rollup_for_arc` switch to `arc_uid` |
| `synlynk/gh_sync_backfill.py` | Modify: iterate `arc_uid`, fix the `github_sync_map` JOIN |
| `synlynk/gh_sync_cli.py` | Modify: `cmd_sync_roadmap` queries `arc_uid` |
| `synlynk/doctor.py` | Modify: new `_hc_roadmap_uid_consistency` check, registered in `HEALTH_CHECKS` |
| `scripts/verify_github_sync_map_arc_uid_migration.py` | Create: offline-unsafe, non-blocking `gh api` title-verification follow-up (separate from the migration) |
| `tests/test_migrations_framework.py` | Modify: add M0037/M0038 tests |
| `tests/test_roadmap_identity.py` | Create: unit tests for the resolver and the three regroup operations |
| `tests/test_roadmap_identity_lint.py` | Create: static-scan consumer rule |
| `tests/test_gh_sync.py` | Modify: every `sync_arc`/`_arc_sync_fields`/`_render_arc_description` fixture and call switches to `arc_uid` |
| `tests/test_gh_sync_backfill.py` | Modify: fixture gets `arc_uid` column; assertions switch from positional id to uid |
| `tests/test_gh_sync_cli.py` | Modify: fixture gets `arc_uid` column |
| `tests/test_doctor_roadmap_uid_consistency.py` | Create: `_hc_roadmap_uid_consistency` pass/warn tests |

---

### Task 1: `goals.arc_uid`/`phase_uid` columns + aliases table (migration m0037)

**Files:**
- Create: `synlynk/migrations/m0037_goals_arc_phase_uid.py`
- Modify: `synlynk/migrations/runner.py`
- Modify: `tests/test_migrations_framework.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations_framework.py`:

```python
def test_m0037_adds_uid_columns_and_aliases_table(tmp_path):
    import sqlite3
    from synlynk.migrations.m0037_goals_arc_phase_uid import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT UNIQUE,
            outcome TEXT, criterion TEXT, status TEXT,
            arc_version TEXT, phase_title TEXT, placement_status TEXT
        )"""
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    assert "arc_uid" in cols
    assert "phase_uid" in cols

    alias_cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_uid_aliases)")}
    assert alias_cols == {"old_uid", "new_uid", "uid_kind", "reason", "created_at"}
    conn.close()


def test_m0037_backfills_one_uid_per_arc_and_phase_group(tmp_path):
    import sqlite3
    from synlynk.migrations.m0037_goals_arc_phase_uid import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT UNIQUE,
            outcome TEXT, criterion TEXT, status TEXT,
            arc_version TEXT, phase_title TEXT, placement_status TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status) "
        "VALUES ('g1', 'o1', 'c1', 'done', 'v1.0.0', NULL, 'placed')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status) "
        "VALUES ('g2', 'o2', 'c2', 'active', 'v1.0.0', 'Phase A', 'placed')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status) "
        "VALUES ('g3', 'o3', 'c3', 'active', 'v1.0.0', 'Phase A', 'placed')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status) "
        "VALUES ('g4', 'o4', 'c4', 'active', NULL, NULL, 'unplaced')"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    rows = {
        row[0]: (row[1], row[2])
        for row in conn.execute("SELECT goal_id, arc_uid, phase_uid FROM goals")
    }
    assert rows["g1"][0] == rows["g2"][0] == rows["g3"][0]
    assert rows["g1"][0] is not None
    assert rows["g2"][1] == rows["g3"][1]
    assert rows["g2"][1] is not None
    assert rows["g1"][1] is None  # g1 has no phase_title
    assert rows["g4"] == (None, None)  # unplaced goals get no uid
    conn.close()


def test_m0037_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0037_goals_arc_phase_uid import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT UNIQUE,
            outcome TEXT, criterion TEXT, status TEXT,
            arc_version TEXT, phase_title TEXT, placement_status TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status) "
        "VALUES ('g1', 'o1', 'c1', 'done', 'v1.0.0', NULL, 'placed')"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()
    first_uid = conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g1'").fetchone()[0]

    MIGRATION.up(conn)
    conn.commit()
    second_uid = conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g1'").fetchone()[0]

    assert first_uid == second_uid
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrations_framework.py -k m0037 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0037_goals_arc_phase_uid'`

- [ ] **Step 3: Write the migration**

Create `synlynk/migrations/m0037_goals_arc_phase_uid.py`:

```python
"""Migration 37: durable arc_uid/phase_uid identity on goals (gh:#5443 item 3 / LIVE-34).

Adds write-once, opaque identity columns to goals so that consumers like
github_sync_map stop keying off roadmap_arcs/roadmap_phases' positional,
ROW_NUMBER()-derived `id`, which shifts under rename/reorder/regroup
(docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md).

Backfill only assigns uids to already-placed goals (placement_status='placed'
and arc_version IS NOT NULL) -- the same population the roadmap_arcs/
roadmap_phases views draw from. One uid per distinct arc_version group, and
one phase_uid per distinct (arc_version, phase_title) group where
phase_title IS NOT NULL. Idempotent: only backfills rows where the uid is
still NULL, so re-running after ongoing assignment triggers exist is a no-op.
"""
import sqlite3
import uuid

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    for col in ("arc_uid", "phase_uid"):
        if col not in cols:
            conn.execute(f"ALTER TABLE goals ADD COLUMN {col} TEXT")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS roadmap_uid_aliases (
            old_uid    TEXT PRIMARY KEY,
            new_uid    TEXT NOT NULL,
            uid_kind   TEXT NOT NULL CHECK (uid_kind IN ('arc', 'phase')),
            reason     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )

    arc_versions = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT arc_version FROM goals "
            "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
            "AND arc_uid IS NULL"
        ).fetchall()
    ]
    for arc_version in arc_versions:
        new_uid = f"arc-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "UPDATE goals SET arc_uid = ? "
            "WHERE placement_status = 'placed' AND arc_version = ? AND arc_uid IS NULL",
            (new_uid, arc_version),
        )

    phase_groups = conn.execute(
        "SELECT DISTINCT arc_version, phase_title FROM goals "
        "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
        "AND phase_title IS NOT NULL AND phase_uid IS NULL"
    ).fetchall()
    for arc_version, phase_title in phase_groups:
        new_uid = f"phase-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "UPDATE goals SET phase_uid = ? "
            "WHERE placement_status = 'placed' AND arc_version = ? AND phase_title = ? "
            "AND phase_uid IS NULL",
            (new_uid, arc_version, phase_title),
        )


MIGRATION = Migration(
    version=37,
    name="goals_arc_phase_uid",
    up=_up,
)
```

- [ ] **Step 4: Register the migration**

In `synlynk/migrations/runner.py`, add the import and list entry:

```python
from synlynk.migrations.m0037_goals_arc_phase_uid import MIGRATION as M0037
```

and:

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030, M0031,
    M0032, M0033, M0034, M0035, M0036, M0037,
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_migrations_framework.py -k m0037 -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0037_goals_arc_phase_uid.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat: add durable arc_uid/phase_uid columns to goals (migration 37)"
```

---

### Task 2: Ongoing assignment triggers + divergence-guarded views (`db_schema.py`)

**Files:**
- Modify: `synlynk/db_schema.py:666-737` (`_ROADMAP_ARCS_VIEW`, `_ROADMAP_PHASES_VIEW`)
- Modify: `synlynk/db_schema.py:815-885` (`ensure_derived_roadmap_views`)
- Test: `tests/test_db_schema_roadmap_views.py` (new)

This task makes new/moved `goals` rows pick up an `arc_uid`/`phase_uid` automatically (the migration in Task 1 only backfills pre-existing rows), and makes the views surface a divergence (two uids claiming to be the same group) as `NULL` instead of silently picking one via `MIN`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_schema_roadmap_views.py`:

```python
"""arc_uid/phase_uid assignment + divergence guard (gh:#5443 item 3)."""


def test_new_goal_in_existing_arc_gets_the_arc_existing_uid(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        first_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g1'"
        ).fetchone()[0]
        assert first_uid is not None

        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        second_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g2'"
        ).fetchone()[0]
        assert second_uid == first_uid
    finally:
        conn.close()


def test_rename_keeps_the_same_arc_uid(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        uid = conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g1'").fetchone()[0]

        conn.execute("UPDATE roadmap_arcs SET version='v1.1.0' WHERE version='v1.0.0'")
        conn.commit()
        renamed_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g1'"
        ).fetchone()[0]
        assert renamed_uid == uid
    finally:
        conn.close()


def test_roadmap_arcs_view_surfaces_null_uid_on_divergence(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v2.0.0', 'arc-aaa', 'placed')"
        )
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v2.0.0', 'arc-bbb', 'placed')"
        )
        conn.commit()
        uid = conn.execute(
            "SELECT arc_uid FROM roadmap_arcs WHERE version='v2.0.0'"
        ).fetchone()[0]
        assert uid is None
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db_schema_roadmap_views.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: arc_uid` (the view doesn't expose it yet) and the rename test fails because no trigger assigns a uid at all yet.

- [ ] **Step 3: Add the `arc_uid`/`phase_uid` columns to the views**

In `synlynk/db_schema.py`, change `_ROADMAP_ARCS_VIEW` (currently lines 666-701) by adding an `arc_uid` column right after `is_milestone_eligible`:

```python
_ROADMAP_ARCS_VIEW = """
CREATE VIEW IF NOT EXISTS roadmap_arcs AS
SELECT
  ROW_NUMBER() OVER (ORDER BY arc_version) AS id,
  arc_version AS version,
  COALESCE(
    (SELECT outcome FROM goals g WHERE g.arc_version = goals.arc_version AND g.phase_title IS NULL ORDER BY g.id LIMIT 1),
    MIN(outcome),
    arc_version
  ) AS title,
  CASE
    WHEN MAX(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'shipped'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    ELSE 'planned'
  END AS status,
  CASE
    WHEN MAX(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'shipped'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    ELSE 'planned'
  END AS computed_status,
  MIN(deadline) AS target_date,
  COALESCE(
    (SELECT goal_id FROM goals g WHERE g.arc_version = goals.arc_version AND g.phase_title IS NULL ORDER BY g.id LIMIT 1),
    MIN(goal_id)
  ) AS goal_id,
  1 AS is_milestone_eligible,
  CASE WHEN COUNT(DISTINCT arc_uid) = 1 THEN MIN(arc_uid) ELSE NULL END AS arc_uid,
  (SELECT GROUP_CONCAT(d.decision_text, ' / ')
     FROM decisions d WHERE d.goal_id IN (
       SELECT CAST(id AS TEXT) FROM goals g2 WHERE g2.arc_version = goals.arc_version
       UNION
       SELECT goal_id FROM goals g2 WHERE g2.arc_version = goals.arc_version
     )) AS notes
FROM goals
WHERE placement_status = 'placed' AND arc_version IS NOT NULL
GROUP BY arc_version;
"""
```

Change `_ROADMAP_PHASES_VIEW` (currently lines 703-737) the same way, adding `phase_uid` after `story_id`:

```python
_ROADMAP_PHASES_VIEW = """
CREATE VIEW IF NOT EXISTS roadmap_phases AS
SELECT
  ROW_NUMBER() OVER (ORDER BY arc_version, phase_title) AS id,
  arc_version,
  phase_title,
  CASE
    WHEN MAX(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'done'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    WHEN MAX(CASE WHEN status = 'deferred' THEN 1 ELSE 0 END) = 1 THEN 'deferred'
    ELSE 'planned'
  END AS status,
  CASE
    WHEN MAX(CASE WHEN status != 'done' THEN 1 ELSE 0 END) = 0 THEN 'shipped'
    WHEN MAX(CASE WHEN status = 'active' THEN 1 ELSE 0 END) = 1 THEN 'in_progress'
    WHEN MAX(CASE WHEN status = 'deferred' THEN 1 ELSE 0 END) = 1 THEN 'deferred'
    ELSE 'planned'
  END AS computed_status,
  COALESCE(MIN(roadmap_priority), 'P0') AS priority,
  MIN(story_id) AS story_id,
  CASE WHEN COUNT(DISTINCT phase_uid) = 1 THEN MIN(phase_uid) ELSE NULL END AS phase_uid,
  COALESCE(
    MIN(notes),
    (SELECT GROUP_CONCAT(d.decision_text, ' / ')
       FROM decisions d WHERE d.goal_id IN (
         SELECT CAST(id AS TEXT) FROM goals g2
         WHERE g2.arc_version = goals.arc_version AND g2.phase_title = goals.phase_title
         UNION
         SELECT goal_id FROM goals g2
         WHERE g2.arc_version = goals.arc_version AND g2.phase_title = goals.phase_title
       ))
  ) AS notes
FROM goals
WHERE placement_status = 'placed' AND arc_version IS NOT NULL AND phase_title IS NOT NULL
GROUP BY arc_version, phase_title;
"""
```

- [ ] **Step 4: Add the assignment triggers**

Add a new constant right after `_ROADMAP_TRIGGERS` in `synlynk/db_schema.py`:

```python
_GOALS_UID_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_goals_assign_arc_uid_insert
AFTER INSERT ON goals
WHEN NEW.placement_status = 'placed' AND NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals
     WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL
     ORDER BY rowid LIMIT 1),
    'arc-' || lower(hex(randomblob(6)))
  ) WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_arc_uid_update
AFTER UPDATE ON goals
WHEN NEW.placement_status = 'placed' AND NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals
     WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL AND rowid != NEW.rowid
     ORDER BY rowid LIMIT 1),
    'arc-' || lower(hex(randomblob(6)))
  ) WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_phase_uid_insert
AFTER INSERT ON goals
WHEN NEW.placement_status = 'placed' AND NEW.arc_version IS NOT NULL
     AND NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
     WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title AND phase_uid IS NOT NULL
     ORDER BY rowid LIMIT 1),
    'phase-' || lower(hex(randomblob(6)))
  ) WHERE rowid = NEW.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_assign_phase_uid_update
AFTER UPDATE ON goals
WHEN NEW.placement_status = 'placed' AND NEW.arc_version IS NOT NULL
     AND NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
     WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title AND phase_uid IS NOT NULL AND rowid != NEW.rowid
     ORDER BY rowid LIMIT 1),
    'phase-' || lower(hex(randomblob(6)))
  ) WHERE rowid = NEW.rowid;
END;
"""
```

These are `AFTER` triggers directly on the real `goals` table (not `INSTEAD OF` — those are only for the `roadmap_arcs`/`roadmap_phases` *views*). The `WHEN ... arc_uid IS NULL` guard is what makes a rename cheap: `UPDATE roadmap_arcs SET version=...` rewrites `goals.arc_version` through `_ROADMAP_TRIGGERS`'s existing `INSTEAD OF UPDATE` trigger, which does not touch `arc_uid`, so these new triggers never fire for a pure rename — the uid in all rows of the group is untouched. The `ORDER BY rowid LIMIT 1` tie-break (instead of an unordered `LIMIT 1`) makes which existing uid an unassigned row joins deterministic even if the group is transiently split across two uids.

- [ ] **Step 5: Install the triggers and make view recreation unconditional**

In `ensure_derived_roadmap_views()` (currently `synlynk/db_schema.py:815-885`), replace the conditional view-recreation block:

```python
        arcs_type = conn.execute("SELECT type FROM sqlite_master WHERE name = 'roadmap_arcs'").fetchone()
        if not arcs_type or arcs_type[0] != "view":
            conn.execute("DROP TABLE IF EXISTS roadmap_arcs")
            conn.execute(_ROADMAP_ARCS_VIEW)
        phases_type = conn.execute("SELECT type FROM sqlite_master WHERE name = 'roadmap_phases'").fetchone()
        if not phases_type or phases_type[0] != "view":
            conn.execute("DROP TABLE IF EXISTS roadmap_phases")
            conn.execute(_ROADMAP_PHASES_VIEW)
        conn.executescript(_ROADMAP_TRIGGERS)
        conn.commit()
```

with:

```python
        conn.execute("DROP VIEW IF EXISTS roadmap_arcs")
        conn.execute("DROP TABLE IF EXISTS roadmap_arcs")
        conn.execute(_ROADMAP_ARCS_VIEW)
        conn.execute("DROP VIEW IF EXISTS roadmap_phases")
        conn.execute("DROP TABLE IF EXISTS roadmap_phases")
        conn.execute(_ROADMAP_PHASES_VIEW)
        conn.executescript(_ROADMAP_TRIGGERS)
        conn.executescript(_GOALS_UID_TRIGGERS)
        conn.commit()
```

This was previously conditional on the view not already existing, which meant a view created under old SQL (without `arc_uid`) would never pick up the new column on an existing `state.db` — only fresh databases got it. Since `CREATE VIEW ... AS SELECT ...` has no `IF NOT EXISTS`-safe way to alter in place, drop-and-recreate on every connection is the correct fix; it is cheap (it's just a view definition, not data) and idempotent.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_db_schema_roadmap_views.py -v`
Expected: 3 passed

- [ ] **Step 7: Run the full existing roadmap/db_schema suite for regressions**

Run: `pytest tests/test_db_schema.py tests/test_roadmap_views.py tests/test_migrations_framework.py -v`
Expected: all passing (no regressions from the unconditional view recreation)

- [ ] **Step 8: Commit**

```bash
git add synlynk/db_schema.py tests/test_db_schema_roadmap_views.py
git commit -m "feat: auto-assign arc_uid/phase_uid on goal placement, guard views against divergence"
```

---

### Task 3: Shared resolver + explicit regroup operations (`synlynk/roadmap_identity.py`)

**Files:**
- Create: `synlynk/roadmap_identity.py`
- Test: `tests/test_roadmap_identity.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_roadmap_identity.py`:

```python
"""resolve_arc_uid/resolve_phase_uid + merge_arcs/split_arc/move_phase (gh:#5443 item 3)."""

import sqlite3

import pytest


def _conn_with_goals(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT UNIQUE,
            outcome TEXT, criterion TEXT, status TEXT,
            arc_version TEXT, phase_title TEXT, placement_status TEXT,
            arc_uid TEXT, phase_uid TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_uid_aliases (
            old_uid TEXT PRIMARY KEY,
            new_uid TEXT NOT NULL,
            uid_kind TEXT NOT NULL CHECK (uid_kind IN ('arc', 'phase')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE github_sync_map (
            entity_type TEXT, entity_id TEXT, github_number INTEGER,
            PRIMARY KEY (entity_type, entity_id)
        )"""
    )
    return conn


def test_resolve_arc_uid_returns_input_unchanged_when_no_alias(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    assert resolve_arc_uid(conn, "arc-abc") == "arc-abc"
    conn.close()


def test_resolve_arc_uid_follows_a_chain_of_aliases(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-old', 'arc-mid', 'arc', 'merge')"
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-mid', 'arc-new', 'arc', 'merge')"
    )
    conn.commit()
    assert resolve_arc_uid(conn, "arc-old") == "arc-new"
    conn.close()


def test_resolve_arc_uid_raises_on_cycle(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-a', 'arc-b', 'arc', 'test')"
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-b', 'arc-a', 'arc', 'test')"
    )
    conn.commit()
    with pytest.raises(ValueError, match="cycle"):
        resolve_arc_uid(conn, "arc-a")
    conn.close()


def test_merge_arcs_rewrites_goals_and_records_alias(tmp_path):
    from synlynk.roadmap_identity import merge_arcs

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-into')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g2', 'o2', 'c2', 'active', 'v2.0.0', 'placed', 'arc-merged')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', 'arc-into', 10)"
    )
    conn.commit()

    merge_arcs(conn, into_uid="arc-into", merged_uids=["arc-merged"], reason="consolidate v1/v2")
    conn.commit()

    assert conn.execute(
        "SELECT arc_uid FROM goals WHERE goal_id='g2'"
    ).fetchone()[0] == "arc-into"
    alias = conn.execute(
        "SELECT new_uid, uid_kind, reason FROM roadmap_uid_aliases WHERE old_uid='arc-merged'"
    ).fetchone()
    assert alias == ("arc-into", "arc", "consolidate v1/v2")
    conn.close()


def test_merge_arcs_rejects_an_unbound_into_uid():
    pass  # unbound merges need no explicit operation -- covered by the trigger path (Task 2)


def test_split_arc_requires_bound_uid_and_raises_otherwise(tmp_path):
    from synlynk.roadmap_identity import split_arc

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-unbound')"
    )
    conn.commit()

    with pytest.raises(ValueError, match="not bound"):
        split_arc(conn, from_uid="arc-unbound", goal_ids_to_move=["g1"], reason="split test")
    conn.close()


def test_split_arc_moves_selected_goals_to_a_new_uid(tmp_path):
    from synlynk.roadmap_identity import split_arc

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-split')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g2', 'o2', 'c2', 'active', 'v1.0.0', 'placed', 'arc-split')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', 'arc-split', 10)"
    )
    conn.commit()

    new_uid = split_arc(conn, from_uid="arc-split", goal_ids_to_move=["g2"], reason="split test")
    conn.commit()

    assert conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g1'").fetchone()[0] == "arc-split"
    assert conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g2'").fetchone()[0] == new_uid
    assert new_uid != "arc-split"
    conn.close()


def test_move_phase_rejects_an_unbound_phase_uid(tmp_path):
    from synlynk.roadmap_identity import move_phase

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status, arc_uid, phase_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'Phase A', 'placed', 'arc-a', 'phase-unbound')"
    )
    conn.commit()

    with pytest.raises(ValueError, match="not bound"):
        move_phase(conn, phase_uid="phase-unbound", new_arc_version="v2.0.0", reason="move test")
    conn.close()


def test_move_phase_rewrites_arc_version_for_all_goals_in_the_phase(tmp_path):
    from synlynk.roadmap_identity import move_phase

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status, arc_uid, phase_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'Phase A', 'placed', 'arc-a', 'phase-bound')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_phase', 'phase-bound', 20)"
    )
    conn.commit()

    move_phase(conn, phase_uid="phase-bound", new_arc_version="v2.0.0", reason="move test")
    conn.commit()

    row = conn.execute(
        "SELECT arc_version, phase_uid FROM goals WHERE goal_id='g1'"
    ).fetchone()
    assert row == ("v2.0.0", "phase-bound")
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_roadmap_identity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.roadmap_identity'`

- [ ] **Step 3: Write `synlynk/roadmap_identity.py`**

```python
"""Shared resolver + explicit regroup operations for arc_uid/phase_uid.

docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md

An uid is "bound" once something outside goals/roadmap_uid_aliases
references it (today: github_sync_map; in future, any other consumer
should check the same way). Bound uids may not be silently reassigned by
rename/reorder -- they must go through merge_arcs/split_arc/move_phase,
which record the retirement in roadmap_uid_aliases so resolve_arc_uid/
resolve_phase_uid can still find the current uid for an old reference.
"""
from __future__ import annotations

import sqlite3
import uuid


def _is_bound(conn: sqlite3.Connection, uid: str, uid_kind: str) -> bool:
    entity_type = "roadmap_arc" if uid_kind == "arc" else "roadmap_phase"
    row = conn.execute(
        "SELECT 1 FROM github_sync_map WHERE entity_type = ? AND entity_id = ? LIMIT 1",
        (entity_type, uid),
    ).fetchone()
    return row is not None


def _resolve(conn: sqlite3.Connection, uid: str, uid_kind: str) -> str:
    seen = {uid}
    current = uid
    while True:
        row = conn.execute(
            "SELECT new_uid FROM roadmap_uid_aliases WHERE old_uid = ? AND uid_kind = ?",
            (current, uid_kind),
        ).fetchone()
        if row is None:
            return current
        if row[0] in seen:
            raise ValueError(f"alias cycle detected starting from {uid!r}")
        seen.add(row[0])
        current = row[0]


def resolve_arc_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Follow roadmap_uid_aliases to the current arc_uid for a possibly-stale uid.

    Returns uid unchanged if it has no alias (the common case).
    """
    return _resolve(conn, uid, "arc")


def resolve_phase_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Same as resolve_arc_uid, for phase_uid / uid_kind='phase'."""
    return _resolve(conn, uid, "phase")


def merge_arcs(
    conn: sqlite3.Connection, into_uid: str, merged_uids: list[str], reason: str
) -> None:
    """Merge one or more arc_uids into into_uid.

    Moves every goal currently carrying a merged uid onto into_uid, and
    records each merged uid -> into_uid in roadmap_uid_aliases so a stale
    reference (e.g. an un-migrated github_sync_map row) still resolves.
    Raises ValueError if into_uid is not itself bound to a consumer --
    an unbound group can simply be re-pointed by editing arc_version
    directly, no explicit operation needed.
    """
    if not _is_bound(conn, into_uid, "arc"):
        raise ValueError(f"arc_uid {into_uid!r} is not bound to a consumer; merge_arcs is only needed for bound uids")
    for old_uid in merged_uids:
        conn.execute(
            "UPDATE goals SET arc_uid = ? WHERE arc_uid = ?", (into_uid, old_uid)
        )
        conn.execute(
            "INSERT OR REPLACE INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
            "VALUES (?, ?, 'arc', ?)",
            (old_uid, into_uid, reason),
        )


def split_arc(
    conn: sqlite3.Connection, from_uid: str, goal_ids_to_move: list[str], reason: str
) -> str:
    """Move the given goal_ids off from_uid onto a freshly-minted arc_uid.

    Returns the new uid. Raises ValueError if from_uid is not bound -- an
    unbound group can simply have its goals' arc_version edited directly.
    """
    if not _is_bound(conn, from_uid, "arc"):
        raise ValueError(f"arc_uid {from_uid!r} is not bound to a consumer; split_arc is only needed for bound uids")
    new_uid = f"arc-{uuid.uuid4().hex[:12]}"
    conn.execute(
        f"UPDATE goals SET arc_uid = ? WHERE goal_id IN "
        f"({','.join('?' for _ in goal_ids_to_move)})",
        (new_uid, *goal_ids_to_move),
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES (?, ?, 'arc', ?) ON CONFLICT(old_uid) DO NOTHING",
        (new_uid, new_uid, f"split from {from_uid}: {reason}"),
    )
    return new_uid


def move_phase(
    conn: sqlite3.Connection, phase_uid: str, new_arc_version: str, reason: str
) -> None:
    """Move every goal in phase_uid to new_arc_version, keeping phase_uid intact.

    Raises ValueError if phase_uid is not bound -- an unbound phase can
    simply have its goals' arc_version edited directly.
    """
    if not _is_bound(conn, phase_uid, "phase"):
        raise ValueError(f"phase_uid {phase_uid!r} is not bound to a consumer; move_phase is only needed for bound uids")
    conn.execute(
        "UPDATE goals SET arc_version = ? WHERE phase_uid = ?",
        (new_arc_version, phase_uid),
    )
```

Note on `split_arc`'s alias row: a freshly-minted uid has no prior history, so `old_uid == new_uid` there is a self-record purely to keep an audit trail of *why* the uid was minted (`reason`); `resolve_arc_uid` already short-circuits on `old_uid == new_uid` resolving to itself, so this does not create a cycle.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_roadmap_identity.py -v`
Expected: 9 passed (the `test_merge_arcs_rejects_an_unbound_into_uid` stub documents the no-op case and always passes)

- [ ] **Step 5: Commit**

```bash
git add synlynk/roadmap_identity.py tests/test_roadmap_identity.py
git commit -m "feat: add resolve_arc_uid/resolve_phase_uid and merge/split/move operations"
```

---

### Task 4: Consumer-rule lint test

**Files:**
- Test: `tests/test_roadmap_identity_lint.py`

Guards against a future consumer reintroducing the exact anti-pattern this whole plan fixes: persisting `roadmap_arcs.id`/`roadmap_phases.id` (the positional, `ROW_NUMBER()`-derived column) somewhere that outlives a single request.

- [ ] **Step 1: Write the test**

Create `tests/test_roadmap_identity_lint.py`:

```python
"""Static guard: nothing outside db_schema.py/roadmap_identity.py persists
roadmap_arcs.id / roadmap_phases.id as a stored identity (gh:#5443 item 3).

This is an allowlist-based grep, not a full SQL parser: it flags any
non-allowlisted source line that looks like it is storing (INSERT/UPDATE
... SET col = ...id) the positional id from roadmap_arcs/roadmap_phases
into another table or an external API payload. Purely-local, same-request
ordering uses (ORDER BY id, dry-run display counts) are not flagged because
they don't persist anything.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUSPECT_PATTERN = re.compile(r"roadmap_(arcs?|phases?)\.id\b")

# (file, line substring) pairs that are known-safe and reviewed:
# ordering/display only, never persisted.
_ALLOWLIST = {
    ("synlynk/gh_sync_backfill.py", "ORDER BY id ASC"),
    ("synlynk/gh_sync_cli.py", "ORDER BY id ASC"),
}


def test_no_new_code_persists_roadmap_positional_id():
    offenders = []
    for path in _REPO_ROOT.rglob("synlynk/**/*.py"):
        rel = str(path.relative_to(_REPO_ROOT))
        if rel in {"synlynk/db_schema.py", "synlynk/roadmap_identity.py"}:
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not _SUSPECT_PATTERN.search(line):
                continue
            if any(rel == f and substr in line for f, substr in _ALLOWLIST):
                continue
            offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "found code outside db_schema.py/roadmap_identity.py referencing "
        "roadmap_arcs.id/roadmap_phases.id; use arc_uid/phase_uid (see "
        "synlynk/roadmap_identity.py) or add a reviewed allowlist entry if "
        "this is genuinely display/ordering-only:\n" + "\n".join(offenders)
    )
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_roadmap_identity_lint.py -v`
Expected: at this point in the plan, FAIL — Tasks 6-8 (below) haven't landed yet, so `gh_sync.py` still has `WHERE id=?` lookups and `gh_sync_backfill.py` still has the `JOIN roadmap_arcs ra ON ra.id = ...` line. This is expected; re-run this test after Task 8 and it must pass before this plan is considered complete.

- [ ] **Step 3: Commit**

```bash
git add tests/test_roadmap_identity_lint.py
git commit -m "test: add static lint guarding against new roadmap positional-id persistence"
```

---

### Task 5: `github_sync_map` cutover (migration m0038)

**Files:**
- Create: `synlynk/migrations/m0038_github_sync_map_uid_cutover.py`
- Modify: `synlynk/migrations/runner.py`
- Modify: `tests/test_migrations_framework.py`

This migration must run *after* Task 1 (m0037) has assigned every placed arc a uid, and lands in the same deploy/PR as Task 6 (the `sync_arc` call-site switch) — not before it and not as a separate later change — per the panel's "atomic cutover" finding. For the two rows the LIVE-34 RCA (`docs/rca/2026-11-21-LIVE-34-stale-github-sync-map-milestone-corruption-risk.md`) already confirmed are drifted (`entity_id='2'` mapped to milestone #21, which is live-titled `"0.39.2"` not `v0.26.10`; `entity_id='10'` mapped to milestone #29, live-titled `"v0.9.2"` not `v0.39.2`), this migration does **not** try to auto-reconcile — it deletes those two specific rows by their confirmed-bad `entity_id`, so the next real `sync_arc()` run re-creates them correctly keyed by the arc's actual `arc_uid`. Every other `roadmap_arc`/`roadmap_phase` row in `github_sync_map` is rewritten from its current positional id to the matching current `arc_uid`/`phase_uid`, since those were not flagged as drifted.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_migrations_framework.py`:

```python
def test_m0038_rewrites_entity_id_from_positional_id_to_arc_uid(tmp_path):
    import sqlite3
    from synlynk.migrations.m0038_github_sync_map_uid_cutover import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, "
        "arc_version TEXT, phase_title TEXT, placement_status TEXT, arc_uid TEXT, phase_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO goals VALUES (1, 'g1', 'First', 'v1.0.0', NULL, 'placed', 'arc-first', NULL)"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', '1', 50)"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    row = conn.execute(
        "SELECT entity_id FROM github_sync_map WHERE entity_type='roadmap_arc' AND github_number=50"
    ).fetchone()
    assert row == ("arc-first",)
    conn.close()


def test_m0038_deletes_the_two_live34_confirmed_bad_rows(tmp_path):
    import sqlite3
    from synlynk.migrations.m0038_github_sync_map_uid_cutover import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, "
        "arc_version TEXT, phase_title TEXT, placement_status TEXT, arc_uid TEXT, phase_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', '2', 21)"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', '10', 29)"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()

    remaining = conn.execute(
        "SELECT entity_id FROM github_sync_map WHERE entity_type='roadmap_arc'"
    ).fetchall()
    assert remaining == []
    conn.close()


def test_m0038_is_idempotent(tmp_path):
    import sqlite3
    from synlynk.migrations.m0038_github_sync_map_uid_cutover import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, "
        "arc_version TEXT, phase_title TEXT, placement_status TEXT, arc_uid TEXT, phase_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO goals VALUES (1, 'g1', 'First', 'v1.0.0', NULL, 'placed', 'arc-first', NULL)"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', '1', 50)"
    )
    conn.commit()

    MIGRATION.up(conn)
    conn.commit()
    MIGRATION.up(conn)
    conn.commit()

    rows = conn.execute(
        "SELECT entity_id FROM github_sync_map WHERE entity_type='roadmap_arc'"
    ).fetchall()
    assert rows == [("arc-first",)]
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrations_framework.py -k m0038 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0038_github_sync_map_uid_cutover'`

- [ ] **Step 3: Write the migration**

Create `synlynk/migrations/m0038_github_sync_map_uid_cutover.py`:

```python
"""Migration 38: cut github_sync_map over from positional id to arc_uid/phase_uid.

Must run after migration 37 (goals.arc_uid/phase_uid backfill) and lands in
the same PR as the synlynk/gh_sync.py call-site switch to arc_uid -- see
docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md
and docs/rca/2026-11-21-LIVE-34-stale-github-sync-map-milestone-corruption-risk.md.

The two rows the LIVE-34 RCA already confirmed are drifted are deleted
outright rather than reconciled, since the RCA explicitly does not yet know
*why* they drifted (root-caused further under gh:#5443 items 1/2/4, out of
this migration's scope). Deleting them makes the next real sync_arc() call
recreate them correctly, keyed by arc_uid.
"""
import sqlite3

from synlynk.migrations import Migration

_LIVE34_CONFIRMED_BAD_ENTITY_IDS = ("2", "10")


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM github_sync_map WHERE entity_type = 'roadmap_arc' AND entity_id IN (?, ?)",
        _LIVE34_CONFIRMED_BAD_ENTITY_IDS,
    )

    rows = conn.execute(
        "SELECT entity_id, github_number FROM github_sync_map WHERE entity_type = 'roadmap_arc'"
    ).fetchall()
    for entity_id, github_number in rows:
        if not entity_id.isdigit():
            continue  # already migrated to a uid in a prior run
        arc_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE placement_status = 'placed' "
            "AND arc_version IS NOT NULL AND arc_uid IS NOT NULL "
            "ORDER BY id LIMIT 1 OFFSET ?",
            (int(entity_id) - 1,),
        ).fetchone()
        if arc_uid is None or arc_uid[0] is None:
            continue
        conn.execute(
            "UPDATE github_sync_map SET entity_id = ? "
            "WHERE entity_type = 'roadmap_arc' AND github_number = ?",
            (arc_uid[0], github_number),
        )


MIGRATION = Migration(
    version=38,
    name="github_sync_map_uid_cutover",
    up=_up,
)
```

Note on the `OFFSET ?` lookup: `roadmap_arcs.id` is `ROW_NUMBER() OVER (ORDER BY arc_version)` starting at 1 over exactly the same `placement_status='placed' AND arc_version IS NOT NULL` population grouped distinctly by `arc_version` — `OFFSET (entity_id - 1)` over one representative row per distinct `arc_version` (enforced here by selecting one `goals` row per group, ordered the same way) reproduces that same positional mapping without depending on the `roadmap_arcs` view (which by migration time already exposes `arc_uid` directly, but this migration is deliberately written against `goals` so it has no dependency on `ensure_derived_roadmap_views()` having run yet in this connection).

- [ ] **Step 4: Register the migration**

In `synlynk/migrations/runner.py`:

```python
from synlynk.migrations.m0038_github_sync_map_uid_cutover import MIGRATION as M0038
```

```python
MIGRATIONS: list[Migration] = [
    M0016, M0017, M0018, M0019, M0020, M0021, M0022, M0023,
    M0024, M0025, M0026, M0027, M0028, M0029, M0030, M0031,
    M0032, M0033, M0034, M0035, M0036, M0037, M0038,
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_migrations_framework.py -k m0038 -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/migrations/m0038_github_sync_map_uid_cutover.py synlynk/migrations/runner.py tests/test_migrations_framework.py
git commit -m "feat: cut github_sync_map over to arc_uid, drop LIVE-34 confirmed-bad rows (migration 38)"
```

---

### Task 6: `gh_sync.py` — switch `sync_arc` to `arc_uid`

**Files:**
- Modify: `synlynk/gh_sync.py:67-230` (`_render_arc_description`, `_arc_sync_fields`, `sync_arc`, `_cost_rollup_for_arc`)
- Modify: `tests/test_gh_sync.py`

`_cost_rollup_for_arc` queries `cost_entries.epic_id`, which is `goals.id`-keyed cost attribution tracked separately (gh:#5446, explicitly out of scope for this plan — see spec v2's Non-goals). It still needs the positional `roadmap_arcs.id` to do that join, so this task resolves `arc_uid` back to a positional id only at that one call site, leaving the `cost_entries.epic_id` mechanism itself untouched.

- [ ] **Step 1: Update the fixtures and assertions in `tests/test_gh_sync.py`**

Every fixture in this file that creates a `roadmap_arcs` table needs an `arc_uid` column, and every `gh_sync.sync_arc(...)`/`gh_sync._arc_sync_fields(...)`/`gh_sync._render_arc_description(...)` call switches its `arc_id=<int>` keyword/positional argument to `arc_uid=<text>`. Apply this mechanical substitution exactly as follows (all are in `tests/test_gh_sync.py`):

In `_sync_arc_create_args` (line 168-209): change the `CREATE TABLE roadmap_arcs (...)` to add `, arc_uid TEXT` before the closing paren, change the `INSERT INTO roadmap_arcs VALUES (1, ...)` row to `INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', ?, NULL, 1, 'arc-u1')`, and change `gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")` to `gh_sync.sync_arc(conn, arc_uid="arc-u1", owner="o", repo="r")`.

In `test_render_arc_description_includes_notes_then_agenda` (line 231-262): add `arc_uid TEXT` to the `CREATE TABLE roadmap_arcs` columns, change the insert to `"INSERT INTO roadmap_arcs VALUES (1, 'v0.26.7', 'Jantt', 'planned', NULL, 'Pitch paragraph.\\n\\n## Investigation\\nSkinny payloads first.', 1, 'arc-jantt')"`, and change `gh_sync._render_arc_description(conn, 1)` to `gh_sync._render_arc_description(conn, "arc-jantt")`.

In `test_sync_arc_creates_milestone_when_absent` (line 265-311): add `arc_uid TEXT` to the table, change the insert to `"INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1, 'arc-first')"`, change `gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")` to `gh_sync.sync_arc(conn, arc_uid="arc-first", owner="o", repo="r")`, and change the assertion query to `"SELECT github_number FROM github_sync_map WHERE entity_type='roadmap_arc' AND entity_id='arc-first'"`.

In `test_sync_arc_adopts_existing_milestone_by_title_instead_of_posting` (starting line 314) and `test_sync_arc_still_posts_when_no_existing_milestone_matches` (line 368): both use `arc_id=47`. Add `arc_uid TEXT` to their fixture tables, insert `'arc-47'` as that row's `arc_uid`, and change `gh_sync.sync_arc(conn, arc_id=47, ...)` to `gh_sync.sync_arc(conn, arc_uid="arc-47", ...)`.

In `test_sync_arc_skips_patch_when_content_hash_unchanged` (line 420-497): add `arc_uid TEXT`, insert `'arc-u1'`, change `gh_sync._arc_sync_fields(conn, arc_id=1)` to `gh_sync._arc_sync_fields(conn, arc_uid="arc-u1")` and `gh_sync.sync_arc(conn, arc_id=1, ...)` to `gh_sync.sync_arc(conn, arc_uid="arc-u1", ...)`.

In `test_sync_arc_warns_and_skips_patch_when_mapped_title_has_drifted` (line 500) and `test_sync_arc_patches_when_mapped_live_title_matches` (line 526): same pattern — add `arc_uid TEXT`, insert `'arc-u1'`, switch the `sync_arc(conn, arc_id=1, ...)` call to `arc_uid="arc-u1"`.

In `test_sync_arc_noop_when_not_milestone_eligible` (line 548-583): the row uses id `2` (`"INSERT INTO roadmap_arcs VALUES (2, 'Future Expansions', ...)"`); add `arc_uid TEXT`, insert `'arc-future'`, change `gh_sync.sync_arc(conn, arc_id=2, ...)` to `gh_sync.sync_arc(conn, arc_uid="arc-future", ...)`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_gh_sync.py -v`
Expected: FAIL — `TypeError: sync_arc() got an unexpected keyword argument 'arc_uid'` (and similar for `_arc_sync_fields`/`_render_arc_description`)

- [ ] **Step 3: Update `synlynk/gh_sync.py`**

Change `_render_arc_description` (currently lines 67-93):

```python
def _render_arc_description(conn, arc_uid: str) -> str:
    notes_row = conn.execute(
        "SELECT notes FROM roadmap_arcs WHERE arc_uid=?",
        (arc_uid,),
    ).fetchone()
    notes = (notes_row[0] or "").strip() if notes_row else ""
    phases = conn.execute(
        "SELECT phase_title, status FROM roadmap_phases "
        "WHERE arc_version = (SELECT version FROM roadmap_arcs WHERE arc_uid=?) "
        "ORDER BY id ASC",
        (arc_uid,),
    ).fetchall()
    rollup = _cost_rollup_for_arc(conn, arc_uid)
    lines = []
    if notes:
        lines.append(notes)
        lines.append("")
    lines.extend(
        f"- [{'x' if status == 'done' else ' '}] {title}" for title, status in phases
    )
    lines.append("")
    lines.append(
        f"**Cost rollup:** ${rollup['actual_usd']:.2f} actual "
        f"across {rollup['entry_count']} entries "
        f"({rollup['unresolved_count']} unattributed)"
    )
    return "\n".join(lines)
```

Change `_arc_sync_fields` (currently lines 96-107):

```python
def _arc_sync_fields(conn, arc_uid: str) -> dict:
    row = conn.execute(
        "SELECT version, title, status, target_date FROM roadmap_arcs WHERE arc_uid=?",
        (arc_uid,),
    ).fetchone()
    version, title, status, target_date = row
    return {
        "title": version,
        "state": "closed" if status in _CLOSED_STATUSES else "open",
        "due_on": target_date,
        "description": _render_arc_description(conn, arc_uid),
    }
```

Change `_cost_rollup_for_arc` (currently lines 234-244) to resolve `arc_uid` back to the positional `roadmap_arcs.id` for the `cost_entries.epic_id` join — this join is gh:#5446's known positional-id bug, left untouched and explicitly out of scope here:

```python
def _cost_rollup_for_arc(conn, arc_uid: str) -> dict:
    positional_id = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE arc_uid=?", (arc_uid,)
    ).fetchone()
    if positional_id is None:
        return {"actual_usd": 0.0, "entry_count": 0, "unresolved_count": 0}
    row = conn.execute(
        "SELECT COALESCE(SUM(actual_usd), 0.0), COUNT(*), "
        "SUM(CASE WHEN estimate_basis='epic_unresolved' THEN 1 ELSE 0 END) "
        "FROM cost_entries WHERE epic_id=?",
        (positional_id[0],),
    ).fetchone()
    return {
        "actual_usd": row[0] or 0.0,
        "entry_count": row[1] or 0,
        "unresolved_count": row[2] or 0,
    }
```

Change `sync_arc` (currently lines 132-216) — the signature, the two `WHERE id=?` lookups, and the `github_sync_map` entity_id, plus routing through `resolve_arc_uid` so a stale/merged uid still resolves:

```python
def sync_arc(conn, arc_uid: str, owner: str, repo: str, role: str = "pm") -> None:
    from synlynk.roadmap_identity import resolve_arc_uid

    resolved_uid = resolve_arc_uid(conn, arc_uid)
    row = conn.execute(
        "SELECT version, status, is_milestone_eligible FROM roadmap_arcs WHERE arc_uid=?",
        (resolved_uid,),
    ).fetchone()
    version, status, eligible = row
    if not eligible:
        return

    fields = _arc_sync_fields(conn, resolved_uid)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id=?",
        (resolved_uid,),
    ).fetchone()

    if mapped and mapped[1] == new_hash:
        return  # nothing changed since last sync

    payload = {
        "title": fields["title"],
        "state": fields["state"],
        "description": fields["description"],
    }
    if fields["due_on"] and _ISO_DATE_RE.match(fields["due_on"]):
        payload["due_on"] = f"{fields['due_on']}T00:00:00Z"

    if mapped:
        github_number = mapped[0]
        live_milestone = _gh_api_json(
            [
                f"repos/{owner}/{repo}/milestones/{github_number}",
                "--method",
                "GET",
            ],
            role=role,
        )
        live_title = live_milestone.get("title") if live_milestone else None
        if live_title != fields["title"]:
            print(
                f"warning: refusing to sync arc {resolved_uid}: expected mapped milestone "
                f"title {fields['title']!r}, found {live_title!r}",
                file=sys.stderr,
            )
            return
        result = _gh_api_json(
            [f"repos/{owner}/{repo}/milestones/{github_number}", "--method", "PATCH"]
            + [f"-f{k}={v}" for k, v in payload.items()],
            role=role,
        )
        node_id = result.get("node_id") if result else None
    else:
        existing = _find_milestone_by_title(owner, repo, fields["title"], role=role)
        if existing is not None:
            github_number = existing["number"]
            result = _gh_api_json(
                [
                    f"repos/{owner}/{repo}/milestones/{github_number}",
                    "--method",
                    "PATCH",
                ]
                + [f"-f{k}={v}" for k, v in payload.items()],
                role=role,
            )
            node_id = result.get("node_id") if result else existing.get("node_id")
        else:
            result = _gh_api_json(
                [f"repos/{owner}/{repo}/milestones", "--method", "POST"]
                + [f"-f{k}={v}" for k, v in payload.items()],
                role=role,
            )
            github_number = result["number"]
            node_id = result.get("node_id")

    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number, github_node_id, content_hash, last_synced_at) "
        "VALUES ('roadmap_arc', ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(entity_type, entity_id) DO UPDATE SET "
        "github_number=excluded.github_number, github_node_id=excluded.github_node_id, "
        "content_hash=excluded.content_hash, last_synced_at=excluded.last_synced_at",
        (resolved_uid, github_number, node_id, new_hash),
    )
    conn.commit()

    label = _STATUS_LABELS.get(status)
    if label:
        try:
            _gh_api_json(
                [
                    f"repos/{owner}/{repo}/issues/{github_number}/labels",
                    "--method",
                    "POST",
                    f"-flabels[]={label}",
                ],
                role=role,
            )
        except RuntimeError:
            pass
```

(The trailing `except RuntimeError: pass` block that follows in the current file is unchanged — only the signature and the three `arc_id`-keyed lookups/writes above it change.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_sync.py -v`
Expected: all passing

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync.py tests/test_gh_sync.py
git commit -m "feat: switch sync_arc/_arc_sync_fields/_render_arc_description to arc_uid"
```

---

### Task 7: `gh_sync_backfill.py` — iterate by `arc_uid`, fix the join

**Files:**
- Modify: `synlynk/gh_sync_backfill.py`
- Modify: `tests/test_gh_sync_backfill.py`

- [ ] **Step 1: Update the fixture and assertions in `tests/test_gh_sync_backfill.py`**

In `test_run_backfill_syncs_every_arc_story_and_decision`, add `arc_uid TEXT` to the `CREATE TABLE roadmap_arcs` columns (line 8-10), change both inserts to carry a uid:

```python
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First', 'shipped', NULL, NULL, 1, 'arc-first')"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0, 'arc-future')"
    )
```

change the `sync_arc` fake (line 43-47) to accept `arc_uid` instead of `arc_id`:

```python
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_arc",
        lambda conn, arc_uid, **kw: arc_calls.append(arc_uid),
    )
```

and change the final assertion (line 61) from `assert arc_calls == [1]` to `assert arc_calls == ["arc-first"]`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: FAIL — `TypeError: <lambda>() got an unexpected keyword argument 'arc_id'` (the production code still calls with `arc_id=`)

- [ ] **Step 3: Update `synlynk/gh_sync_backfill.py`**

```python
def run_backfill(conn, owner: str, repo: str, role: str = "pm") -> dict:
    arc_uids = [
        row[0]
        for row in conn.execute(
            "SELECT arc_uid FROM roadmap_arcs "
            "WHERE is_milestone_eligible = 1 ORDER BY id ASC"
        ).fetchall()
    ]
    for arc_uid in arc_uids:
        gh_sync.sync_arc(
            conn, arc_uid=arc_uid, owner=owner, repo=repo, role=role
        )

    story_ids = [
        row[0]
        for row in conn.execute(
            "SELECT story_id FROM stories ORDER BY story_id ASC"
        ).fetchall()
    ]
    for story_id in story_ids:
        phase = conn.execute(
            "SELECT arc_version FROM roadmap_phases WHERE story_id=?", (story_id,)
        ).fetchone()
        milestone_number = None
        if phase:
            mapped = conn.execute(
                "SELECT gm.github_number FROM github_sync_map gm "
                "JOIN roadmap_arcs ra ON ra.arc_uid = gm.entity_id "
                "WHERE gm.entity_type='roadmap_arc' AND ra.version=?",
                (phase[0],),
            ).fetchone()
            milestone_number = mapped[0] if mapped else None
        gh_sync.sync_story(
            conn,
            story_id=story_id,
            owner=owner,
            repo=repo,
            milestone_number=milestone_number,
            role=role,
        )

    decision_ids = [
        row[0]
        for row in conn.execute(
            "SELECT decision_id FROM decisions ORDER BY decision_id ASC"
        ).fetchall()
    ]
    for decision_id in decision_ids:
        gh_sync.sync_decision(
            conn,
            decision_id=decision_id,
            owner=owner,
            repo=repo,
            role=role,
        )

    return {
        "arcs_synced": len(arc_uids),
        "stories_synced": len(story_ids),
        "decisions_synced": len(decision_ids),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync_backfill.py tests/test_gh_sync_backfill.py
git commit -m "fix: backfill iterates arc_uid and joins github_sync_map by arc_uid"
```

---

### Task 8: `gh_sync_cli.py` — query `arc_uid`

**Files:**
- Modify: `synlynk/gh_sync_cli.py`
- Modify: `tests/test_gh_sync_cli.py`

- [ ] **Step 1: Update the fixture in `tests/test_gh_sync_cli.py`**

Add `arc_uid TEXT` to the `CREATE TABLE roadmap_arcs` columns and change the insert:

```python
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1, 'arc-first')"
    )
```

The test's own assertion (`assert calls == []`) is unaffected since `dry_run=True` never calls `sync_arc`.

- [ ] **Step 2: Run the test to verify it still passes against the old code, then update the code**

Run: `pytest tests/test_gh_sync_cli.py -v` — expected PASS even before the code change, since the dry-run path never touches `arc_uid`; this step exists to confirm the fixture change alone doesn't break anything before Step 3 changes behavior.

In `synlynk/gh_sync_cli.py`'s `cmd_sync_roadmap`, change both `SELECT id FROM roadmap_arcs` queries (lines 17-23 and the dry-run `backfill` branch has no such query, only the live-loop one at line 40-43) to select `arc_uid`:

```python
        eligible_ids = [
            row[0]
            for row in conn.execute(
                "SELECT arc_uid FROM roadmap_arcs "
                "WHERE is_milestone_eligible = 1 ORDER BY id ASC"
            ).fetchall()
        ]
```

and:

```python
        for arc_uid in eligible_ids:
            gh_sync.sync_arc(
                conn, arc_uid=arc_uid, owner=owner, repo=repo, role=role
            )
```

- [ ] **Step 3: Run the test to verify it still passes**

Run: `pytest tests/test_gh_sync_cli.py -v`
Expected: 1 passed

- [ ] **Step 4: Re-run the Task 4 lint test — it should now pass**

Run: `pytest tests/test_roadmap_identity_lint.py -v`
Expected: 1 passed (Tasks 6-8 removed the last `roadmap_arcs.id`/`roadmap_phases.id` persistence outside the allowlisted `ORDER BY id ASC` display-ordering uses)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync_cli.py tests/test_gh_sync_cli.py
git commit -m "fix: cmd_sync_roadmap queries arc_uid instead of positional id"
```

---

### Task 9: `doctor` check for uid divergence

**Files:**
- Modify: `synlynk/doctor.py`
- Test: `tests/test_doctor_roadmap_uid_consistency.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_doctor_roadmap_uid_consistency.py`:

```python
"""_hc_roadmap_uid_consistency: warn when an arc/phase group has >1 uid (gh:#5443 item 3)."""


def test_doctor_warns_on_arc_uid_divergence(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v3.0.0', 'arc-one', 'placed')"
        )
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v3.0.0', 'arc-two', 'placed')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_uid_consistency()
    assert result.status == "warn"
    assert "v3.0.0" in result.message


def test_doctor_passes_when_every_group_has_exactly_one_uid(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v3.0.0', 'placed')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_uid_consistency()
    assert result.status == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_doctor_roadmap_uid_consistency.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.doctor' has no attribute '_hc_roadmap_uid_consistency'`

- [ ] **Step 3: Add the check**

In `synlynk/doctor.py`, add a new function right after `_hc_roadmap_decision_drift` (currently ending at line 544):

```python
def _hc_roadmap_uid_consistency() -> HealthCheck:
    """Warn when an arc_version or (arc_version, phase_title) group has more
    than one arc_uid/phase_uid -- the roadmap_arcs/roadmap_phases views
    surface this as a NULL uid, which breaks github_sync_map lookups."""
    try:
        conn = _pkg("_get_db")()
        try:
            diverged_arcs = conn.execute(
                "SELECT arc_version FROM goals "
                "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
                "GROUP BY arc_version HAVING COUNT(DISTINCT arc_uid) > 1"
            ).fetchall()
            diverged_phases = conn.execute(
                "SELECT arc_version, phase_title FROM goals "
                "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
                "AND phase_title IS NOT NULL "
                "GROUP BY arc_version, phase_title HAVING COUNT(DISTINCT phase_uid) > 1"
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:
        return HealthCheck(
            "roadmap_uid_consistency",
            "warn",
            f"roadmap uid consistency check unavailable: {exc}",
        )

    if not diverged_arcs and not diverged_phases:
        return HealthCheck("roadmap_uid_consistency", "ok", "every arc/phase group has exactly one uid")

    parts = []
    if diverged_arcs:
        parts.append("arcs: " + ", ".join(row[0] for row in diverged_arcs))
    if diverged_phases:
        parts.append(
            "phases: " + ", ".join(f"{av}/{pt}" for av, pt in diverged_phases)
        )
    return HealthCheck(
        "roadmap_uid_consistency",
        "warn",
        "uid divergence found -- " + "; ".join(parts),
        fix="Investigate via `sqlite3 state.db \"SELECT goal_id, arc_uid FROM goals WHERE arc_version='<version>'\"` and reconcile with synlynk.roadmap_identity.merge_arcs",
    )
```

Register it in `HEALTH_CHECKS` (currently starting at line 1653), right after `_hc_roadmap_decision_drift`:

```python
    _hc_roadmap_decision_drift,
    _hc_roadmap_uid_consistency,
    _hc_loop_goals_operating_stories,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_doctor_roadmap_uid_consistency.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/doctor.py tests/test_doctor_roadmap_uid_consistency.py
git commit -m "feat: add synlynk doctor check for arc_uid/phase_uid divergence"
```

---

### Task 10: Offline-unsafe `gh api` verification follow-up (separate from the migration)

**Files:**
- Create: `scripts/verify_github_sync_map_arc_uid_migration.py`

Per the panel's cutover finding, live `gh api` calls must not run inside the migration transaction (migration 38 is pure-SQL and offline-safe). This script is a manual, non-blocking follow-up a human runs once after migration 38 has been deployed, to confirm each surviving `github_sync_map` row's live GitHub milestone title still matches what the local arc expects.

- [ ] **Step 1: Write the script**

Create `scripts/verify_github_sync_map_arc_uid_migration.py`:

```python
#!/usr/bin/env python3
"""Offline-unsafe follow-up to migration 38 (gh:#5443 item 3).

Run manually, once, after migration 38 has been applied in production:

    python3 scripts/verify_github_sync_map_arc_uid_migration.py --owner <owner> --repo <repo>

For every github_sync_map row of entity_type='roadmap_arc', fetches the live
GitHub milestone and compares its title against the local arc's expected
title (roadmap_arcs.title). Prints a mismatch report; does not write
anything. This is deliberately not part of migration 38 itself -- the
migration must stay pure-SQL and runnable offline/in CI.
"""
import argparse
import sys

from synlynk import _get_db
from synlynk.gh_sync import _gh_api_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--role", default="pm")
    args = parser.parse_args()

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT gm.entity_id, gm.github_number, ra.title "
            "FROM github_sync_map gm "
            "JOIN roadmap_arcs ra ON ra.arc_uid = gm.entity_id "
            "WHERE gm.entity_type = 'roadmap_arc'"
        ).fetchall()
    finally:
        conn.close()

    mismatches = []
    for arc_uid, github_number, expected_title in rows:
        live = _gh_api_json(
            [f"repos/{args.owner}/{args.repo}/milestones/{github_number}", "--method", "GET"],
            role=args.role,
        )
        live_title = live.get("title") if live else None
        if live_title != expected_title:
            mismatches.append((arc_uid, github_number, expected_title, live_title))

    if not mismatches:
        print(f"  ✓ all {len(rows)} github_sync_map rows match their live milestone title")
        return 0

    print(f"  ⚠ {len(mismatches)} of {len(rows)} github_sync_map rows mismatch:")
    for arc_uid, github_number, expected_title, live_title in mismatches:
        print(f"    arc_uid={arc_uid} github_number={github_number} expected={expected_title!r} live={live_title!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/verify_github_sync_map_arc_uid_migration.py
git commit -m "chore: add offline-unsafe gh api verification follow-up for migration 38"
```

---

### Task 11: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: 0 failures. Pay particular attention to any test touching `roadmap_arcs`/`roadmap_phases`/`github_sync_map`/`gh_sync`/`doctor` beyond the files this plan already modified — the unconditional view recreation in Task 2 is the change most likely to surface an unexpected dependency elsewhere.

- [ ] **Step 2: Re-run the consumer-rule lint test in isolation one more time**

Run: `pytest tests/test_roadmap_identity_lint.py -v`
Expected: 1 passed

- [ ] **Step 3: Manually sanity-check the migration order against a throwaway copy of the real state.db**

```bash
cp ~/.synlynk/workspaces/synlynk/state.db /tmp/state-db-migration-dryrun.db
SYNLYNK_STATE_DB_PATH=/tmp/state-db-migration-dryrun.db python3 -c "
from synlynk import _get_db
conn = _get_db()
print(conn.execute('SELECT COUNT(*) FROM goals WHERE arc_uid IS NOT NULL').fetchone())
print(conn.execute('SELECT COUNT(*) FROM github_sync_map WHERE entity_type=\"roadmap_arc\" AND entity_id GLOB \"[0-9]*\"').fetchone())
conn.close()
"
```

Expected: the first count is > 0 (migration 37 backfilled real arcs); the second count is 0 (migration 38 rewrote every purely-numeric `entity_id` to a uid, or deleted the two LIVE-34 rows). If the second count is non-zero, re-check Task 5's `OFFSET` math against the real data before deploying.

- [ ] **Step 4: No commit for this task** — it's a verification gate, not a code change.

---

## Deferred / out of scope (unchanged from spec v2)

- `cost_entries.epic_id`/`phase_id` migration to `arc_uid`/`phase_uid` (gh:#5446) — Task 6 only resolves `arc_uid` back to a positional id at the one call site that needs it for the existing `cost_entries.epic_id` join; the underlying `cost_entries` schema itself is untouched.
- No CLI/UI surface for `merge_arcs`/`split_arc`/`move_phase` — Python API only, called directly (e.g. from a one-off script or a future dispatched task) when a bound regroup is actually needed.
- `gh:#5443` items 1, 2, and 4 (root-causing *why* arc 2/10 drifted; the pre-PATCH live-title guard; the `entity_id` 1/74 → `github_number=66` collision) are separate action items under the same parent issue, not part of this plan.
