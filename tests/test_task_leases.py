import os

import pytest
import sqlite3
import time

from synlynk import _get_db
from synlynk.jobs import (
    acquire_task_lease,
    renew_task_lease,
    release_task_lease,
    get_active_lease,
    reclaim_stranded_stories,
)


@pytest.fixture
def db_conn(tmp_path):
    conn = _get_db(db_path=str(tmp_path / "test_leases.db"))
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-lease-1', 'Distributed mesh relay handler', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    return conn


def test_acquire_and_get_task_lease(db_conn):
    res = acquire_task_lease("story-lease-1", "worker-codex-1", duration_seconds=60, conn=db_conn)
    assert res["acquired"] is True
    assert res["story_id"] == "story-lease-1"
    assert res["leased_by"] == "worker-codex-1"

    lease = get_active_lease("story-lease-1", conn=db_conn)
    assert lease is not None
    assert lease["leased_by"] == "worker-codex-1"
    assert lease["status"] == "active"

    # Story status in DB should be in_progress
    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "in_progress"


def test_concurrent_lease_conflict(db_conn):
    acquire_task_lease("story-lease-1", "worker-codex-1", duration_seconds=600, conn=db_conn)

    # Worker 2 attempts to acquire same active lease
    conflict = acquire_task_lease("story-lease-1", "worker-agy-2", duration_seconds=600, conn=db_conn)
    assert conflict["acquired"] is False
    assert conflict["reason"] == "already_leased"
    assert conflict["leased_by"] == "worker-codex-1"


def test_renew_task_lease(db_conn):
    acquire_task_lease("story-lease-1", "worker-codex-1", duration_seconds=10, conn=db_conn)
    initial_lease = get_active_lease("story-lease-1", conn=db_conn)

    time.sleep(1)
    renewed = renew_task_lease("story-lease-1", "worker-codex-1", extend_seconds=120, conn=db_conn)
    assert renewed is True

    updated_lease = get_active_lease("story-lease-1", conn=db_conn)
    assert updated_lease["expires_at"] > initial_lease["expires_at"]


def test_release_task_lease(db_conn):
    acquire_task_lease("story-lease-1", "worker-codex-1", duration_seconds=60, conn=db_conn)
    released = release_task_lease("story-lease-1", "worker-codex-1", new_status="done", conn=db_conn)
    assert released is True

    active = get_active_lease("story-lease-1", conn=db_conn)
    assert active is None

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "done"


def test_dead_pid_claim_does_not_block_new_claim(db_conn):
    # Simulate a crashed session: a PID that is guaranteed not to exist.
    dead_pid = 999999
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=dead_pid, harness="claude", conn=db_conn,
    )

    result = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", conn=db_conn,
    )
    assert result["acquired"] is True


def test_live_pid_claim_blocks_new_claim_without_override(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    conflict = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", conn=db_conn,
    )
    assert conflict["acquired"] is False
    assert conflict["reason"] == "already_leased"
    assert conflict["harness"] == "claude"


def test_override_bypasses_live_claim(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    result = acquire_task_lease(
        "story-lease-1", "codex:session-b", duration_seconds=600,
        pid=os.getpid(), harness="codex", override=True, conn=db_conn,
    )
    assert result["acquired"] is True


def test_task_leases_table_has_pid_and_harness_columns(db_conn):
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(task_leases)")}
    assert "pid" in cols
    assert "harness" in cols


def test_get_active_lease_includes_harness_and_pid(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:session-a", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )
    lease = get_active_lease("story-lease-1", conn=db_conn)
    assert lease["harness"] == "claude"
    assert lease["pid"] == os.getpid()


def test_reclaim_stranded_story_with_lease(db_conn):
    # Acquire lease with an explicitly dead PID (dead worker scenario)
    acquire_task_lease("story-lease-1", "dead-worker", duration_seconds=60, pid=999999, conn=db_conn)

    # Run reclaim (dead worker has no running daemon job, and its claim PID is dead)
    reclaimed = reclaim_stranded_stories(max_age_minutes=30, dry_run=False, conn=db_conn)
    assert len(reclaimed) == 1
    assert reclaimed[0]["story_id"] == "story-lease-1"

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "ready"

    active_lease = get_active_lease("story-lease-1", conn=db_conn)
    assert active_lease is None


def test_reclaim_leaves_live_interactive_claim_alone(db_conn):
    # A live interactive claim (no daemon job at all) must NOT be reclaimed.
    acquire_task_lease(
        "story-lease-1", "claude:host:live", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    reclaimed = reclaim_stranded_stories(max_age_minutes=30, dry_run=False, conn=db_conn)
    assert reclaimed == []

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "in_progress"


def test_heartbeat_all_claims_for_pid(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:host:999", duration_seconds=10,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )
    before = get_active_lease("story-lease-1", conn=db_conn)

    time.sleep(1)
    from synlynk.jobs import heartbeat_claims_for_pid
    count = heartbeat_claims_for_pid(os.getpid(), extend_seconds=120, conn=db_conn)
    assert count == 1

    after = get_active_lease("story-lease-1", conn=db_conn)
    assert after["heartbeat_at"] > before["heartbeat_at"]


def test_story_done_releases_active_claim(db_conn):
    acquire_task_lease(
        "story-lease-1", "claude:host:1", duration_seconds=600,
        pid=os.getpid(), harness="claude", conn=db_conn,
    )

    from synlynk.db import cmd_story_done
    cmd_story_done("story-lease-1", conn=db_conn)

    row = db_conn.execute(
        "SELECT status FROM task_leases WHERE story_id='story-lease-1' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "released"


def test_story_done_clears_tracked_active_claim(db_conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    from synlynk.session import _add_active_claim, _read_active_claims
    from synlynk.db import cmd_story_done

    _add_active_claim("story-lease-1")
    cmd_story_done("story-lease-1", conn=db_conn)

    assert "story-lease-1" not in _read_active_claims()


def test_heartbeat_by_story_ids_renews_across_simulated_process_boundary(db_conn, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    from synlynk.session import _add_active_claim, _read_active_claims
    from synlynk.jobs import heartbeat_claims_by_story_ids, get_active_lease

    # Simulate the one-shot `story claim` process: takes the lease with its own PID,
    # then "exits" (we never heartbeat using that PID again in this test).
    acquire_task_lease(
        "story-lease-1", "claude:host:555", duration_seconds=10,
        pid=999999, harness="claude", conn=db_conn,
    )
    _add_active_claim("story-lease-1")
    before = get_active_lease("story-lease-1", conn=db_conn)

    time.sleep(1)
    # Simulate a later, unrelated `synlynk exec` process (different PID, same checkout):
    count = heartbeat_claims_by_story_ids(_read_active_claims(), extend_seconds=120, conn=db_conn)
    assert count == 1

    after = get_active_lease("story-lease-1", conn=db_conn)
    assert after["heartbeat_at"] > before["heartbeat_at"]
