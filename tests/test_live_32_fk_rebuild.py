"""Reproduction and regression test for LIVE-32 (#5274).

sqlite3.OperationalError: foreign key mismatch - "goals" referencing "roadmap_phases"
"""

import sqlite3
import pytest
from synlynk.db import _migrate_remove_roadmap_foreign_keys
from synlynk.db_schema import ensure_derived_roadmap_views


def test_migrate_remove_roadmap_foreign_keys_table_rebuild(tmp_path):
    """Verify legacy goals and cost_entries tables referencing roadmap_phases/arcs are safely rebuilt."""
    db_path = tmp_path / "legacy_state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # 1. Create legacy roadmap tables
    conn.execute(
        """CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            title TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT NOT NULL REFERENCES roadmap_arcs(version),
            phase_title TEXT NOT NULL
        )"""
    )
    # 2. Create legacy goals and cost_entries with foreign keys
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT NOT NULL UNIQUE,
            outcome TEXT NOT NULL,
            criterion TEXT NOT NULL,
            phase_id INTEGER REFERENCES roadmap_phases(id),
            status TEXT DEFAULT 'active',
            kind TEXT DEFAULT 'feature'
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_source TEXT NOT NULL,
            epic_id INTEGER REFERENCES roadmap_arcs(id),
            phase_id INTEGER REFERENCES roadmap_phases(id),
            total_cost_usd REAL
        )"""
    )

    # Insert sample rows
    conn.execute("INSERT INTO roadmap_arcs (version, title) VALUES ('v1.0.0', 'Release 1')")
    conn.execute("INSERT INTO roadmap_phases (arc_version, phase_title) VALUES ('v1.0.0', 'Phase 1')")
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, phase_id) VALUES ('goal-1', 'Outcome 1', 'Crit 1', 1)"
    )
    conn.execute(
        "INSERT INTO cost_entries (cost_source, epic_id, phase_id, total_cost_usd) VALUES ('manual', 1, 1, 0.5)"
    )
    conn.commit()

    # 3. Migrate derived roadmap views
    ensure_derived_roadmap_views(conn)
    conn.commit()

    # Verify trg_roadmap_phases_update trigger exists
    trg = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_roadmap_phases_update'"
    ).fetchone()
    assert trg is not None

    # Run migration / table rebuild
    _migrate_remove_roadmap_foreign_keys(conn)
    conn.commit()

    # 4. Now execute an INSERT INTO goals and cost_entries with foreign keys enabled
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-new', 'New Outcome', 'New Criterion')"
    )
    conn.execute(
        "INSERT INTO cost_entries (cost_source, total_cost_usd) VALUES ('claude', 1.25)"
    )
    conn.commit()

    # Verify rows preserved
    row = conn.execute("SELECT outcome, phase_id FROM goals WHERE goal_id='goal-1'").fetchone()
    assert row == ("Outcome 1", 1)

    cost_row = conn.execute("SELECT cost_source, epic_id, phase_id FROM cost_entries WHERE cost_source='manual'").fetchone()
    assert cost_row == ("manual", 1, 1)

    # Verify SQL schema has no references to roadmap_phases or roadmap_arcs
    goals_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'").fetchone()[0]
    assert "REFERENCES roadmap_phases" not in goals_sql

    costs_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cost_entries'").fetchone()[0]
    assert "REFERENCES roadmap_phases" not in costs_sql
    assert "REFERENCES roadmap_arcs" not in costs_sql

    # Verify PRAGMA foreign_key_list reports no references to roadmap views
    fks_goals = conn.execute("PRAGMA foreign_key_list(goals)").fetchall()
    assert not any(fk[2] in ("roadmap_phases", "roadmap_arcs") for fk in fks_goals)

    fks_costs = conn.execute("PRAGMA foreign_key_list(cost_entries)").fetchall()
    assert not any(fk[2] in ("roadmap_phases", "roadmap_arcs") for fk in fks_costs)

    conn.close()


def test_migrate_when_view_and_triggers_already_exist(tmp_path):
    """Specifically verify that pre-existing view triggers do not cause trigger collision errors during rebuild."""
    db_path = tmp_path / "trigger_collision_state.db"
    conn = sqlite3.connect(db_path)

    # Create goals with legacy FK
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT NOT NULL UNIQUE,
            outcome TEXT NOT NULL,
            criterion TEXT NOT NULL,
            phase_id INTEGER REFERENCES roadmap_phases(id),
            status TEXT DEFAULT 'active'
        )"""
    )
    # Pre-create the view and trigger that caused DROP COLUMN / table-rename errors
    conn.execute("CREATE VIEW roadmap_phases AS SELECT 1 AS id, 'v1.0.0' AS arc_version, 'Phase 1' AS phase_title")
    conn.execute(
        """CREATE TRIGGER trg_roadmap_phases_update INSTEAD OF UPDATE ON roadmap_phases
        BEGIN
            UPDATE goals SET status = 'done' WHERE phase_id = OLD.id;
        END"""
    )
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion, phase_id) VALUES ('goal-pre', 'Out', 'Crit', 1)")
    conn.commit()

    # Rebuilding goals must succeed without trigger errors
    _migrate_remove_roadmap_foreign_keys(conn)
    conn.commit()

    # Enable FKs and verify insertion succeeds
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-post', 'Out Post', 'Crit Post')")
    conn.commit()

    rows = conn.execute("SELECT goal_id, outcome FROM goals ORDER BY id").fetchall()
    assert rows == [("goal-pre", "Out"), ("goal-post", "Out Post")]

    conn.close()


def test_ensure_derived_roadmap_views_idempotence(tmp_path):
    """Verify that multiple consecutive calls to ensure_derived_roadmap_views are completely idempotent."""
    db_path = tmp_path / "idempotent_state.db"
    conn = sqlite3.connect(db_path)

    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT NOT NULL UNIQUE,
            outcome TEXT NOT NULL,
            criterion TEXT NOT NULL,
            phase_id INTEGER,
            status TEXT DEFAULT 'active'
        )"""
    )
    conn.commit()

    ensure_derived_roadmap_views(conn)
    ensure_derived_roadmap_views(conn)
    ensure_derived_roadmap_views(conn)
    conn.commit()

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO goals (goal_id, outcome, criterion) VALUES ('goal-idem', 'Out', 'Crit')")
    conn.commit()

    assert conn.execute("SELECT goal_id FROM goals WHERE goal_id='goal-idem'").fetchone() == ("goal-idem",)
    conn.close()
