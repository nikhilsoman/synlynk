"""Regression tests for LIVE-19 circuit-breaker reconciliation races."""

import json
import os

from synlynk.circuit_breaker import CircuitBreakerResult


def _patch_reconcile_dependencies(monkeypatch, synlynk, jobs):
    """Keep reconciliation tests focused on terminal-state selection."""
    monkeypatch.setattr(synlynk, "load_config", lambda: {})
    monkeypatch.setattr(synlynk, "_check_job_stall", lambda *args: False)
    monkeypatch.setattr(synlynk, "extract_tokens", lambda *args, **kwargs: (0, 0))
    monkeypatch.setattr(synlynk, "update_costs", lambda *args, **kwargs: None)
    monkeypatch.setattr(synlynk, "_write_job_summary", lambda *args, **kwargs: "")
    monkeypatch.setattr(synlynk, "_worktree_files_touched", lambda *args: [])
    monkeypatch.setattr(synlynk, "_inspect_worktree_git_state", lambda *args: None, raising=False)
    monkeypatch.setattr(jobs, "_write_sentinel_alert", lambda *args, **kwargs: None)


def test_cli_reconcile_preserves_clean_exit_when_breaker_did_not_kill(monkeypatch, tmp_path):
    import synlynk
    import synlynk.jobs as jobs_mod

    job = {
        "id": "job-live19-cli-clean",
        "agent": "claude",
        "status": "running",
        "pid": 1234,
        "started_at": "2026-10-02T00:00:00",
    }
    saved = []
    _patch_reconcile_dependencies(monkeypatch, synlynk, jobs_mod)
    monkeypatch.setattr(jobs_mod, "_load_jobs", lambda: [job])
    monkeypatch.setattr(jobs_mod, "_save_jobs", lambda value: saved.append(value))
    monkeypatch.setattr(synlynk, "evaluate_job_circuit_breaker", lambda *args: CircuitBreakerResult(
        tripped=True, process_killed=False, reason="observed after natural exit"
    ))
    monkeypatch.setattr(os, "waitpid", lambda pid, options: (pid, 0))

    jobs_mod._reconcile_jobs_unlocked()

    assert job["status"] == "completed"
    assert job["exit_code"] == 0
    assert saved and saved[0][0]["status"] == "completed"


def test_daemon_reconcile_reaps_clean_exit_when_breaker_did_not_kill(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _patch_reconcile_dependencies(monkeypatch, synlynk, jobs_mod)
    monkeypatch.setattr(synlynk, "evaluate_job_circuit_breaker", lambda *args: CircuitBreakerResult(
        tripped=True, process_killed=False, reason="observed after natural exit"
    ))
    monkeypatch.setattr(os, "waitpid", lambda pid, options: (pid, 0))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, pid, "
        "enqueued_at, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("job-live19-daemon-clean", "claude", "task", "running", 5, "[]", 5678,
         "2026-10-02T00:00:00", "2026-10-02T00:00:00"),
    )
    conn.commit()
    conn.close()

    jobs_mod._reconcile_daemon_jobs()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?",
        ("job-live19-daemon-clean",),
    ).fetchone()
    conn.close()
    assert tuple(row) == ("done", 0)


def test_both_reconcilers_trip_only_after_confirmed_kill(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    _patch_reconcile_dependencies(monkeypatch, synlynk, jobs_mod)
    monkeypatch.setattr(synlynk, "evaluate_job_circuit_breaker", lambda *args: CircuitBreakerResult(
        tripped=True, process_killed=True, reason="runaway worker"
    ))

    cli_job = {
        "id": "job-live19-cli-killed",
        "agent": "claude",
        "status": "running",
        "pid": 1234,
        "started_at": "2026-10-02T00:00:00",
    }
    monkeypatch.setattr(jobs_mod, "_load_jobs", lambda: [cli_job])
    saved = []
    monkeypatch.setattr(jobs_mod, "_save_jobs", lambda value: saved.append(value))
    jobs_mod._reconcile_jobs_unlocked()
    assert cli_job["status"] == "circuit_breaker_tripped"
    assert cli_job["exit_code"] == -9

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, pid, "
        "enqueued_at, started_at, pid_identity) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("job-live19-daemon-killed", "claude", "task", "running", 5, "[]", 5679,
         "2026-10-02T00:00:00", "2026-10-02T00:00:00", json.dumps({"start_time": "test"})),
    )
    conn.commit()
    conn.close()

    jobs_mod._reconcile_daemon_jobs()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?",
        ("job-live19-daemon-killed",),
    ).fetchone()
    conn.close()
    assert tuple(row) == ("circuit_breaker_tripped", -9)
