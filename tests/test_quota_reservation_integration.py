"""Integration coverage for the quota-aware dispatch reservation design.

Exercises the full reserve -> dispatch -> settle -> release lifecycle and
verifies that an exhausted queued job resumes after quota refresh without
re-dispatching a completed job.  Dispatch is monkeypatched so no subprocess is
spawned.
"""

import time


def _fake_dispatch_success(monkeypatch, sl):
    """Simulate a successful spawn without starting a real subprocess."""

    def _fake(agent, task, story_id=None, force_agent=False, job_id=None, **kwargs):
        conn = sl._get_db()
        conn.execute(
            "UPDATE daemon_jobs SET status='running', pid=999999, started_at=? "
            "WHERE job_id=?",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), job_id),
        )
        conn.commit()
        conn.close()
        return {"job_id": job_id, "pid": 999999}

    monkeypatch.setattr(sl, "dispatch_agent", _fake)


def test_full_reserve_dispatch_settle_release_cycle(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.scheduler import _enqueue_plan

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )

    plan = [
        {
            "story_id": "story-int1", "title": "A", "agent": "codex", "score": 1.0,
            "model": "unknown", "priority": 5, "estimated_tokens": 10_000,
            "headroom_before": 100_000, "headroom_after": 90_000,
        },
        {
            "story_id": "story-int2", "title": "B", "agent": "agy", "score": 1.0,
            "model": "unknown", "priority": 5, "estimated_tokens": 20_000,
            "headroom_before": 100_000, "headroom_after": 80_000,
        },
    ]
    job_ids = _enqueue_plan(plan)
    assert len(job_ids) == 2

    open_count = conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE status='open'"
    ).fetchone()[0]
    assert open_count == 2

    _fake_dispatch_success(monkeypatch, sl)
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *args, **kwargs: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *args, **kwargs: None)

    launched = sl._dispatch_ready_jobs(max_parallel=4)
    assert launched == 2

    running_count = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status='running'"
    ).fetchone()[0]
    assert running_count == 2

    sl._reconcile_daemon_jobs()

    for job_id in job_ids:
        status = conn.execute(
            "SELECT status FROM daemon_jobs WHERE job_id=?", (job_id,)
        ).fetchone()[0]
        assert status in ("done", "timed_out", "failed")

    open_count_after = conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE status='open'"
    ).fetchone()[0]
    assert open_count_after == 0
    released_count = conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE status='released'"
    ).fetchone()[0]
    assert released_count == 2


def test_deferred_job_survives_reset_and_resumes_without_redispatch(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    past_reset = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 60)
    )
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=10_000, used_tokens=10_000,
        unit="tokens", reset_at=past_reset, conn=conn,
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at, blocked_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-deferred1", "codex", "task", "queued", 5, "[]",
         "2026-08-08T00:00:00", "quota_exhausted"),
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-already-done1", "codex", "task", "done", 5, "[]", "2026-08-08T00:00:00"),
    )
    conn.commit()

    # Simulate refreshed post-reset telemetry: the quota is available again.
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=10_000, used_tokens=0,
        unit="tokens", reset_at=None, conn=conn,
    )

    _fake_dispatch_success(monkeypatch, sl)

    launched = sl._dispatch_ready_jobs(max_parallel=4)
    assert launched == 1

    status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-deferred1'"
    ).fetchone()[0]
    assert status == "running"

    already_done_status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-already-done1'"
    ).fetchone()[0]
    assert already_done_status == "done"
