# Stable Roadmap Arc/Phase Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `roadmap_arcs`/`roadmap_phases` durable, position-independent identity columns (`goals.arc_uid`/`goals.phase_uid`) so `github_sync_map` and future consumers can key on something that survives arc/phase reordering, instead of the `ROW_NUMBER()`-derived `roadmap_arcs.id`/`roadmap_phases.id` that drifts whenever the underlying goal set's shape changes (gh:#5443 item 3 / LIVE-34).

**Architecture:** Add two nullable `TEXT` columns to `goals` (`arc_uid`, `phase_uid`), assigned once via new `AFTER INSERT`/`AFTER UPDATE` triggers on `goals` guarded by `WHEN ... IS NULL` (so renames never reassign), with a one-time in-place backfill for already-placed goals folded into the existing idempotent `ensure_derived_roadmap_views()` entry point. The derived views expose the new columns. `gh_sync.py::sync_arc` and `gh_sync_backfill.py`'s story→milestone join switch from the positional `roadmap_arcs.id` to `arc_uid` wherever the value is persisted in `github_sync_map`. A separate one-time data-migration function rewrites existing `github_sync_map` rows from positional ids to `arc_uid` and removes the two known-orphaned rows — written and tested here, but **not invoked against the live database as part of this plan** (per explicit user decision: ship the fix first, run the production backfill after).

**Tech Stack:** Python 3 stdlib (`sqlite3`), pytest. No new dependencies.

**Out of scope (filed separately):** `cost_entries.epic_id`/`phase_id` have the same positional-id drift on their live write path (`synlynk/db.py:2809-2822`) — tracked as gh:#5446, not touched here.

---

## File Structure

| File | Change |
|---|---|
| `synlynk/db_schema.py` | Modify: add `arc_uid`/`phase_uid` columns + backfill block, new `AFTER` triggers appended to `_ROADMAP_TRIGGERS`, view SQL exposes both columns, `ensure_derived_roadmap_views()` unconditionally recreates both views every call |
| `synlynk/gh_sync.py` | Modify: `sync_arc` resolves and persists `arc_uid` into `github_sync_map` instead of `str(arc_id)` |
| `synlynk/gh_sync_backfill.py` | Modify: story→milestone join switches from `CAST(gm.entity_id AS INTEGER) = ra.id` to `gm.entity_id = ra.arc_uid` |
| `synlynk/roadmap_migration.py` | Modify: add `backfill_github_sync_map_arc_uid()` — one-time, not auto-invoked |
| `tests/test_roadmap_views.py` | Modify: assert `arc_uid`/`phase_uid` present and shared across sibling goals |
| `tests/test_roadmap_identity_migration.py` | Create: new-goal assignment, existing-goal backfill, rename-stability, reorder-stability, forced view recreation, `backfill_github_sync_map_arc_uid` |
| `tests/test_gh_sync.py` | Modify: fixture gains `arc_uid` column; assert `github_sync_map.entity_id` is the uid, not `str(arc_id)` |
| `tests/test_gh_sync_backfill.py` | Modify: fixture gains `arc_uid`; new test for the story→milestone join using `arc_uid` |

`synlynk/gh_sync_cli.py` needs no change — it only passes the positional `arc_id` into `sync_arc`, which now does the uid translation internally.

---

## Task 1: `goals.arc_uid`/`phase_uid` columns, assignment triggers, and backfill

**Files:**
- Modify: `synlynk/db_schema.py:826-840` (column loop), `synlynk/db_schema.py:666-737` (view SQL), `synlynk/db_schema.py:739-812` (`_ROADMAP_TRIGGERS`), `synlynk/db_schema.py:869-877` (view (re)creation)
- Test: `tests/test_roadmap_identity_migration.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_roadmap_identity_migration.py`:

```python
import sqlite3

from synlynk.db_schema import ensure_derived_roadmap_views


def _base_goals_schema(conn):
    conn.executescript("""
    CREATE TABLE goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id TEXT NOT NULL UNIQUE,
        outcome TEXT NOT NULL,
        criterion TEXT NOT NULL,
        deadline TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        kind TEXT NOT NULL DEFAULT 'feature',
        placement_status TEXT NOT NULL DEFAULT 'unplaced',
        arc_version TEXT,
        phase_title TEXT,
        roadmap_priority INTEGER
    );
    CREATE TABLE decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT NOT NULL UNIQUE,
        topic TEXT NOT NULL,
        decision_text TEXT NOT NULL,
        goal_id TEXT REFERENCES goals(id)
    );
    """)


def test_new_goal_joining_placed_arc_is_assigned_arc_uid(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-1', 'A', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    ensure_derived_roadmap_views(conn)

    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-2', 'B', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.commit()

    rows = conn.execute("SELECT goal_id, arc_uid FROM goals ORDER BY goal_id").fetchall()
    assert rows[0]["arc_uid"] is not None
    assert rows[0]["arc_uid"] == rows[1]["arc_uid"]
    conn.close()


def test_existing_placed_goals_are_backfilled_with_shared_arc_uid(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-1', 'A', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-2', 'B', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.commit()

    ensure_derived_roadmap_views(conn)

    rows = conn.execute("SELECT goal_id, arc_uid FROM goals ORDER BY goal_id").fetchall()
    assert rows[0]["arc_uid"] is not None
    assert rows[0]["arc_uid"] == rows[1]["arc_uid"]
    conn.close()


def test_phase_uid_backfilled_and_shared_within_phase(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version, phase_title) "
        "VALUES ('goal-1', 'A', 'crit', 'active', 'placed', 'v1.0.0', 'Phase 1')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version, phase_title) "
        "VALUES ('goal-2', 'B', 'crit', 'active', 'placed', 'v1.0.0', 'Phase 1')"
    )
    conn.commit()

    ensure_derived_roadmap_views(conn)

    rows = conn.execute("SELECT goal_id, phase_uid FROM goals ORDER BY goal_id").fetchall()
    assert rows[0]["phase_uid"] is not None
    assert rows[0]["phase_uid"] == rows[1]["phase_uid"]
    conn.close()


def test_rename_does_not_reassign_arc_uid(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-1', 'A', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.commit()
    ensure_derived_roadmap_views(conn)

    before = conn.execute("SELECT arc_uid FROM goals WHERE goal_id='goal-1'").fetchone()["arc_uid"]
    assert before is not None

    conn.execute("UPDATE goals SET arc_version='v1.0.0-renamed' WHERE goal_id='goal-1'")
    conn.commit()

    after = conn.execute("SELECT arc_uid FROM goals WHERE goal_id='goal-1'").fetchone()["arc_uid"]
    assert after == before
    conn.close()


def test_arc_uid_survives_positional_id_reordering(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-b', 'B', 'crit', 'active', 'placed', 'v2.0.0')"
    )
    conn.commit()
    ensure_derived_roadmap_views(conn)

    arc_before = conn.execute("SELECT id, arc_uid FROM roadmap_arcs WHERE version='v2.0.0'").fetchone()
    assert arc_before["id"] == 1

    # Insert a new arc that sorts before v2.0.0, shifting v2.0.0's positional id to 2.
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-a', 'A', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.commit()
    ensure_derived_roadmap_views(conn)

    arc_after = conn.execute("SELECT id, arc_uid FROM roadmap_arcs WHERE version='v2.0.0'").fetchone()
    assert arc_after["id"] == 2
    assert arc_after["arc_uid"] == arc_before["arc_uid"]
    conn.close()


def test_ensure_derived_roadmap_views_forces_recreation_of_stale_view(tmp_path):
    """Reproduces the gap where an already-migrated DB's view never got
    redefined because the Python guard only recreates when the object is
    NOT already a view."""
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    _base_goals_schema(conn)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, placement_status, arc_version) "
        "VALUES ('goal-1', 'A', 'crit', 'active', 'placed', 'v1.0.0')"
    )
    conn.commit()

    # Simulate a DB that already has an old-shape view (pre-arc_uid) installed.
    conn.execute("""
        CREATE VIEW roadmap_arcs AS
        SELECT ROW_NUMBER() OVER (ORDER BY arc_version) AS id, arc_version AS version
        FROM goals WHERE placement_status='placed' AND arc_version IS NOT NULL
        GROUP BY arc_version
    """)
    conn.commit()

    ensure_derived_roadmap_views(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    assert "arc_uid" in cols
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_roadmap_identity_migration.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: arc_uid` (or similar) on every test, since the column/triggers/view changes don't exist yet.

- [ ] **Step 3: Add `arc_uid`/`phase_uid` columns and backfill block**

In `synlynk/db_schema.py`, extend the column-add loop at lines 827-833:

```python
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    for col, defn in (
        ("arc_version", "TEXT"),
        ("phase_title", "TEXT"),
        ("roadmap_priority", "TEXT"),
        ("story_id", "TEXT"),
        ("notes", "TEXT"),
        ("arc_uid", "TEXT"),
        ("phase_uid", "TEXT"),
    ):
        if col not in cols:
            try:
                conn.execute(f"ALTER TABLE goals ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    # One-time backfill: assign a single shared arc_uid/phase_uid per
    # arc_version/phase_title group that doesn't have one yet. Idempotent —
    # a group with any existing non-null uid among its members adopts that
    # value instead of minting a new one, so a goal that joins an already-
    # placed arc/phase later converges onto the same identity (gh:#5443 item 3).
    conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _arc_uid_backfill AS
        SELECT arc_version, 'arc-' || lower(hex(randomblob(8))) AS new_uid
        FROM goals
        WHERE arc_version IS NOT NULL AND arc_uid IS NULL
        GROUP BY arc_version
    """)
    conn.execute("""
        UPDATE goals SET arc_uid = (
            SELECT COALESCE(
                (SELECT MAX(g2.arc_uid) FROM goals g2
                 WHERE g2.arc_version = goals.arc_version AND g2.arc_uid IS NOT NULL),
                (SELECT new_uid FROM _arc_uid_backfill b WHERE b.arc_version = goals.arc_version)
            )
        )
        WHERE arc_version IS NOT NULL AND arc_uid IS NULL
    """)
    conn.execute("DROP TABLE _arc_uid_backfill")

    conn.execute("""
        CREATE TEMP TABLE IF NOT EXISTS _phase_uid_backfill AS
        SELECT arc_version, phase_title, 'phase-' || lower(hex(randomblob(8))) AS new_uid
        FROM goals
        WHERE arc_version IS NOT NULL AND phase_title IS NOT NULL AND phase_uid IS NULL
        GROUP BY arc_version, phase_title
    """)
    conn.execute("""
        UPDATE goals SET phase_uid = (
            SELECT COALESCE(
                (SELECT MAX(g2.phase_uid) FROM goals g2
                 WHERE g2.arc_version = goals.arc_version AND g2.phase_title = goals.phase_title
                       AND g2.phase_uid IS NOT NULL),
                (SELECT new_uid FROM _phase_uid_backfill b
                 WHERE b.arc_version = goals.arc_version AND b.phase_title = goals.phase_title)
            )
        )
        WHERE arc_version IS NOT NULL AND phase_title IS NOT NULL AND phase_uid IS NULL
    """)
    conn.execute("DROP TABLE _phase_uid_backfill")
    conn.commit()
```

- [ ] **Step 4: Add `AFTER INSERT`/`AFTER UPDATE` assignment triggers**

In `synlynk/db_schema.py`, append to the end of `_ROADMAP_TRIGGERS` (after the existing `trg_roadmap_phases_delete` trigger, before the closing `"""` at line 812):

```python
_ROADMAP_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_roadmap_arcs_insert
INSTEAD OF INSERT ON roadmap_arcs
BEGIN
  INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status)
  VALUES (
    COALESCE(NEW.goal_id, 'arc-goal-' || hex(randomblob(4))),
    COALESCE(NEW.title, NEW.version),
    'Outcome for ' || NEW.version,
    CASE WHEN NEW.status = 'in_progress' THEN 'active' ELSE COALESCE(NEW.status, 'active') END,
    NEW.version,
    'placed'
  )
  ON CONFLICT(goal_id) DO UPDATE SET
    arc_version = excluded.arc_version,
    placement_status = 'placed',
    status = excluded.status,
    outcome = CASE WHEN excluded.outcome != excluded.arc_version THEN excluded.outcome ELSE goals.outcome END;
END;

CREATE TRIGGER IF NOT EXISTS trg_roadmap_arcs_update
INSTEAD OF UPDATE ON roadmap_arcs
BEGIN
  UPDATE goals
  SET status = CASE WHEN NEW.status = 'in_progress' THEN 'active' ELSE NEW.status END
  WHERE arc_version = OLD.version;
END;

CREATE TRIGGER IF NOT EXISTS trg_roadmap_arcs_delete
INSTEAD OF DELETE ON roadmap_arcs
BEGIN
  DELETE FROM goals WHERE arc_version = OLD.version;
END;

CREATE TRIGGER IF NOT EXISTS trg_roadmap_phases_insert
INSTEAD OF INSERT ON roadmap_phases
BEGIN
  INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, roadmap_priority, story_id, notes, placement_status)
  VALUES (
    'phase-goal-' || hex(randomblob(4)),
    NEW.phase_title,
    'Outcome for ' || NEW.phase_title,
    CASE WHEN NEW.status = 'in_progress' THEN 'active' ELSE COALESCE(NEW.status, 'active') END,
    NEW.arc_version,
    NEW.phase_title,
    COALESCE(NEW.priority, 'P0'),
    NEW.story_id,
    NEW.notes,
    'placed'
  );
END;

CREATE TRIGGER IF NOT EXISTS trg_roadmap_phases_update
INSTEAD OF UPDATE ON roadmap_phases
BEGIN
  UPDATE goals
  SET status = CASE WHEN NEW.status = 'done' THEN 'done' WHEN NEW.status = 'in_progress' THEN 'active' ELSE NEW.status END,
      arc_version = NEW.arc_version,
      phase_title = NEW.phase_title,
      roadmap_priority = COALESCE(NEW.priority, OLD.priority, 'P0'),
      story_id = NEW.story_id,
      notes = NEW.notes
  WHERE (arc_version = OLD.arc_version AND phase_title = OLD.phase_title)
     OR (OLD.story_id IS NOT NULL AND story_id = OLD.story_id)
     OR (NEW.story_id IS NOT NULL AND story_id = NEW.story_id)
     OR (phase_id = OLD.id);
END;

CREATE TRIGGER IF NOT EXISTS trg_roadmap_phases_delete
INSTEAD OF DELETE ON roadmap_phases
BEGIN
  DELETE FROM goals WHERE arc_version = OLD.arc_version AND phase_title = OLD.phase_title;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_arc_uid_assign_insert
AFTER INSERT ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL LIMIT 1),
    'arc-' || lower(hex(randomblob(8)))
  )
  WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_arc_uid_assign_update
AFTER UPDATE ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.arc_uid IS NULL
BEGIN
  UPDATE goals SET arc_uid = COALESCE(
    (SELECT arc_uid FROM goals WHERE arc_version = NEW.arc_version AND arc_uid IS NOT NULL LIMIT 1),
    'arc-' || lower(hex(randomblob(8)))
  )
  WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_phase_uid_assign_insert
AFTER INSERT ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
     WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title AND phase_uid IS NOT NULL LIMIT 1),
    'phase-' || lower(hex(randomblob(8)))
  )
  WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_goals_phase_uid_assign_update
AFTER UPDATE ON goals
WHEN NEW.arc_version IS NOT NULL AND NEW.phase_title IS NOT NULL AND NEW.phase_uid IS NULL
BEGIN
  UPDATE goals SET phase_uid = COALESCE(
    (SELECT phase_uid FROM goals
     WHERE arc_version = NEW.arc_version AND phase_title = NEW.phase_title AND phase_uid IS NOT NULL LIMIT 1),
    'phase-' || lower(hex(randomblob(8)))
  )
  WHERE id = NEW.id;
END;
"""
```

- [ ] **Step 5: Expose the new columns in the derived views**

In `synlynk/db_schema.py`, change `_ROADMAP_ARCS_VIEW` (lines 666-701) to add `arc_uid`:

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
  (SELECT GROUP_CONCAT(d.decision_text, ' / ')
     FROM decisions d WHERE d.goal_id IN (
       SELECT CAST(id AS TEXT) FROM goals g2 WHERE g2.arc_version = goals.arc_version
       UNION
       SELECT goal_id FROM goals g2 WHERE g2.arc_version = goals.arc_version
     )) AS notes,
  MAX(arc_uid) AS arc_uid
FROM goals
WHERE placement_status = 'placed' AND arc_version IS NOT NULL
GROUP BY arc_version;
"""
```

And `_ROADMAP_PHASES_VIEW` (lines 703-737) to add `phase_uid`:

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
  ) AS notes,
  MAX(phase_uid) AS phase_uid
FROM goals
WHERE placement_status = 'placed' AND arc_version IS NOT NULL AND phase_title IS NOT NULL
GROUP BY arc_version, phase_title;
"""
```

- [ ] **Step 6: Force unconditional view recreation on every call**

In `synlynk/db_schema.py`, replace lines 869-877:

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
        # Views are cheap, pure-derived definitions with no state of their
        # own, so always drop and recreate rather than gating on whether an
        # object of that name already exists as a view — a prior gated
        # version left already-migrated DBs with a stale view definition
        # whenever the view SQL text changed (gh:#5443 item 3).
        conn.execute("DROP VIEW IF EXISTS roadmap_arcs")
        conn.execute("DROP TABLE IF EXISTS roadmap_arcs")
        conn.execute(_ROADMAP_ARCS_VIEW)
        conn.execute("DROP VIEW IF EXISTS roadmap_phases")
        conn.execute("DROP TABLE IF EXISTS roadmap_phases")
        conn.execute(_ROADMAP_PHASES_VIEW)
        conn.executescript(_ROADMAP_TRIGGERS)
        conn.commit()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_roadmap_identity_migration.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Run the full existing roadmap/FK test suites to check for regressions**

Run: `pytest tests/test_roadmap_views.py tests/test_live_32_fk_rebuild.py tests/test_cli_roadmap_derived.py -v`
Expected: PASS (no regressions — new columns are additive, existing tests use named column access)

- [ ] **Step 9: Commit**

```bash
git add synlynk/db_schema.py tests/test_roadmap_identity_migration.py
git commit -m "feat: add stable arc_uid/phase_uid identity columns to goals (gh:#5443)

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Task 2: Extend `test_roadmap_views.py` to assert the new columns

**Files:**
- Modify: `tests/test_roadmap_views.py`

- [ ] **Step 1: Write the failing assertions**

In `tests/test_roadmap_views.py`, add to the end of `test_derived_roadmap_views_creation_and_query` (after the existing phase assertions, before `conn.close()`):

```python
    # arc_uid is present and shared by every goal within the same arc
    assert arc35["arc_uid"] is not None
    arc36_row = arcs[1]
    assert arc36_row["arc_uid"] is not None
    assert arc35["arc_uid"] != arc36_row["arc_uid"]

    goal_uids = conn.execute(
        "SELECT arc_uid FROM goals WHERE arc_version='v0.35.0'"
    ).fetchall()
    assert len({row["arc_uid"] for row in goal_uids}) == 1

    # phase_uid is present and shared within a phase
    assert phases[0]["phase_uid"] is not None
    assert phases[1]["phase_uid"] is not None
    assert phases[0]["phase_uid"] != phases[1]["phase_uid"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_roadmap_views.py -v`
Expected: FAIL if Task 1 hasn't landed yet in this worktree state; PASS if run after Task 1 (Task 1 already implements the feature this asserts). Run this immediately after Task 1's Step 7 to confirm it passes rather than expecting a fail — Task 1's implementation already covers this.

- [ ] **Step 3: Run to verify it passes**

Run: `pytest tests/test_roadmap_views.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_roadmap_views.py
git commit -m "test: assert arc_uid/phase_uid present in derived roadmap views (gh:#5443)

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Task 3: `gh_sync.py::sync_arc` persists `arc_uid` instead of the positional id

**Files:**
- Modify: `synlynk/gh_sync.py:132-216`
- Test: `tests/test_gh_sync.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_gh_sync.py`, modify `_sync_arc_create_args` (lines 168-209) to add the `arc_uid` column and value:

```python
def _sync_arc_create_args(tmp_path, monkeypatch, target_date):
    import sqlite3

    from synlynk import gh_sync

    tmp_path.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE cost_entries (actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First release', "
        "'planned', ?, NULL, 1, 'arc-test-uid-001')",
        (target_date,),
    )
    conn.commit()

    created = {}

    def fake_gh_api_json(args, **kwargs):
        if args[1:3] == ["--method", "GET"]:
            return []
        created["args"] = args
        return {"number": 99, "node_id": "MI_abc"}

    monkeypatch.setattr(gh_sync, "_gh_api_json", fake_gh_api_json)
    gh_sync.sync_arc(conn, arc_id=1, owner="o", repo="r")
    conn.close()
    return created["args"]
```

Add a new test after `test_sync_arc_omits_due_on_when_target_date_is_none`:

```python
def test_sync_arc_persists_arc_uid_not_positional_id(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases ("
        "id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT, status TEXT)"
    )
    conn.execute(
        "CREATE TABLE cost_entries (actual_usd REAL, estimate_basis TEXT, epic_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (7, 'v9.0.0', 'Ninth release', "
        "'planned', NULL, NULL, 1, 'arc-stable-uid-xyz')"
    )
    conn.commit()

    monkeypatch.setattr(
        gh_sync, "_gh_api_json",
        lambda args, **kw: [] if args[1:3] == ["--method", "GET"] else {"number": 5, "node_id": "MI_z"},
    )

    gh_sync.sync_arc(conn, arc_id=7, owner="o", repo="r")

    row = conn.execute(
        "SELECT entity_id FROM github_sync_map WHERE entity_type='roadmap_arc'"
    ).fetchone()
    assert row[0] == "arc-stable-uid-xyz"
    conn.close()


def test_sync_arc_refuses_when_arc_uid_missing(tmp_path, monkeypatch, capsys):
    import sqlite3

    from synlynk import gh_sync

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (3, 'v3.0.0', 'Third release', "
        "'planned', NULL, NULL, 1, NULL)"
    )
    conn.commit()

    calls = []
    monkeypatch.setattr(gh_sync, "_gh_api_json", lambda args, **kw: calls.append(args))

    gh_sync.sync_arc(conn, arc_id=3, owner="o", repo="r")

    assert calls == []
    assert "no arc_uid assigned" in capsys.readouterr().err
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gh_sync.py -k "arc_uid" -v`
Expected: FAIL — `github_sync_map.entity_id` is still `'7'` (the positional id), not `'arc-stable-uid-xyz'`; the missing-uid test fails because `sync_arc` doesn't check for it yet.

- [ ] **Step 3: Rewrite `sync_arc` to resolve and persist `arc_uid`**

In `synlynk/gh_sync.py`, replace lines 132-216:

```python
def sync_arc(conn, arc_id: int, owner: str, repo: str, role: str = "pm") -> None:
    row = conn.execute(
        "SELECT version, status, is_milestone_eligible, arc_uid FROM roadmap_arcs WHERE id=?",
        (arc_id,),
    ).fetchone()
    version, status, eligible, arc_uid = row
    if not eligible:
        return
    if not arc_uid:
        print(
            f"warning: refusing to sync arc {arc_id} ({version}): no arc_uid assigned",
            file=sys.stderr,
        )
        return

    fields = _arc_sync_fields(conn, arc_id)
    new_hash = _content_hash(fields)

    mapped = conn.execute(
        "SELECT github_number, content_hash FROM github_sync_map "
        "WHERE entity_type='roadmap_arc' AND entity_id=?",
        (arc_uid,),
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
                f"warning: refusing to sync arc {arc_id}: expected mapped milestone "
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
        (arc_uid, github_number, node_id, new_hash),
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
```

Keep everything after this point in the function (the remainder of the label-application `try` block) unchanged — only the two `str(arc_id)` occurrences become `arc_uid`, the initial `SELECT` gains the `arc_uid` column, and the new missing-uid guard is added right after the `eligible` check.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_sync.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones — confirms no regression)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync.py tests/test_gh_sync.py
git commit -m "fix: sync_arc persists arc_uid in github_sync_map, not positional id (gh:#5443)

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Task 4: `gh_sync_backfill.py` story→milestone join uses `arc_uid`

**Files:**
- Modify: `synlynk/gh_sync_backfill.py:30-42`
- Test: `tests/test_gh_sync_backfill.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_gh_sync_backfill.py`, modify the fixture's `roadmap_arcs`/`roadmap_phases` CREATE statements to add `arc_uid`, and add a new test reproducing the LIVE-34 join bug:

```python
def test_run_backfill_syncs_every_arc_story_and_decision(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync_backfill

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
        "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)"
    )
    conn.execute(
        "CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
        "synthesis TEXT, decision_text TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First', 'shipped', NULL, NULL, 1, 'arc-uid-1')"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0, 'arc-uid-2')"
    )
    conn.execute("INSERT INTO stories VALUES ('story-a', 'A', 'done', NULL)")
    conn.execute("INSERT INTO stories VALUES ('story-b', 'B', 'open', '42')")
    conn.execute(
        "INSERT INTO decisions VALUES ('dec-1', 'Topic', 'decided', 'syn', 'text')"
    )
    conn.commit()

    arc_calls, story_calls, decision_calls = [], [], []
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_arc",
        lambda conn, arc_id, **kw: arc_calls.append(arc_id),
    )
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_story",
        lambda conn, story_id, **kw: story_calls.append(story_id),
    )
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_decision",
        lambda conn, decision_id, **kw: decision_calls.append(decision_id),
    )

    gh_sync_backfill.run_backfill(conn, owner="o", repo="r")

    assert arc_calls == [1]
    assert sorted(story_calls) == ["story-a", "story-b"]
    assert decision_calls == ["dec-1"]
    conn.close()


def test_run_backfill_resolves_milestone_via_arc_uid_not_positional_id(tmp_path, monkeypatch):
    """Reproduces LIVE-34: the story->milestone join must key on arc_uid,
    not CAST(github_sync_map.entity_id AS INTEGER), which breaks the moment
    entity_id stores a uid string instead of a positional integer."""
    import sqlite3

    from synlynk import gh_sync_backfill

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
        "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)"
    )
    conn.execute(
        "CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
        "synthesis TEXT, decision_text TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First', 'shipped', NULL, NULL, 1, 'arc-uid-stable')"
    )
    conn.execute(
        "INSERT INTO roadmap_phases VALUES "
        "(1, 'v1.0.0', 'Phase 1', 'done', 'P0', 'story-a', NULL)"
    )
    conn.execute("INSERT INTO stories VALUES ('story-a', 'A', 'done', NULL)")
    conn.execute(
        "INSERT INTO github_sync_map VALUES "
        "('roadmap_arc', 'arc-uid-stable', 77, 'MI_1', 'hash', '2026-01-01')"
    )
    conn.commit()

    milestone_numbers = []
    monkeypatch.setattr(gh_sync_backfill.gh_sync, "sync_arc", lambda conn, arc_id, **kw: None)
    monkeypatch.setattr(gh_sync_backfill.gh_sync, "sync_decision", lambda conn, decision_id, **kw: None)
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_story",
        lambda conn, story_id, milestone_number=None, **kw: milestone_numbers.append(milestone_number),
    )

    gh_sync_backfill.run_backfill(conn, owner="o", repo="r")

    assert milestone_numbers == [77]
    conn.close()
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: FAIL on `test_run_backfill_resolves_milestone_via_arc_uid_not_positional_id` with `milestone_numbers == [None]` (the `CAST(gm.entity_id AS INTEGER)` join can't match a non-numeric uid string, so the join finds nothing)

- [ ] **Step 3: Fix the join**

In `synlynk/gh_sync_backfill.py`, replace lines 30-42:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gh_sync_backfill.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/gh_sync_backfill.py tests/test_gh_sync_backfill.py
git commit -m "fix: backfill story->milestone join keys on arc_uid, not CAST(entity_id) (gh:#5443)

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Task 5: One-time `github_sync_map` data migration function (written and tested, not invoked here)

**Files:**
- Modify: `synlynk/roadmap_migration.py`
- Test: `tests/test_roadmap_identity_migration.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_roadmap_identity_migration.py`:

```python
def test_backfill_github_sync_map_arc_uid_rewrites_entity_id(tmp_path):
    import sqlite3

    from synlynk.roadmap_migration import backfill_github_sync_map_arc_uid

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute("INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'arc-uid-stable-1')")
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '1', 55, 'MI_1', 'h1', '2026-01-01')"
    )
    # Known-bad orphaned rows per docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '2', 21, 'MI_2', 'h2', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '10', 29, 'MI_3', 'h3', '2026-01-01')"
    )
    conn.commit()

    result = backfill_github_sync_map_arc_uid(conn)

    assert result["migrated"] == [
        {"old_entity_id": "1", "new_entity_id": "arc-uid-stable-1", "github_number": 55}
    ]
    assert sorted(result["deleted"]) == ["10", "2"]

    rows = conn.execute(
        "SELECT entity_id, github_number FROM github_sync_map WHERE entity_type='roadmap_arc'"
    ).fetchall()
    assert rows == [("arc-uid-stable-1", 55)]
    conn.close()


def test_backfill_github_sync_map_arc_uid_skips_unresolvable_rows(tmp_path):
    import sqlite3

    from synlynk.roadmap_migration import backfill_github_sync_map_arc_uid

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, arc_uid TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    # entity_id '99' has no corresponding roadmap_arcs row at all (not one of
    # the two documented known-bad rows, so it's skipped rather than deleted).
    conn.execute(
        "INSERT INTO github_sync_map VALUES ('roadmap_arc', '99', 12, 'MI_9', 'h9', '2026-01-01')"
    )
    conn.commit()

    result = backfill_github_sync_map_arc_uid(conn)

    assert result["migrated"] == []
    assert result["skipped"] == ["99"]
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_roadmap_identity_migration.py -k backfill_github_sync_map -v`
Expected: FAIL — `ImportError: cannot import name 'backfill_github_sync_map_arc_uid'`

- [ ] **Step 3: Implement the migration function**

Append to `synlynk/roadmap_migration.py`:

```python
# Two orphaned github_sync_map rows identified during the LIVE-34 investigation
# (docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md):
# entity_id '2' pointed at milestone 21 and entity_id '10' pointed at milestone
# 29, neither of which corresponds to a live arc by the time this migration
# runs. They are deleted rather than migrated.
_KNOWN_ORPHANED_ARC_ENTITY_IDS = ("2", "10")


def backfill_github_sync_map_arc_uid(conn: sqlite3.Connection) -> Dict[str, Any]:
    """One-time migration: rewrite github_sync_map.entity_id for
    entity_type='roadmap_arc' from the old positional roadmap_arcs.id to the
    stable arc_uid (gh:#5443 item 3). Not invoked automatically anywhere —
    run manually, once, after the arc_uid-assigning fix has shipped and the
    live database has had a chance to backfill arc_uid for every placed goal.

    Returns:
        Dict with keys:
          - migrated: List[Dict] of {old_entity_id, new_entity_id, github_number}
          - deleted: List[str] of entity_ids removed as known-orphaned
          - skipped: List[str] of entity_ids with no resolvable arc_uid
    """
    deleted: List[str] = []
    for bad_id in _KNOWN_ORPHANED_ARC_ENTITY_IDS:
        cur = conn.execute(
            "DELETE FROM github_sync_map WHERE entity_type='roadmap_arc' AND entity_id=?",
            (bad_id,),
        )
        if cur.rowcount:
            deleted.append(bad_id)

    rows = conn.execute(
        "SELECT entity_id, github_number FROM github_sync_map WHERE entity_type='roadmap_arc'"
    ).fetchall()

    migrated: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for old_entity_id, github_number in rows:
        arc_row = conn.execute(
            "SELECT arc_uid FROM roadmap_arcs WHERE id=?", (old_entity_id,)
        ).fetchone()
        if not arc_row or not arc_row[0]:
            skipped.append(old_entity_id)
            continue
        new_uid = arc_row[0]
        conn.execute(
            "UPDATE github_sync_map SET entity_id=? "
            "WHERE entity_type='roadmap_arc' AND entity_id=?",
            (new_uid, old_entity_id),
        )
        migrated.append(
            {
                "old_entity_id": old_entity_id,
                "new_entity_id": new_uid,
                "github_number": github_number,
            }
        )

    conn.commit()
    return {"migrated": migrated, "deleted": deleted, "skipped": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_roadmap_identity_migration.py -v`
Expected: PASS (all 8 tests in the file)

- [ ] **Step 5: Run the full targeted test suite for this plan's touched files**

Run: `pytest tests/test_roadmap_identity_migration.py tests/test_roadmap_views.py tests/test_gh_sync.py tests/test_gh_sync_backfill.py tests/test_gh_sync_cli.py tests/test_live_32_fk_rebuild.py tests/test_cli_roadmap_derived.py -v`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add synlynk/roadmap_migration.py tests/test_roadmap_identity_migration.py
git commit -m "feat: add one-time github_sync_map arc_uid backfill migration (gh:#5443)

Not invoked automatically — run manually against the live database after
this fix ships, per explicit decision to ship the fix and backfill separately.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>"
```

---

## Post-merge follow-up (not part of this plan's tasks)

1. Run `backfill_github_sync_map_arc_uid(conn)` once against the live `state.db` (e.g. via a short one-off script using `synlynk._get_db()`), after confirming the merged fix has had a chance to backfill `arc_uid` for every already-placed arc. Review the returned `migrated`/`deleted`/`skipped` lists before trusting the result — this is a manual, audited run, not an automated one.
2. Track gh:#5446 (`cost_entries.epic_id`/`phase_id` live-write-path drift) as separate follow-up work — not part of this plan.

---

## Self-Review Notes

- **Spec coverage:** durable `arc_uid`/`phase_uid` columns (Task 1), rename-stability via `WHEN ... IS NULL` guard (Task 1, `test_rename_does_not_reassign_arc_uid`), new-goal-joins-existing-arc adoption (Task 1, `test_new_goal_joining_placed_arc_is_assigned_arc_uid`), view exposure (Task 1 Step 5, Task 2), `github_sync_map` migration call-site fix in `sync_arc` (Task 3) and the backfill join (Task 4), one-time data migration with the two documented known-bad rows (Task 5), the discovered view-recreation gap (Task 1 Step 6). `cost_entries` explicitly deferred to gh:#5446 per user decision.
- **Placeholder scan:** no TBD/TODO; every step has complete, runnable code.
- **Type consistency:** `arc_uid`/`phase_uid` are `TEXT` throughout (columns, trigger literals, `github_sync_map.entity_id`, migration function signatures) — no int/str mismatch across tasks. `sync_arc`'s public signature (`arc_id: int`) is unchanged, so `gh_sync_backfill.py`'s and `gh_sync_cli.py`'s existing call sites that pass `arc_id=arc_id` need no change; only the internal persistence target changed.
