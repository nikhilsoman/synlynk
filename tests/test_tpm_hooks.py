"""Tests for the TPM hook stub surface."""

import pytest


def test_tpm_observe_reservations_returns_open_reservations(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_observe_reservations

    conn = sl._get_db()
    sl._open_reservation(conn, "claude", 2_000, scope="session")
    sl._open_reservation(conn, "codex", 3_000, scope="plan", scope_id="run-1")

    result = tpm_observe_reservations(conn)
    harnesses = {r["harness"] for r in result}
    assert harnesses == {"claude", "codex"}

    scoped = tpm_observe_reservations(conn, scope="plan", scope_id="run-1")
    assert len(scoped) == 1
    assert scoped[0]["harness"] == "codex"


def test_tpm_reorder_queue_updates_priorities(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reorder_queue

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-r1', 'codex', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-r2', 'agy', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    conn.commit()

    changed = tpm_reorder_queue(conn, {"job-r1": 1, "job-r2": 9})
    assert changed == 2

    rows = dict(conn.execute(
        "SELECT job_id, priority FROM daemon_jobs WHERE job_id IN ('job-r1','job-r2')"
    ).fetchall())
    assert rows == {"job-r1": 1, "job-r2": 9}


def test_tpm_reallocate_moves_reservation_and_agent(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reallocate

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-realloc1', 'codex', 't', 'queued', 5, '2026-08-08T00:00:00')"
    )
    rid = sl._open_reservation(conn, "codex", 5_000, scope="adhoc", job_id="job-realloc1")
    conn.commit()

    result = tpm_reallocate(conn, "job-realloc1", "agy")

    assert result["job_id"] == "job-realloc1"
    assert result["new_harness"] == "agy"
    assert conn.execute(
        "SELECT agent FROM daemon_jobs WHERE job_id='job-realloc1'"
    ).fetchone()[0] == "agy"
    assert conn.execute(
        "SELECT status FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()[0] == "released"
    assert conn.execute(
        "SELECT harness, tokens, status FROM agent_reservations "
        "WHERE job_id='job-realloc1' AND status='open'"
    ).fetchone() == ("agy", 5_000, "open")


def test_tpm_reallocate_raises_when_not_queued(project_dir):
    import synlynk as sl
    from synlynk.tpm_hooks import tpm_reallocate

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, enqueued_at) "
        "VALUES ('job-running2', 'codex', 't', 'running', 5, '2026-08-08T00:00:00')"
    )
    conn.commit()

    with pytest.raises(ValueError):
        tpm_reallocate(conn, "job-running2", "agy")


def test_cli_quota_tpm_view_prints_reservations(project_dir, capsys, monkeypatch):
    import synlynk as sl
    from synlynk.cli import main

    conn = sl._get_db()
    sl._open_reservation(conn, "claude", 4_500, scope="session")

    monkeypatch.setattr("sys.argv", ["synlynk", "quota", "--tpm-view"])
    main()

    out = capsys.readouterr().out
    assert "claude" in out
    assert "4,500" in out or "4500" in out
