"""Unit tests for cost_entries estimate-vs-actual drift tracking (v0.26.9)."""

import synlynk as sl


def test_cost_entries_has_estimate_columns(tmp_path):
    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
        assert "estimated_input_tokens" in cols
        assert "estimated_output_tokens" in cols
        assert "estimated_cost_usd" in cols
    finally:
        conn.close()


import os

from synlynk.db import _insert_cost_row


def _seed_reservation(conn, job_id, tokens):
    conn.execute(
        "INSERT INTO harness_reservations (harness, tokens, scope, job_id, status) "
        "VALUES ('claude', ?, 'session', ?, 'open')",
        (tokens, job_id),
    )
    conn.commit()


def test_insert_cost_row_populates_estimate_from_reservation(tmp_path, monkeypatch):
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        _seed_reservation(conn, "job-drift-1", 10_000)
    finally:
        conn.close()

    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-8",
        input_tokens=10_000,
        output_tokens=2_000,
        cost_source="actual",
        total_cost_usd=0.19,
        actual_usd=0.19,
        job_id="job-drift-1",
    )

    conn = sl._get_db(str(db_file))
    try:
        row = conn.execute(
            "SELECT estimated_input_tokens, estimated_output_tokens, estimated_cost_usd "
            "FROM cost_entries WHERE job_id='job-drift-1'"
        ).fetchone()
        assert row[0] == 10_000
        assert row[1] == 0
        assert row[2] is not None and row[2] > 0.0
    finally:
        conn.close()


def test_insert_cost_row_fires_drift_alert_over_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        # Reservation estimated only 1,000 tokens.
        _seed_reservation(conn, "job-drift-2", 1_000)
    finally:
        conn.close()

    # Actual cost is wildly higher than what 1,000 tokens would predict.
    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-8",
        input_tokens=50_000,
        output_tokens=10_000,
        cost_source="actual",
        total_cost_usd=0.90,
        actual_usd=0.90,
        job_id="job-drift-2",
    )

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_path.exists()
    assert "COST_ESTIMATE_DRIFT" in sentinel_path.read_text()


def test_insert_cost_row_no_alert_within_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    db_file = tmp_path / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_file))
    conn = sl._get_db(str(db_file))
    try:
        _seed_reservation(conn, "job-drift-3", 10_000)
    finally:
        conn.close()

    _insert_cost_row(
        session_date="2026-10-31",
        agent="claude",
        harness="claude",
        model="claude-opus-4-8",
        input_tokens=10_500,
        output_tokens=2_000,
        cost_source="actual",
        total_cost_usd=0.19,
        actual_usd=0.19,
        job_id="job-drift-3",
    )

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert not sentinel_path.exists() or "COST_ESTIMATE_DRIFT" not in sentinel_path.read_text()

