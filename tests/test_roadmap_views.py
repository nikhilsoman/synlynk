import sqlite3
import pytest
from synlynk.db_schema import ensure_derived_roadmap_views


def test_derived_roadmap_views_creation_and_query(tmp_path):
    """Verify that roadmap_arcs and roadmap_phases views derive status and notes from goals and decisions."""
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # Create base schema
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

    # Populate goals across two arcs
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline, status, placement_status, arc_version, phase_title, roadmap_priority) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("goal-1", "Feature A", "Passes", "2026-12-01", "done", "placed", "v0.35.0", "Phase 1 - Core", 1)
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline, status, placement_status, arc_version, phase_title, roadmap_priority) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("goal-2", "Feature B", "Passes", "2026-12-15", "active", "placed", "v0.35.0", "Phase 2 - Expansion", 2)
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, deadline, status, placement_status, arc_version, phase_title, roadmap_priority) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("goal-3", "Feature C", "Passes", "2027-01-01", "done", "placed", "v0.36.0", "Phase 1 - Engine", 1)
    )

    # Decisions linked to goals
    conn.execute(
        "INSERT INTO decisions (decision_id, topic, decision_text, goal_id) VALUES (?, ?, ?, ?)",
        ("dec-1", "Architecture", "Adopt Approach C", "1")
    )

    # Create the derived views
    ensure_derived_roadmap_views(conn)

    # Verify roadmap_arcs view
    arcs = conn.execute("SELECT * FROM roadmap_arcs ORDER BY version ASC").fetchall()
    assert len(arcs) == 2

    # v0.35.0 has one done and one active -> computed status = in_progress
    arc35 = arcs[0]
    assert arc35["version"] == "v0.35.0"
    assert arc35["status"] == "in_progress"
    assert arc35["target_date"] == "2026-12-01"
    assert "Adopt Approach C" in (arc35["notes"] or "")

    # v0.36.0 has one goal, done -> computed status = shipped
    arc36 = arcs[1]
    assert arc36["version"] == "v0.36.0"
    assert arc36["status"] == "shipped"

    # Verify roadmap_phases view
    phases = conn.execute("SELECT * FROM roadmap_phases ORDER BY arc_version, priority").fetchall()
    assert len(phases) == 3
    assert phases[0]["phase_title"] == "Phase 1 - Core"
    assert phases[0]["status"] == "shipped"
    assert phases[1]["phase_title"] == "Phase 2 - Expansion"
    assert phases[1]["status"] == "in_progress"

    conn.close()
