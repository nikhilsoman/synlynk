import sqlite3
import pytest

from synlynk import cli
from synlynk.migrations.m0041_native_session_capture import MIGRATION
from tests.native_capture_fixtures import assistant, write


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("""CREATE TABLE cost_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, session_date TEXT NOT NULL,
        agent TEXT, harness TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER,
        total_cost_usd REAL, cost_source TEXT NOT NULL, estimate_basis TEXT, job_id TEXT, session_id TEXT,
        pr_number INTEGER, turn_usage_json TEXT, payment_mode TEXT, notes TEXT, story_id TEXT)""")
    conn.execute("CREATE TABLE sessions (session_id TEXT PRIMARY KEY, title TEXT, goal_id TEXT, status TEXT, opened_at TEXT)")
    MIGRATION.up(conn)
    conn.commit()
    conn.close()

    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(str(db_file)))
    return db_file


def test_cli_cost_capture_session_writes_row(test_db, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    res = cli.main(["cost", "capture-session", "--session", "s1", "--transcript", str(p)])
    assert res == 0
    conn = sqlite3.connect(str(test_db))
    rows = conn.execute("SELECT session_id, cost_source FROM cost_entries").fetchall()
    assert rows == [("s1", "transcript_derived")]


def test_cli_cost_capture_session_idempotent(test_db, tmp_path):
    p = write(tmp_path / "s1.jsonl", [assistant("m1")])
    cli.main(["cost", "capture-session", "--session", "s1", "--transcript", str(p)])
    cli.main(["cost", "capture-session", "--session", "s1", "--transcript", str(p)])
    conn = sqlite3.connect(str(test_db))
    count = conn.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0]
    assert count == 1


def test_cli_cost_capture_session_pending_sweep(test_db, tmp_path):
    base = tmp_path / "projects"
    native = base / "-Users-n-dev-synlynk"
    native.mkdir(parents=True)
    write(native / "s1.jsonl", [assistant("m1")])
    res = cli.main(["cost", "capture-session", "--pending", "--projects-dir", str(base)])
    assert res == 0
    conn = sqlite3.connect(str(test_db))
    rows = conn.execute("SELECT session_id FROM cost_entries").fetchall()
    assert rows == [("s1",)]


def test_cli_cost_link_session(test_db):
    res = cli.main(["cost", "link-session", "--session", "s1", "--pr", "5420", "--role", "implementer"])
    assert res == 0
    conn = sqlite3.connect(str(test_db))
    row = conn.execute("SELECT session_id, pr_number, role, source FROM session_pr_links").fetchone()
    assert row == ("s1", 5420, "implementer", "manual")


def test_cli_cost_capture_missing_transcript_fails(test_db, tmp_path, capsys):
    missing = tmp_path / "nonexistent.jsonl"
    res = cli.main(["cost", "capture-session", "--session", "s1", "--transcript", str(missing)])
    assert res == 1
    captured = capsys.readouterr()
    assert str(missing) in captured.err or str(missing) in captured.out
