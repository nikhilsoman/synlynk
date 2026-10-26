import os
import json
import pytest

from synlynk import _get_db
from synlynk.jobs import get_active_lease, acquire_task_lease
from synlynk.session import _read_active_claims


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_story_claims.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    # Also isolate active claims marker
    claims_file = str(tmp_path / "active_claims.json")
    monkeypatch.setattr("synlynk.session._active_claims_path", lambda: claims_file)

    conn = _get_db(db_path=db_path)
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-claim-auto-1', 'Auto claim test story', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    return conn


def test_story_update_in_progress_acquires_lease(db_conn, tmp_path):
    from synlynk.cli import cmd_story_update

    res = cmd_story_update("story-claim-auto-1", status="in_progress", harness="agy")
    assert res == 0

    lease = get_active_lease("story-claim-auto-1", conn=db_conn)
    assert lease is not None
    assert lease["status"] == "active"
    assert lease["harness"] == "agy"

    # Verify story status transitioned
    row = db_conn.execute("SELECT status, readiness FROM stories WHERE story_id='story-claim-auto-1'").fetchone()
    assert row[0] == "in_progress"
    assert row[1] == "in_progress"

    # Verify active_claims marker
    active_claims = _read_active_claims()
    assert "story-claim-auto-1" in active_claims


def test_story_update_in_progress_conflict_rejected(db_conn, tmp_path):
    from synlynk.cli import cmd_story_update

    # Pre-seed active claim with current live PID
    first = acquire_task_lease(
        "story-claim-auto-1", "claude:testhost:111", pid=os.getpid(), harness="claude", conn=db_conn
    )
    assert first["acquired"] is True

    # Attempting to move story to in_progress by another session should fail
    res = cmd_story_update("story-claim-auto-1", status="in_progress", harness="codex", override=False)
    assert res == 1

    # Lease still belongs to claude
    lease = get_active_lease("story-claim-auto-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "claude"


def test_story_update_in_progress_override_transfers_lease(db_conn, tmp_path):
    from synlynk.cli import cmd_story_update

    # Pre-seed active claim
    acquire_task_lease(
        "story-claim-auto-1", "claude:testhost:111", pid=os.getpid(), harness="claude", conn=db_conn
    )

    # Move with override=True
    res = cmd_story_update("story-claim-auto-1", status="in_progress", harness="codex", override=True)
    assert res == 0

    lease = get_active_lease("story-claim-auto-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "codex"


def test_story_update_cli_invocation(db_conn, tmp_path):
    from synlynk.cli import main

    exit_code = None
    try:
        main(["story", "update", "story-claim-auto-1", "--status", "in_progress", "--harness", "agy"])
        exit_code = 0
    except SystemExit as e:
        exit_code = e.code

    assert exit_code in (0, None)
    lease = get_active_lease("story-claim-auto-1", conn=db_conn)
    assert lease is not None
    assert lease["harness"] == "agy"

