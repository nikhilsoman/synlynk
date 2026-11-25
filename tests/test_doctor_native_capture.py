import json
import sqlite3
import pytest

from synlynk import doctor
from synlynk import session_hooks as sh
from synlynk.migrations.m0041_native_session_capture import MIGRATION
from tests.native_capture_fixtures import assistant, write


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    settings_file = tmp_path / ".claude" / "settings.json"
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text(json.dumps(sh.merge_hooks({})))

    err_log = tmp_path / ".synlynk" / "native_capture_errors.log"
    monkeypatch.setattr(sh, "ERROR_LOG", err_log)

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True)

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

    monkeypatch.setattr(doctor, "_CLAUDE_SETTINGS_PATH", settings_file)
    monkeypatch.setattr(doctor, "_CLAUDE_PROJECTS_DIR", projects_dir)
    monkeypatch.setattr("synlynk._get_db", lambda *a, **k: sqlite3.connect(str(db_file)))
    return {"settings": settings_file, "projects": projects_dir, "db": db_file, "err_log": err_log}


def test_doctor_native_capture_ok_when_compliant(test_env):
    hc = doctor._hc_native_capture()
    assert hc.status == "ok"


def test_doctor_native_capture_fail_when_hooks_missing(test_env):
    test_env["settings"].write_text(json.dumps({}))
    hc = doctor._hc_native_capture()
    assert hc.status == "fail"
    assert "synlynk doctor --fix" in hc.fix


def test_doctor_native_capture_warn_when_error_log_has_content(test_env):
    test_env["err_log"].parent.mkdir(parents=True, exist_ok=True)
    test_env["err_log"].write_text("some error logged\n")
    hc = doctor._hc_native_capture()
    assert hc.status == "warn"


def test_doctor_native_capture_fail_when_uncaptured_transcripts(test_env):
    proj = test_env["projects"] / "-Users-n-dev-synlynk"
    proj.mkdir(parents=True)
    write(proj / "s1.jsonl", [assistant("m1")])
    hc = doctor._hc_native_capture()
    assert hc.status == "fail"
