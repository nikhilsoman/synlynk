import os

import pytest

from synlynk import _get_db
from synlynk.jobs import acquire_task_lease, get_active_lease


@pytest.fixture
def db_conn(tmp_path):
    conn = _get_db(db_path=str(tmp_path / "test_claim.db"))
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-claim-1', 'Claim test story', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    return conn


def test_story_claim_blocks_second_session(db_conn):
    # Simulate a live holder (this test process's own PID is alive).
    first = acquire_task_lease(
        "story-claim-1", "claude:host:111", pid=os.getpid(), harness="claude",
        conn=db_conn,
    )
    assert first["acquired"] is True

    second = acquire_task_lease(
        "story-claim-1", "codex:host:222", pid=os.getpid(), harness="codex",
        conn=db_conn,
    )
    assert second["acquired"] is False
    assert second["harness"] == "claude"


def test_story_claim_override_takes_lease(db_conn):
    acquire_task_lease(
        "story-claim-1", "claude:host:111", pid=os.getpid(), harness="claude",
        conn=db_conn,
    )

    overridden = acquire_task_lease(
        "story-claim-1", "codex:host:222", pid=os.getpid(), harness="codex",
        override=True, conn=db_conn,
    )
    assert overridden["acquired"] is True

    lease = get_active_lease("story-claim-1", conn=db_conn)
    assert lease["harness"] == "codex"


def test_cmd_story_claim_via_cli_handler(tmp_path, monkeypatch):
    """Exercise the actual cmd_story_claim CLI handler (not just acquire_task_lease).

    cmd_story_claim calls acquire_task_lease() with no `conn` kwarg, so it
    resolves its own connection via `synlynk._get_db()`. Point that at an
    isolated file-backed DB via SYNLYNK_STATE_DB_PATH (the real override env
    var honored by _get_db — not SYNLYNK_DB_PATH, which doesn't exist) so
    this stays deterministic and isolated like the rest of the suite.
    """
    from synlynk import jobs as jobs_module

    db_path = str(tmp_path / "test_claim_cli.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)

    setup_conn = _get_db(db_path=db_path)
    setup_conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-claim-cli-1', 'Claim CLI test story', 'dev', 'open', 'ready', 'ready')
    """)
    setup_conn.commit()
    setup_conn.close()

    exit_code = jobs_module.cmd_story_claim(
        "story-claim-cli-1", harness="claude", duration_seconds=60,
    )
    assert exit_code == 0

    lease = get_active_lease("story-claim-cli-1")
    assert lease is not None
    assert lease["harness"] == "claude"

    # A second claim by a different harness should be refused (exit code 1),
    # since the first session's PID (this test process) is alive.
    second_exit_code = jobs_module.cmd_story_claim(
        "story-claim-cli-1", harness="codex", duration_seconds=60,
    )
    assert second_exit_code == 1
