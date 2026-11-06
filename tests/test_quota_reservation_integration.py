"""Integration coverage for the quota-aware dispatch reservation design.

Exercises the full reserve -> dispatch -> settle -> release lifecycle and
verifies that an exhausted queued job resumes after quota refresh without
re-dispatching a completed job.  Dispatch is monkeypatched so no subprocess is
spawned.
"""

import time
import sqlite3
from concurrent.futures import ThreadPoolExecutor


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
    # This integration test exercises reservation settlement, not process
    # teardown. Model the external teardown observer proving the owned job
    # domain is stopped; without that proof the reservation must stay held.
    monkeypatch.setattr(
        jobs_mod,
        "_resolve_persisted_termination_domain",
        lambda *_args, **_kwargs: "stopped_verified",
    )
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


def test_deferred_job_replays_selected_model(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0,
        model="claude-sonnet-5", track="claude_proxy", conn=conn,
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, "
        "enqueued_at, requested_model, resolved_model) VALUES "
        "('job-model-replay', 'agy', 'task', 'queued', 5, '[]', "
        "'2026-11-01T00:00:00', 'claude-sonnet-5', 'claude-sonnet-5')"
    )
    conn.commit()
    seen = {}

    def fake_dispatch(agent, task, **kwargs):
        seen.update(kwargs)
        return {"job_id": kwargs["job_id"], "pid": 123}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch)
    assert sl._dispatch_ready_jobs(max_parallel=1) == 1
    assert seen["model"] == "claude-sonnet-5"


def test_agy_unknown_selected_pool_is_rejected_without_reservation(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    result = sl._check_and_reserve_quota(
        conn,
        harness="agy",
        model="gemini-3.8-flash-low",
        track="gemini",
        estimated_tokens=1000,
        estimated_cost_usd=0.01,
        payment_mode="credit_grant",
        scope="session",
        job_id="job-unknown-pool",
    )

    assert result["accepted"] is False
    assert result["reason"] == "quota_unknown"
    assert conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE job_id='job-unknown-pool'"
    ).fetchone()[0] == 0


def test_agy_unknown_pool_blocks_before_worktree_or_process(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch_pipeline as pipeline
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        pipeline,
        "prepare_worktree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("worktree creation must not run")
        ),
    )
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("process spawn must not run")
        ),
    )

    result = sl.dispatch_agent(
        "agy",
        "implement the requested change",
        model="gemini-3.8-flash-low",
        force_agent=True,
        skip_preflight=True,
        job_id="job-agy-preflight-block",
    )

    assert result["deferred"] is True
    assert result["reason"] == "quota_unknown"
    assert result["preflight"] == {
        "harness": "agy",
        "model": "gemini-3.8-flash-low",
        "track": "gemini",
        "result": "quota_unknown",
    }


def test_agy_exhausted_credit_is_rejected_without_reservation(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0,
        track="gemini", model="gemini-3.7-flash", conn=conn,
    )
    result = sl._check_and_reserve_quota(
        conn,
        harness="agy",
        model="gemini-3.7-flash",
        track="gemini",
        estimated_tokens=1000,
        estimated_cost_usd=0.01,
        payment_mode="credit_grant",
        scope="session",
        job_id="job-no-credit",
    )

    assert result["accepted"] is False
    assert result["reason"] == "credit_exhausted"
    assert conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE job_id='job-no-credit'"
    ).fetchone()[0] == 0


def test_selected_pool_ignores_exhausted_other_track(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=10_000, used_tokens=10_000,
        track="claude_proxy", model="claude-sonnet-5", conn=conn,
    )
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=10_000, used_tokens=0,
        track="gemini", model="gemini-3.7-flash", conn=conn,
    )
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 10.0, 10.0, '2026-11-01')"
    )
    conn.commit()

    result = sl._check_and_reserve_quota(
        conn,
        harness="agy",
        model="gemini-3.7-flash",
        track="gemini",
        estimated_tokens=1000,
        estimated_cost_usd=0.01,
        payment_mode="credit_grant",
        scope="session",
        job_id="job-healthy-gemini",
    )

    assert result["accepted"] is True
    assert conn.execute(
        "SELECT model, track FROM harness_reservations WHERE job_id='job-healthy-gemini'"
    ).fetchone() == ("gemini-3.7-flash", "gemini")


def test_parallel_same_pool_reservations_do_not_oversubscribe(tmp_path):
    import synlynk as sl

    db_path = tmp_path / "atomic-reservations.db"
    seed = sl._get_db(str(db_path))
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=1500, used_tokens=0,
        track="gemini", model="gemini-3.7-flash", conn=seed,
    )
    seed.close()

    def reserve(job_id):
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            return sl._check_and_reserve_quota(
                conn,
                harness="agy",
                model="gemini-3.7-flash",
                track="gemini",
                estimated_tokens=1000,
                estimated_cost_usd=0.0,
                payment_mode="subscription",
                scope="session",
                job_id=job_id,
            )
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ("job-atomic-a", "job-atomic-b")))

    assert sorted(result["accepted"] for result in results) == [False, True]
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE status='open'"
    ).fetchone()[0] == 1
    conn.close()


def test_shared_credit_is_not_oversubscribed_across_models(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    for model, track in (("gemini-3.7-flash", "gemini"), ("claude-sonnet-5", "claude_proxy")):
        sl._upsert_agent_quota(
            "agy", "5h", limit_tokens=100_000, used_tokens=0,
            model=model, track=track, conn=conn,
        )
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 1.0, 1.0, '2026-11-01')"
    )
    conn.commit()

    first = sl._check_and_reserve_quota(
        conn, harness="agy", model="gemini-3.7-flash", track="gemini",
        estimated_tokens=1000, estimated_cost_usd=0.75, payment_mode="credit_grant",
        scope="session", job_id="job-credit-a",
    )
    second = sl._check_and_reserve_quota(
        conn, harness="agy", model="claude-sonnet-5", track="claude_proxy",
        estimated_tokens=1000, estimated_cost_usd=0.75, payment_mode="credit_grant",
        scope="session", job_id="job-credit-b",
    )
    assert first["accepted"] is True
    assert second == {"accepted": False, "reason": "credit_exhausted", "credit_remaining_usd": 1.0}


def test_request_quota_is_reserved_atomically(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=1, used_tokens=0, unit="requests",
        model="gemini-3.7-flash", track="gemini", conn=conn,
    )
    first = sl._check_and_reserve_quota(
        conn, harness="agy", model="gemini-3.7-flash", track="gemini",
        estimated_tokens=1000, estimated_cost_usd=0, payment_mode="subscription",
        scope="session", job_id="job-request-a",
    )
    second = sl._check_and_reserve_quota(
        conn, harness="agy", model="gemini-3.7-flash", track="gemini",
        estimated_tokens=1000, estimated_cost_usd=0, payment_mode="subscription",
        scope="session", job_id="job-request-b",
    )
    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["reason"] == "quota_exhausted"


def test_stale_selected_pool_is_unknown(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0,
        model="gemini-3.7-flash", track="gemini", conn=conn,
    )
    conn.execute(
        "UPDATE harness_quotas SET updated_at='2000-01-01 00:00:00', "
        "reset_at='2000-01-01 05:00:00' WHERE harness='agy'"
    )
    conn.commit()
    result = sl._check_and_reserve_quota(
        conn, harness="agy", model="gemini-3.7-flash", track="gemini",
        estimated_tokens=1000, estimated_cost_usd=0, payment_mode="subscription",
        scope="session", job_id="job-stale",
    )
    assert result["accepted"] is False
    assert result["reason"] == "quota_stale"


def test_elapsed_subscription_window_is_not_stale(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    past_reset = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 60))
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=100_000,
        model="gpt-5", track="default", reset_at=past_reset, conn=conn,
    )
    result = sl._check_and_reserve_quota(
        conn, harness="codex", model="gpt-5", track="default",
        estimated_tokens=1000, estimated_cost_usd=0, payment_mode="subscription",
        scope="session", job_id="job-rollover",
    )
    assert result["accepted"] is True
    assert result["quota"]["headroom"] == 100_000


def test_stale_subscription_harness_does_not_block_dispatch(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=100_000, used_tokens=0,
        model="claude-sonnet", track="default", conn=conn,
    )
    conn.execute(
        "UPDATE harness_quotas SET updated_at='2000-01-01 00:00:00' WHERE harness='claude'"
    )
    conn.commit()
    result = sl._check_and_reserve_quota(
        conn, harness="claude", model="claude-sonnet", track="default",
        estimated_tokens=1000, estimated_cost_usd=0, payment_mode="subscription",
        scope="session", job_id="job-stale-subscription",
    )
    assert result["accepted"] is True


def test_unchecked_existing_reservation_is_revalidated(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "agy", "5h", limit_tokens=100_000, used_tokens=0,
        model="gemini-3.7-flash", track="gemini", conn=conn,
    )
    existing = sl._open_reservation(
        conn, "agy", 1000, scope="plan", job_id="job-unchecked",
        model="gemini-3.7-flash", track="gemini",
    )
    result = sl._check_and_reserve_quota(
        conn, harness="agy", model="gemini-3.7-flash", track="gemini",
        estimated_tokens=1000, estimated_cost_usd=0.25,
        payment_mode="credit_grant", scope="plan", job_id="job-unchecked",
        existing_reservation_id=existing,
    )
    assert result["accepted"] is False
    assert result["reason"] == "credit_exhausted"
    assert conn.execute(
        "SELECT status FROM harness_reservations WHERE id=?", (existing,)
    ).fetchone()[0] == "released"
