import sqlite3

from synlynk.db import _insert_cost_row

_COST_ENTRIES_SCHEMA = """
    CREATE TABLE cost_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT, model TEXT,
        input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
        story_id TEXT, type_id TEXT, epic_id INTEGER, phase_id INTEGER,
        total_cost_usd REAL, api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT,
        notes TEXT, cost_source TEXT NOT NULL, estimate_basis TEXT, job_id TEXT,
        recorded_at TEXT, dispatch_context TEXT, context_mode TEXT, session_id TEXT,
        pr_number INTEGER, harness TEXT, agent_role TEXT, decision_revision INTEGER,
        turn_usage_json TEXT, estimated_input_tokens INTEGER, estimated_output_tokens INTEGER,
        estimated_cost_usd REAL, compaction_event_type TEXT,
        requested_harness TEXT
    )
"""


def test_insert_cost_row_persists_requested_harness(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(_COST_ENTRIES_SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(db_path))
    _insert_cost_row(
        session_date="2026-11-18", agent="agy", harness="agy",
        cost_source="actual", total_cost_usd=1.0, requested_harness="local",
        db_path=db_path,
    )
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT requested_harness FROM cost_entries").fetchone()
    assert row[0] == "local"


def test_insert_cost_row_upsert_path_also_persists_requested_harness(tmp_path, monkeypatch):
    """_insert_cost_row has a separate UPDATE path for an existing job_id row;
    it must thread requested_harness too, not just the INSERT path."""
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute(_COST_ENTRIES_SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(db_path))
    _insert_cost_row(
        session_date="2026-11-18", agent="agy", harness="agy", job_id="job-1",
        cost_source="actual", total_cost_usd=1.0, requested_harness="local",
        db_path=db_path,
    )
    _insert_cost_row(
        session_date="2026-11-18", agent="agy", harness="agy", job_id="job-1",
        cost_source="actual", total_cost_usd=2.0, requested_harness="local",
        db_path=db_path,
    )
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT requested_harness FROM cost_entries WHERE job_id='job-1'").fetchall()
    assert len(rows) == 1, "second call with the same job_id must UPDATE, not INSERT a second row"
    assert rows[0][0] == "local"
