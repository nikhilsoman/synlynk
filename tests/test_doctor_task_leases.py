import os
import time
import pytest
from synlynk import _get_db
from synlynk.doctor import _hc_task_leases_integrity, HEALTH_CHECKS, cmd_doctor, cmd_doctor_fix
from synlynk.jobs import acquire_task_lease, get_active_lease


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_doctor_leases.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    claims_file = str(tmp_path / "active_claims.json")
    monkeypatch.setattr("synlynk.session._active_claims_path", lambda: claims_file)

    conn = _get_db(db_path=db_path)
    conn.execute("""
        INSERT INTO stories (story_id, title, role, stage, status, readiness)
        VALUES ('story-doc-1', 'Doctor test story', 'dev', 'open', 'ready', 'ready')
    """)
    conn.commit()
    return conn


def test_hc_task_leases_integrity_in_health_checks():
    assert _hc_task_leases_integrity in HEALTH_CHECKS


def test_hc_task_leases_integrity_ok_when_empty_or_live(db_conn):
    # Empty
    check = _hc_task_leases_integrity()
    assert check.status == "ok"
    assert check.name == "task_leases_integrity"

    # Live lease with current PID
    acquire_task_lease("story-doc-1", "claude:testhost:1234", pid=os.getpid(), harness="claude", conn=db_conn)
    check2 = _hc_task_leases_integrity()
    assert check2.status == "ok"


def test_hc_task_leases_integrity_detects_dead_pid_and_expired(db_conn):
    # Seed dead PID lease
    db_conn.execute("""
        INSERT INTO task_leases (lease_id, story_id, leased_by, pid, harness, acquired_at, heartbeat_at, expires_at, status)
        VALUES ('lease-dead-1', 'story-doc-1', 'dead:host:999999', 999999, 'dead', '2026-10-20T00:00:00Z', '2026-10-20T00:00:00Z', '2026-10-20T01:00:00Z', 'active')
    """)
    db_conn.commit()

    check = _hc_task_leases_integrity()
    assert check.status == "warn"
    assert "1 orphaned or expired lease(s)" in check.message
    assert "synlynk doctor --fix leases" in check.fix


def test_doctor_fix_reclaims_orphaned_leases(db_conn):
    db_conn.execute("""
        INSERT INTO task_leases (lease_id, story_id, leased_by, pid, harness, acquired_at, heartbeat_at, expires_at, status)
        VALUES ('lease-dead-2', 'story-doc-1', 'dead:host:999999', 999999, 'dead', '2026-10-20T00:00:00Z', '2026-10-20T00:00:00Z', '2026-10-20T01:00:00Z', 'active')
    """)
    db_conn.execute("UPDATE stories SET status='in_progress', readiness='in_progress' WHERE story_id='story-doc-1'")
    db_conn.commit()

    ret = cmd_doctor_fix("leases")
    assert ret == 0

    # Lease marked expired
    row = db_conn.execute("SELECT status FROM task_leases WHERE lease_id='lease-dead-2'").fetchone()
    assert row[0] == "expired"

    # Story reverted to ready
    story_row = db_conn.execute("SELECT status, readiness FROM stories WHERE story_id='story-doc-1'").fetchone()
    assert story_row[0] == "ready"
    assert story_row[1] == "ready"

    # Health check is now ok
    check = _hc_task_leases_integrity()
    assert check.status == "ok"
