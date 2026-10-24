"""Regression tests for the cost_entries/daemon_jobs harness-model
attribution mismatch guard (#2547 telemetry finding)."""
import os
import pytest


def test_ensure_cost_entry_refuses_mismatched_harness(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, actual_harness, resolved_model) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("job-mismatch-1", "codex", "task", "done", 5, "[]", None,
         "2026-10-02T00:00:00", "codex", "codex-5.1"),
    )
    conn.commit()
    conn.close()

    conn = synlynk._get_db()
    with pytest.raises(jobs_mod.CostAttributionMismatch):
        jobs_mod._ensure_daemon_job_cost_entry(
            "job-mismatch-1", agent="grok", story_id=None, log_text="", conn=conn,
        )
    conn.close()


def test_ensure_cost_entry_accepts_matching_harness(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    (project_dir / ".synlynk" / ".synlynk_migrated").touch()
    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, actual_harness, resolved_model) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("job-match-1", "codex", "task", "done", 5, "[]", None,
         "2026-10-02T00:00:00", "codex", "codex-5.1"),
    )
    conn.commit()
    conn.close()

    conn = synlynk._get_db()
    written = jobs_mod._ensure_daemon_job_cost_entry(
        "job-match-1", agent="codex", story_id=None, log_text="", conn=conn,
    )
    conn.close()
    assert written


def test_cmd_cost_log_refuses_mismatched_harness_for_job_id(monkeypatch, project_dir):
    import synlynk
    from synlynk.db import cmd_cost_log
    from synlynk.jobs import CostAttributionMismatch

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, actual_harness, resolved_model) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("job-log-mismatch", "codex", "task", "done", 5, "[]", None,
         "2026-10-02T00:00:00", "codex", "codex-5.1"),
    )
    conn.commit()
    conn.close()

    with pytest.raises(CostAttributionMismatch):
        cmd_cost_log(
            agent="grok",
            tokens_in=100,
            tokens_out=50,
            job_id="job-log-mismatch",
        )


def test_cmd_cost_log_accepts_matching_harness_for_job_id(monkeypatch, project_dir):
    import synlynk
    from synlynk.db import cmd_cost_log

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, actual_harness, resolved_model) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("job-log-match", "codex", "task", "done", 5, "[]", None,
         "2026-10-02T00:00:00", "codex", "codex-5.1"),
    )
    conn.commit()
    conn.close()

    cmd_cost_log(
        agent="codex",
        tokens_in=100,
        tokens_out=50,
        job_id="job-log-match",
    )

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT harness, job_id FROM cost_entries WHERE job_id='job-log-match'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "codex"


def test_cmd_cost_log_unguarded_when_no_job_id(monkeypatch, project_dir):
    import synlynk
    from synlynk.db import cmd_cost_log

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    cmd_cost_log(
        agent="claude",
        tokens_in=200,
        tokens_out=100,
        pr=123,
    )

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT harness, pr_number FROM cost_entries WHERE pr_number=123"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "claude"


def test_import_guard_from_costs():
    from synlynk.costs import CostAttributionMismatch, cmd_cost_log
    assert issubclass(CostAttributionMismatch, Exception)
    assert callable(cmd_cost_log)

