import sqlite3
import pytest
from synlynk.db import cmd_decision_record
from synlynk.db_schema import ensure_derived_roadmap_views


def test_decision_record_places_goal_into_derived_roadmap(tmp_path, monkeypatch):
    """Verify that cmd_decision_record with arc, phase, and priority places the goal into derived roadmap views."""
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # Create base tables
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
        date TEXT NOT NULL,
        panel TEXT,
        status TEXT,
        inputs TEXT,
        synthesis TEXT,
        decision_text TEXT NOT NULL,
        signature TEXT,
        goal_id TEXT
    );
    """)

    # Seed an unplaced goal
    conn.execute(
        "INSERT INTO goals (id, goal_id, outcome, criterion, placement_status) "
        "VALUES (1, 'goal-ibpd', 'IBPD Engine', 'Works', 'unplaced')"
    )
    conn.commit()

    # Monkeypatch _get_db and file writers
    monkeypatch.setattr("synlynk._get_db", lambda: sqlite3.connect(str(db_file)))
    monkeypatch.setattr("synlynk.db._get_db", lambda: sqlite3.connect(str(db_file)))
    monkeypatch.setattr("synlynk.team._sign_capability_rating", lambda r: "mock-sig")
    monkeypatch.setattr("synlynk.events.emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("synlynk.db._write_decision_record_md", lambda *args, **kwargs: "mock-slug")

    # Record decision with placement flags
    slug = cmd_decision_record(
        decision_id="dec-test-1",
        topic="Adopt IBPD Engine",
        date="2026-11-14",
        panel=["claude", "agy"],
        inputs={"claude": "agree"},
        synthesis="Consensus reached",
        decision_text="Ship Track 4",
        goal_id="goal-ibpd",
        arc="v0.36.0",
        phase="Phase 1 - IBPD",
        priority=1,
    )

    assert slug is not None

    # Check goal updated
    goal = conn.execute("SELECT * FROM goals WHERE goal_id = 'goal-ibpd'").fetchone()
    assert goal["placement_status"] == "placed"
    assert goal["arc_version"] == "v0.36.0"
    assert goal["phase_title"] == "Phase 1 - IBPD"
    assert goal["roadmap_priority"] == 1

    # Check views reflect placed goal
    ensure_derived_roadmap_views(conn)
    arc = conn.execute("SELECT * FROM roadmap_arcs WHERE version = 'v0.36.0'").fetchone()
    assert arc is not None
    assert arc["version"] == "v0.36.0"
    assert arc["status"] == "in_progress"
    assert "Ship Track 4" in arc["notes"]

    conn.close()
