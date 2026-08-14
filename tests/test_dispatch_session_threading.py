def test_insert_cost_row_inherits_session_id_from_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))

    from synlynk import _get_db
    from synlynk.db import _insert_cost_row

    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, title, opened_at) VALUES (?, ?, ?)",
        ("session-abc12345", "test session", "2026-08-17T00:00:00"),
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, session_id) "
        "VALUES ('job-test1', 'codex', 'do a thing', 'running', '2026-08-17T00:00:00', 'session-abc12345')"
    )
    conn.commit()
    conn.close()

    _insert_cost_row(
        session_date="2026-08-17", agent="codex", model="gpt-5-codex",
        input_tokens=100, output_tokens=50, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.01, job_id="job-test1",
    )

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM cost_entries WHERE job_id='job-test1'"
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345",)


def test_dispatch_agent_writes_session_id_to_daemon_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))

    from synlynk import _get_db
    from synlynk.session import _write_active_session
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    _write_active_session("session-abc12345")
    conn = _get_db()
    conn.execute(
        "INSERT INTO sessions (session_id, title, opened_at) VALUES (?, ?, ?)",
        ("session-abc12345", "test session", "2026-08-17T00:00:00"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        dispatch_mod,
        "_create_job_worktree",
        lambda *a, **kw: {
            "path": str(tmp_path),
            "branch": "dispatch/test/job-fixed-id",
            "base_branch": "main",
            "base_sha": "deadbeef",
        },
    )
    monkeypatch.setattr(sl, "generate_context", lambda *a, **kw: "context")
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "Popen",
        lambda *a, **kw: type("P", (), {"pid": 12345})(),
    )

    dispatch_mod.dispatch_agent(
        "codex", "do a thing", job_id="job-fixed-id", skip_preflight=True
    )

    conn = _get_db()
    row = conn.execute(
        "SELECT session_id FROM daemon_jobs WHERE job_id='job-fixed-id'"
    ).fetchone()
    conn.close()
    assert row == ("session-abc12345",)
