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


def test_reclaim_stranded_story_with_lease(db_conn):
    # Acquire lease
    acquire_task_lease("story-lease-1", "dead-worker", duration_seconds=60, conn=db_conn)

    # Run reclaim (dead worker has no running daemon job)
    reclaimed = reclaim_stranded_stories(max_age_minutes=30, dry_run=False, conn=db_conn)
    assert len(reclaimed) == 1
    assert reclaimed[0]["story_id"] == "story-lease-1"

    row = db_conn.execute("SELECT status FROM stories WHERE story_id='story-lease-1'").fetchone()
    assert row[0] == "ready"

    active_lease = get_active_lease("story-lease-1", conn=db_conn)
    assert active_lease is None
