"""Tests for synlynk.worktree_lease: Leased worktree locks with TTL and dead-PID reclamation."""

import json
import os
import sqlite3
import time
import pytest
from unittest.mock import patch

from synlynk.worktree_lease import (
    acquire_worktree_lease,
    renew_worktree_lease,
    release_worktree_lease,
    get_active_worktree_lease,
    audit_and_reclaim_stale_worktree_leases,
    init_worktree_lease_schema,
)
from synlynk.wal_ledger import ensure_wal_pragmas


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    ensure_wal_pragmas(conn)
    init_worktree_lease_schema(conn)
    yield conn
    conn.close()


def test_acquire_worktree_lease_success(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-1"
    wt_path.mkdir(parents=True)

    res = acquire_worktree_lease(
        str(wt_path),
        leased_by="codex",
        job_id="job-1",
        pid=os.getpid(),
        duration_seconds=600,
        conn=db_conn,
    )

    assert res["acquired"] is True
    assert res["leased_by"] == "codex"
    assert res["job_id"] == "job-1"

    # Verify on-disk lease JSON
    lease_file = wt_path / ".synlynk" / "lease.json"
    assert lease_file.exists()
    data = json.loads(lease_file.read_text())
    assert data["leased_by"] == "codex"
    assert data["job_id"] == "job-1"
    assert data["pid"] == os.getpid()

    # Verify DB query
    lease = get_active_worktree_lease(str(wt_path), conn=db_conn)
    assert lease is not None
    assert lease["leased_by"] == "codex"
    assert lease["status"] == "active"


def test_acquire_worktree_lease_conflict_when_active_and_pid_alive(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-conflict"
    wt_path.mkdir(parents=True)

    with patch("synlynk.worktree_lease._is_pid_alive", return_value=True):
        res1 = acquire_worktree_lease(
            str(wt_path),
            leased_by="codex",
            job_id="job-1",
            pid=12345,
            duration_seconds=600,
            conn=db_conn,
        )
        assert res1["acquired"] is True

        res2 = acquire_worktree_lease(
            str(wt_path),
            leased_by="agy",
            job_id="job-2",
            pid=54321,
            duration_seconds=600,
            conn=db_conn,
        )
        assert res2["acquired"] is False
        assert res2["reason"] == "already_leased"
        assert res2["leased_by"] == "codex"


def test_acquire_worktree_lease_steals_when_pid_is_dead(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-dead"
    wt_path.mkdir(parents=True)

    # First lease acquired by a PID that later dies
    with patch("synlynk.worktree_lease._is_pid_alive", return_value=True):
        res1 = acquire_worktree_lease(
            str(wt_path),
            leased_by="codex",
            job_id="job-old",
            pid=99999,
            duration_seconds=600,
            conn=db_conn,
        )
        assert res1["acquired"] is True

    # When PID 99999 is dead, new agent acquires
    with patch("synlynk.worktree_lease._is_pid_alive", return_value=False):
        res2 = acquire_worktree_lease(
            str(wt_path),
            leased_by="agy",
            job_id="job-new",
            pid=os.getpid(),
            duration_seconds=600,
            conn=db_conn,
        )
        assert res2["acquired"] is True
        assert res2["leased_by"] == "agy"
        assert res2.get("stolen_from_dead_pid") is True


def test_acquire_worktree_lease_steals_when_ttl_expired(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-expired"
    wt_path.mkdir(parents=True)

    # First lease acquired with negative/expired duration
    res1 = acquire_worktree_lease(
        str(wt_path),
        leased_by="codex",
        job_id="job-old",
        pid=os.getpid(),
        duration_seconds=-10,
        conn=db_conn,
    )
    assert res1["acquired"] is True

    # Second agent acquires since TTL expired
    res2 = acquire_worktree_lease(
        str(wt_path),
        leased_by="agy",
        job_id="job-new",
        pid=os.getpid(),
        duration_seconds=600,
        conn=db_conn,
    )
    assert res2["acquired"] is True
    assert res2["leased_by"] == "agy"


def test_renew_worktree_lease(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-renew"
    wt_path.mkdir(parents=True)

    acquire_worktree_lease(
        str(wt_path),
        leased_by="codex",
        job_id="job-1",
        pid=os.getpid(),
        duration_seconds=300,
        conn=db_conn,
    )

    renewed = renew_worktree_lease(
        str(wt_path),
        leased_by="codex",
        extend_seconds=900,
        conn=db_conn,
    )
    assert renewed is True

    lease = get_active_worktree_lease(str(wt_path), conn=db_conn)
    assert lease is not None


def test_release_worktree_lease(tmp_path, db_conn):
    wt_path = tmp_path / "worktrees" / "job-release"
    wt_path.mkdir(parents=True)

    acquire_worktree_lease(
        str(wt_path),
        leased_by="codex",
        job_id="job-1",
        pid=os.getpid(),
        duration_seconds=600,
        conn=db_conn,
    )

    lease_file = wt_path / ".synlynk" / "lease.json"
    assert lease_file.exists()

    released = release_worktree_lease(
        str(wt_path),
        leased_by="codex",
        conn=db_conn,
    )
    assert released is True
    assert not lease_file.exists()

    lease = get_active_worktree_lease(str(wt_path), conn=db_conn)
    assert lease is None


def test_audit_and_reclaim_stale_worktree_leases(tmp_path, db_conn):
    wt1 = tmp_path / "worktrees" / "job-stale-1"
    wt2 = tmp_path / "worktrees" / "job-stale-2"
    wt3 = tmp_path / "worktrees" / "job-alive"
    wt1.mkdir(parents=True)
    wt2.mkdir(parents=True)
    wt3.mkdir(parents=True)

    # wt1: expired TTL
    acquire_worktree_lease(str(wt1), "codex", job_id="j1", pid=101, duration_seconds=-10, conn=db_conn)
    # wt2: dead PID
    acquire_worktree_lease(str(wt2), "agy", job_id="j2", pid=102, duration_seconds=600, conn=db_conn)
    # wt3: alive PID
    acquire_worktree_lease(str(wt3), "claude", job_id="j3", pid=103, duration_seconds=600, conn=db_conn)

    def mock_alive(pid):
        return pid == 103

    with patch("synlynk.worktree_lease._is_pid_alive", side_effect=mock_alive):
        reclaimed = audit_and_reclaim_stale_worktree_leases(conn=db_conn)

    reclaimed_paths = [r["worktree_path"] for r in reclaimed]
    assert str(wt1) in reclaimed_paths
    assert str(wt2) in reclaimed_paths
    assert str(wt3) not in reclaimed_paths
