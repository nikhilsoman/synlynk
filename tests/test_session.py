import json
import os

import pytest


def test_write_and_read_active_session(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _active_session_path

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    _write_active_session("session-abc12345")

    assert os.path.exists(_active_session_path())
    assert _read_active_session() == "session-abc12345"


def test_read_active_session_returns_none_when_absent(tmp_path, monkeypatch):
    from synlynk.session import _read_active_session

    monkeypatch.chdir(tmp_path)
    assert _read_active_session() is None


def test_clear_active_session_removes_marker(tmp_path, monkeypatch):
    from synlynk.session import _write_active_session, _read_active_session, _clear_active_session

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    _write_active_session("session-abc12345")
    _clear_active_session()

    assert _read_active_session() is None


import sqlite3


def test_cmd_session_open_creates_row_and_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open
    from synlynk.session import _read_active_session
    from synlynk import _get_db

    session_id = cmd_session_open("Investigate flaky Codex GH-write routing")

    assert session_id.startswith("session-")
    assert _read_active_session() == session_id

    conn = _get_db()
    row = conn.execute(
        "SELECT title, status FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    assert row == ("Investigate flaky Codex GH-write routing", "open")


def test_cmd_session_close_sets_disposition_and_clears_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_close
    from synlynk.session import _read_active_session
    from synlynk import _get_db

    session_id = cmd_session_open("Ship v0.14.0")
    cmd_session_close(disposition="goal_progress", summary="Shipped GOVERNS event extension")

    assert _read_active_session() is None
    conn = _get_db()
    row = conn.execute(
        "SELECT status, disposition, closing_summary FROM sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    assert row == ("closed", "goal_progress", "Shipped GOVERNS event extension")


def test_cmd_session_close_rejects_invalid_disposition(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_close

    cmd_session_open("Explore quota routing options")
    with pytest.raises(ValueError):
        cmd_session_close(disposition="not_a_real_disposition")


def test_migrate_db_adds_session_id_to_jobs_and_devlog(tmp_path, monkeypatch):
    """Existing DBs lack session_id; status/checkpoint query it (PR #940 sequencing gap)."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, "
        "status TEXT, enqueued_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE devlog_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "author TEXT NOT NULL, entry_date TEXT NOT NULL, session_title TEXT, "
        "body TEXT NOT NULL, recorded_at TEXT)"
    )
    sl._migrate_db(conn)
    job_cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    devlog_cols = {row[1] for row in conn.execute("PRAGMA table_info(devlog_entries)")}
    sl._migrate_db(conn)  # idempotent
    conn.close()
    assert "session_id" in job_cols
    assert "session_id" in devlog_cols


def test_cmd_session_status_and_checkpoint_tolerate_unpopulated_session_id(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    from synlynk.db import cmd_session_open, cmd_session_status, cmd_session_checkpoint

    cmd_session_open("smoke test")
    cmd_session_status()
    status_out = capsys.readouterr().out
    assert "Jobs attributed: 0" in status_out
    assert "Devlog entries: 0" in status_out

    cmd_session_checkpoint()
    checkpoint_out = capsys.readouterr().out
    assert "Jobs attributed to this session: 0" in checkpoint_out
    assert "Devlog entries linked: 0" in checkpoint_out
