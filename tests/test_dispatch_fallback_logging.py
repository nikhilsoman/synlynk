"""Durable logging for auto-routing fallback decisions (#2064)."""

import os


def test_local_unreachable_fallback_writes_sentinel_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: False)
    monkeypatch.setattr(
        dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex"
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "codex"
    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_path.exists()
    text = sentinel_path.read_text()
    assert "codex" in text
    assert "local oMLX unreachable" in text
    assert "DISPATCH_ROUTING_FALLBACK" in text


def test_low_capability_fallback_writes_sentinel_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: True)
    monkeypatch.setattr(dispatch, "_get_local_capability_score", lambda task_type, db: 0.1)
    monkeypatch.setattr(
        dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex"
    )
    monkeypatch.setattr(
        dispatch, "_read_local_threshold", lambda config_path=".synlynk/config.json": 0.5
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "codex"
    text = (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "local capability score 0.10" in text
    assert "threshold 0.50" in text
    assert "codex" in text


def test_local_selection_does_not_write_fallback_sentinel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: True)
    monkeypatch.setattr(dispatch, "_get_local_capability_score", lambda task_type, db: 0.8)
    monkeypatch.setattr(
        dispatch, "_read_local_threshold", lambda config_path=".synlynk/config.json": 0.5
    )

    result = dispatch._resolve_dispatch_agent("auto", "implement", None)

    assert result == "local"
    assert not (tmp_path / ".synlynk" / "sentinel.md").exists()


def _dispatch_after_fallback(monkeypatch, *, preflight_ok, score=0.1):
    from synlynk import dispatch

    monkeypatch.setattr(dispatch, "_preflight_local_silent", lambda: preflight_ok)
    monkeypatch.setattr(dispatch, "_get_local_capability_score", lambda task_type, db: score)
    monkeypatch.setattr(
        dispatch, "_read_local_fallback", lambda config_path=".synlynk/config.json": "codex"
    )
    monkeypatch.setattr(
        dispatch, "_read_local_threshold", lambda config_path=".synlynk/config.json": 0.5
    )
    monkeypatch.setattr(
        dispatch,
        "_preflight_dispatch",
        lambda *a, **k: {"passed": True, "sentinel": None, "reason": None},
    )

    class FakeProc:
        pid = 4242

    monkeypatch.setattr(dispatch.subprocess, "Popen", lambda *a, **kw: FakeProc())
    resolved = dispatch._resolve_dispatch_agent("auto", "implement", None)
    job = dispatch.dispatch_agent(
        resolved,
        "implement the fallback logging",
        skip_preflight=True,
        context_mode="none",
        force_agent=True,
    )
    return resolved, job


def test_unreachable_fallback_persists_requested_and_actual_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        '<!-- synlynk:start version="0.23.0-dev" tool="codex" -->\n'
    )
    import synlynk as sl

    resolved, job = _dispatch_after_fallback(monkeypatch, preflight_ok=False)
    assert resolved == "codex"
    assert job["requested_harness"] == "local"
    assert job["actual_harness"] == "codex"
    assert "local oMLX unreachable" in job["fallback_reason"]

    conn = sl._get_db()
    try:
        row = conn.execute(
            "SELECT requested_harness, actual_harness, fallback_reason "
            "FROM daemon_jobs WHERE job_id=?",
            (job["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "local"
    assert row[1] == "codex"
    assert "local oMLX unreachable" in row[2]


def test_low_capability_fallback_persists_score_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        '<!-- synlynk:start version="0.23.0-dev" tool="codex" -->\n'
    )
    resolved, job = _dispatch_after_fallback(monkeypatch, preflight_ok=True, score=0.1)
    assert resolved == "codex"
    assert job["requested_harness"] == "local"
    assert job["actual_harness"] == "codex"
    assert "local capability score 0.10" in job["fallback_reason"]


def test_jobs_listing_surfaces_routing_fallback(monkeypatch, capsys):
    import synlynk as sl

    monkeypatch.setattr(sl.os, "kill", lambda pid, sig: None)
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, pid, enqueued_at, started_at, requested_harness, actual_harness, "
        "fallback_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "job-route1", "codex", "implement fallback logging", "story-1", "running",
            5, "[]", os.getpid(), "2026-10-06T08:00:00", "2026-10-06T08:00:00",
            "local", "codex", "Routing to: codex (local oMLX unreachable)",
        ),
    )
    conn.commit()
    conn.close()

    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "job-route1" in out
    assert "local->codex" in out
