import sqlite3

import synlynk
from synlynk import db


def _create_cost_test_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE)"
    )
    conn.execute(
        """CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arc_version TEXT, phase_title TEXT, status TEXT,
            priority TEXT, story_id TEXT, notes TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT,
            harness TEXT, agent_role TEXT, model TEXT, input_tokens INTEGER,
            output_tokens INTEGER, cache_read_tokens INTEGER, story_id TEXT,
            type_id TEXT, epic_id INTEGER, phase_id INTEGER, total_cost_usd REAL,
            api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT, notes TEXT,
            cost_source TEXT, estimate_basis TEXT, job_id TEXT,
            decision_revision INTEGER, recorded_at TEXT, dispatch_context TEXT,
            context_mode TEXT, turn_usage_json TEXT, session_id TEXT, pr_number INTEGER,
            estimated_input_tokens INTEGER, estimated_output_tokens INTEGER, estimated_cost_usd REAL
        )"""
    )
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, role TEXT)")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, role TEXT, context_mode TEXT, session_id TEXT)"
    )
    conn.execute("CREATE TABLE job_terminal_decision (job_id TEXT, revision INTEGER)")
    return conn


def test_insert_cost_row_resolves_epic_id_from_story_phase(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    conn = _create_cost_test_db(db_path)
    conn.execute("INSERT INTO roadmap_arcs (version) VALUES ('v1.0.0')")
    conn.execute(
        "INSERT INTO roadmap_phases (arc_version, phase_title, story_id) "
        "VALUES ('v1.0.0', 'Core cluster', 'story-abc')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(db_path))

    db._insert_cost_row(
        session_date="2026-10-29",
        agent="claude",
        story_id="story-abc",
        total_cost_usd=1.23,
        cost_source="actual",
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT epic_id, phase_id, estimate_basis FROM cost_entries WHERE story_id='story-abc'"
    ).fetchone()
    arc_id = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version='v1.0.0'"
    ).fetchone()[0]
    phase_id = conn.execute(
        "SELECT id FROM roadmap_phases WHERE story_id='story-abc'"
    ).fetchone()[0]
    conn.close()
    assert row == (arc_id, phase_id, None)


def test_insert_cost_row_marks_epic_id_unresolved_when_no_phase_match(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "state.db"
    conn = _create_cost_test_db(db_path)
    conn.execute("INSERT INTO stories (story_id) VALUES ('story-orphan')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(db_path))

    db._insert_cost_row(
        session_date="2026-10-29",
        agent="claude",
        story_id="story-orphan",
        total_cost_usd=1.0,
        cost_source="actual",
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT epic_id, phase_id, estimate_basis FROM cost_entries WHERE story_id='story-orphan'"
    ).fetchone()
    conn.close()
    assert row == (None, None, "epic_unresolved")
