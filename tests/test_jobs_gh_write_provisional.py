"""gh:#2137 — local reconcile must not publish a gh-write failure before verification."""

import os

import synlynk
import synlynk.jobs as jobs_mod


def _running_job(job_id, log_file, *, requires_gh_write):
    return {
        "id": job_id,
        "agent": "grok",
        "pid": 9999999 if requires_gh_write else 9999998,
        "status": "running",
        "ended_at": None,
        "exit_code": None,
        "log_file": log_file,
        "task": "review the pull request and post the result",
        "started_at": "2026-10-08T12:00:00",
        "requires_gh_write": requires_gh_write,
        "gh_write_target": "pr:2137" if requires_gh_write else None,
        "gh_write_expect": "review_posted" if requires_gh_write else None,
    }


def test_reconcile_holds_local_gh_write_failure_as_pending_verification(project_dir, capsys):
    """Log evidence that looks like a failure stays non-terminal for gh-write jobs only."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    gh_log = ".synlynk/logs/job-gh-local-fail.log"
    plain_log = ".synlynk/logs/job-plain-local-fail.log"
    for path in (gh_log, plain_log):
        with open(path, "w") as handle:
            handle.write("worker exited before any verified GitHub effect\n")
        with open(path + ".exit", "w") as handle:
            handle.write("1\n")

    synlynk._save_jobs([
        _running_job("job-gh-local-fail", gh_log, requires_gh_write=True),
        _running_job("job-plain-local-fail", plain_log, requires_gh_write=False),
    ])

    jobs_mod._reconcile_jobs_unlocked()
    saved = {job["id"]: job for job in synlynk._load_jobs()}
    gh_job = saved["job-gh-local-fail"]
    plain_job = saved["job-plain-local-fail"]

    assert gh_job["status"] == jobs_mod.STATUS_PENDING_VERIFICATION
    assert gh_job["status"] not in jobs_mod.FAILURE_LOOKING_JOB_STATUSES
    assert jobs_mod.is_terminal_status(gh_job["status"]) is False
    assert plain_job["status"] == "task_delivery_failed"
    assert plain_job["status"] in jobs_mod.FAILURE_LOOKING_JOB_STATUSES

    out = capsys.readouterr().out
    assert "PENDING_VERIFICATION" in out
    assert "TASK_DELIVERY_FAILED" in out


def test_jobs_all_renders_pending_verification_distinct_from_failure(project_dir, monkeypatch, capsys):
    """A provisional gh-write row is active and colored apart from a real failure."""
    monkeypatch.setattr(synlynk, "_reconcile_daemon_jobs", lambda: None)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, enqueued_at, exit_code) "
        "VALUES ('job-pending', 'grok', 'story-2137', 'review pr', 'running', "
        "'2026-10-08T12:00:00', NULL)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, story_id, task, status, enqueued_at, exit_code) "
        "VALUES ('job-real-fail', 'grok', 'story-2137', 'local edit', 'failed', "
        "'2026-10-08T12:00:00', 1)"
    )
    conn.commit()
    conn.close()
    synlynk._save_jobs([
        {
            "id": "job-pending",
            "agent": "grok",
            "status": jobs_mod.STATUS_PENDING_VERIFICATION,
            "task": "review pr",
            "requires_gh_write": True,
        },
        {
            "id": "job-real-fail",
            "agent": "grok",
            "status": "failed",
            "task": "local edit",
            "requires_gh_write": False,
        },
    ])

    jobs_mod.cmd_jobs(all_jobs=True)
    out = capsys.readouterr().out
    pending_line = next(line for line in out.splitlines() if "job-pending" in line)
    failed_line = next(line for line in out.splitlines() if "job-real-fail" in line)

    assert "pending_verification" in pending_line
    assert jobs_mod._GREEN in pending_line
    assert jobs_mod._YELLOW not in pending_line
    assert "failed" in failed_line
    assert jobs_mod._YELLOW in failed_line
    assert jobs_mod._GREEN not in failed_line
    assert jobs_mod._job_status_color("pending_verification") != jobs_mod._job_status_color("failed")
