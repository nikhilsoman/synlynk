"""Regression tests for job_timing_metrics extraction (#2547 instrumentation)."""
import json
import os


def test_settle_daemon_job_terminal_writes_timing_metrics(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-1", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1"),
    )
    conn.commit()

    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-1", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()

    row = conn.execute(
        "SELECT harness, model, queue_seconds, active_seconds FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-1",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "codex"
    assert row[1] == "codex-5.1"
    assert row[2] == 60.0   # 00:01:00 - 00:00:00
    assert row[3] == 240.0  # 00:05:00 - 00:01:00


def test_self_reported_block_never_overrides_objective_timestamps(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-2", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1",
         None),
    )
    conn.commit()

    monkeypatch.setattr(
        jobs_mod, "_extract_self_reported_timing", lambda job_id: {"active_seconds": 999999}
    )

    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-2", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()

    row = conn.execute(
        "SELECT active_seconds, self_reported_json, cross_check_status FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-2",),
    ).fetchone()
    conn.close()

    assert row[0] == 240.0  # objective value, NOT the self-reported 999999
    assert "999999" in row[1]
    assert row[2] == "disagree"


def test_extract_self_reported_timing_from_log_file(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    log_file = project_dir / "job.log"
    log_content = (
        "Some initial log output...\n"
        "SYNLYNK_TIMING_SELF_REPORT: {\"active_seconds\": 240.0, \"queue_seconds\": 60.0}\n"
        "End of log\n"
    )
    log_file.write_text(log_content)

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-3", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1",
         str(log_file)),
    )
    conn.commit()
    conn.close()

    extracted = jobs_mod._extract_self_reported_timing("job-timing-3")
    assert extracted is not None
    assert extracted.get("active_seconds") == 240.0
    assert extracted.get("queue_seconds") == 60.0

    conn = synlynk._get_db()
    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-3", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()

    row = conn.execute(
        "SELECT active_seconds, cross_check_status FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-3",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 240.0
    assert row[1] == "agree"


def test_self_reported_json_list_records_objective_metrics(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    log_file = project_dir / "job-list.log"
    log_file.write_text("SYNLYNK_TIMING_SELF_REPORT: [1, 2, 3]\n")

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-list", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1",
         str(log_file)),
    )
    conn.commit()

    assert jobs_mod._extract_self_reported_timing("job-timing-list", conn=conn) is None

    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-list", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()

    row = conn.execute(
        "SELECT queue_seconds, active_seconds, cross_check_status FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-list",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 60.0
    assert row[1] == 240.0
    assert row[2] == "absent"

    # Also verify when self-reported value is a list (e.g. from external report),
    # _record_job_timing_metrics defensively handles it and records objective metrics
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-list-mock", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1",
         None),
    )
    conn.commit()
    monkeypatch.setattr(jobs_mod, "_extract_self_reported_timing", lambda *a, **kw: [1, 2, 3])
    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-list-mock", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()
    row2 = conn.execute(
        "SELECT queue_seconds, active_seconds, cross_check_status FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-list-mock",),
    ).fetchone()
    conn.close()
    assert row2 is not None
    assert row2[0] == 60.0
    assert row2[1] == 240.0
    assert row2[2] == "absent"


def test_self_reported_non_numeric_active_seconds_records_objective_metrics(monkeypatch, project_dir):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))

    log_file = project_dir / "job-str.log"
    log_file.write_text('SYNLYNK_TIMING_SELF_REPORT: {"active_seconds": "not-a-number"}\n')

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, actual_harness, "
        "resolved_model, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("job-timing-str", "codex", "task", "running", 5, "[]", None,
         "2026-10-02T00:00:00", "2026-10-02T00:01:00", "codex", "codex-5.1",
         str(log_file)),
    )
    conn.commit()

    extracted = jobs_mod._extract_self_reported_timing("job-timing-str", conn=conn)
    assert extracted == {"active_seconds": "not-a-number"}

    jobs_mod._settle_daemon_job_terminal(
        conn, "job-timing-str", "done", 0, "2026-10-02T00:05:00",
    )
    conn.commit()

    row = conn.execute(
        "SELECT queue_seconds, active_seconds, cross_check_status FROM "
        "job_timing_metrics WHERE job_id=?", ("job-timing-str",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 60.0
    assert row[1] == 240.0
    assert row[2] == "absent"
