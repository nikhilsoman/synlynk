import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_dispatch_ready_jobs_prints_fence_when_schedule_allowlisted(monkeypatch, capsys):
    from synlynk.fencing import FenceData
    from synlynk.jobs import _dispatch_ready_jobs

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, "
        "story_id TEXT, depends_on TEXT, log_path TEXT, priority INTEGER, "
        "enqueued_at TEXT, status TEXT, pid INTEGER, started_at TEXT, completed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, depends_on, log_path, "
        "priority, enqueued_at, status) VALUES "
        "('job-abc123', 'codex', 'do the thing', 'story-x', '[]', '/tmp/x-log', 1, "
        "'2026-07-17T00:00:00', 'queued')"
    )
    conn.commit()

    fake_job = {
        "id": "job-abc123",
        "pid": 999,
        "started_at": "2026-07-17T00:00:00",
        "log_file": "/tmp/x-log",
        "fence": FenceData(
            command="schedule",
            kind="estimate",
            in_tokens=100,
            out_tokens=50,
            cost_usd=0.01,
            basis="prompt_estimate",
        ),
    }

    import synlynk.jobs as jobs_mod
    from synlynk.fencing import render_task_fence

    def pkg_side_effect(name, default=None):
        if name == "_get_db":
            return lambda: conn
        if name == "dispatch_agent":
            return lambda *a, **k: fake_job
        if name == "render_task_fence":
            return render_task_fence
        return default

    monkeypatch.setattr(jobs_mod, "_pkg", pkg_side_effect)

    launched = _dispatch_ready_jobs(max_parallel=4)

    assert launched == 1
    out = capsys.readouterr().out
    assert "schedule" in out
    assert "$0.01" in out


def test_write_job_summary_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-123",
        "claude",
        "story-9",
        0,
        12.4,
        42100,
        3200,
        0.14,
        [],
    )

    summary_path = tmp_path / ".synlynk" / "logs" / "job-123.summary"
    assert summary_path.exists()
    assert summary_path.read_text() == text


def test_write_job_summary_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-abc",
        "agy",
        "story-42",
        0,
        3.0,
        1000,
        250,
        0.03,
        ["src/app.py", "tests/test_app.py"],
    )

    assert "agent:    agy   story: story-42" in text
    assert "status:   OK (exit 0)" in text
    assert "duration: 3.0s" in text
    assert "cost:   $0.03  (1,000 in / 250 out, structured_output)" in text


def test_write_job_summary_failed_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-fail",
        "codex",
        None,
        1,
        8.0,
        0,
        0,
        0.0,
        [],
    )

    assert "status:   FAILED (exit 1)" in text


def test_cmd_jobs_summary_flag_reads_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    summary_text = synlynk._write_job_summary(
        "job-read",
        "claude",
        "story-1",
        0,
        2.5,
        10,
        20,
        0.01,
        [],
    )

    synlynk.cmd_jobs(summary="job-read")
    out = capsys.readouterr().out
    assert out == summary_text


def test_cmd_jobs_summary_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    synlynk.cmd_jobs(summary="nonexistent")
    out = capsys.readouterr().out
    assert "No summary for nonexistent -- job may still be running or predates this feature" in out


def test_reconcile_jobs_writes_and_prints_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 42\nOutput tokens: 3200\n")
    (log_path.parent / "job-run.log.exit").write_text("0")

    jobs = [{
        "id": "job-run",
        "agent": "claude",
        "story_id": "story-7",
        "task": "task",
        "pid": 99999999,
        "log_file": str(log_path),
        "started_at": "2026-07-03T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
    }]
    synlynk._save_jobs(jobs)

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    assert "-- job job-run complete ---------" in out
    assert "status:   OK (exit 0)" in out
    summary_path = tmp_path / ".synlynk" / "logs" / "job-run.summary"
    assert summary_path.exists()
