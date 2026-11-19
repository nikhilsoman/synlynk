import sqlite3


def _cost_table(conn):
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT, agent TEXT, model TEXT,
            input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
            story_id TEXT, type_id TEXT, epic_id INTEGER, phase_id INTEGER,
            total_cost_usd REAL, api_equivalent_usd REAL, actual_usd REAL, payment_mode TEXT,
            notes TEXT, cost_source TEXT NOT NULL, estimate_basis TEXT, job_id TEXT,
            recorded_at TEXT, dispatch_context TEXT, context_mode TEXT, session_id TEXT,
            pr_number INTEGER, harness TEXT, agent_role TEXT, decision_revision INTEGER,
            turn_usage_json TEXT, estimated_input_tokens INTEGER, estimated_output_tokens INTEGER,
            estimated_cost_usd REAL, compaction_event_type TEXT, requested_harness TEXT
        )"""
    )


def test_insert_cost_row_persists_requested_harness(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    _cost_table(conn)
    conn.commit()
    conn.close()

    from synlynk.db import _insert_cost_row

    _insert_cost_row(
        session_date="2026-11-18", agent="agy", harness="agy",
        cost_source="actual", total_cost_usd=1.0, requested_harness="local",
        db_path=db_path,
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT requested_harness FROM cost_entries").fetchone()
    conn.close()
    assert row == ("local",)


def test_insert_cost_row_upsert_persists_requested_harness(tmp_path):
    db_path = str(tmp_path / "state.db")
    conn = sqlite3.connect(db_path)
    _cost_table(conn)
    conn.commit()
    conn.close()

    from synlynk.db import _insert_cost_row

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
    rows = conn.execute(
        "SELECT requested_harness FROM cost_entries WHERE job_id='job-1'"
    ).fetchall()
    conn.close()
    assert rows == [("local",)]


def test_write_capability_rating_persists_requested_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs("synlynk/state", exist_ok=True)

    import synlynk as sl
    from synlynk._constants import _role_dispatch_story_id

    monkeypatch.setattr(sl, "_sign_capability_rating", lambda data: "")
    conn = sl._get_db()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    if "requested_harness" not in columns:
        conn.execute("ALTER TABLE capability_ratings ADD COLUMN requested_harness TEXT")
    conn.commit()
    conn.close()
    job = {
        "story_id": "", "agent": "agy", "requested_harness": "local",
        "model_at_dispatch": "agy-model", "resolved_agent_role": "dev",
        "started_at": "2026-11-18T10:00:00", "ended_at": "2026-11-18T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }

    sl._write_capability_rating(job, "19 passed in 2.1s")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT requested_harness FROM capability_ratings WHERE story_id=?",
        (_role_dispatch_story_id("dev"),),
    ).fetchone()
    conn.close()
    assert row == ("local",)
