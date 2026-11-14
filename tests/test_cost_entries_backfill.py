import sqlite3
import pytest
from synlynk.roadmap_migration import backfill_cost_entries_goals


def test_cost_entries_backfill_unambiguous_and_ambiguous(tmp_path):
    """Verify that cost_entries phase_id is backfilled to goals.id, with ambiguities reported."""
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
    CREATE TABLE goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id TEXT NOT NULL UNIQUE,
        arc_version TEXT,
        phase_title TEXT,
        placement_status TEXT DEFAULT 'placed'
    );

    CREATE TABLE roadmap_phases_legacy (
        id INTEGER PRIMARY KEY,
        arc_version TEXT,
        phase_title TEXT
    );

    CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phase_id INTEGER,
        goal_fk_id INTEGER
    );
    """)

    # Populate legacy phases
    # Phase 1: Unambiguous (1 goal)
    conn.execute("INSERT INTO roadmap_phases_legacy (id, arc_version, phase_title) VALUES (1, 'v0.33.0', 'Editions')")
    conn.execute("INSERT INTO goals (id, goal_id, arc_version, phase_title) VALUES (10, 'goal-editions', 'v0.33.0', 'Editions')")

    # Phase 2: Ambiguous (2 goals share arc and phase)
    conn.execute("INSERT INTO roadmap_phases_legacy (id, arc_version, phase_title) VALUES (2, 'v0.34.0', 'Constitution')")
    conn.execute("INSERT INTO goals (id, goal_id, arc_version, phase_title) VALUES (20, 'goal-const-1', 'v0.34.0', 'Constitution')")
    conn.execute("INSERT INTO goals (id, goal_id, arc_version, phase_title) VALUES (21, 'goal-const-2', 'v0.34.0', 'Constitution')")

    # Insert cost entries
    conn.execute("INSERT INTO cost_entries (id, phase_id) VALUES (101, 1)")
    conn.execute("INSERT INTO cost_entries (id, phase_id) VALUES (102, 2)")

    # Run backfill
    report = backfill_cost_entries_goals(conn)

    # Verify unambiguous backfill
    row1 = conn.execute("SELECT phase_id FROM cost_entries WHERE id = 101").fetchone()
    assert row1["phase_id"] == 10

    # Verify deterministic tie-break for ambiguous (lowest goals.id wins: 20)
    row2 = conn.execute("SELECT phase_id FROM cost_entries WHERE id = 102").fetchone()
    assert row2["phase_id"] == 20

    # Verify report records the ambiguity
    assert len(report["ambiguous_phases"]) == 1
    ambig = report["ambiguous_phases"][0]
    assert ambig["legacy_phase_id"] == 2
    assert ambig["candidate_goal_ids"] == [20, 21]

    conn.close()
