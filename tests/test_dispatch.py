from synlynk.dispatch import _format_job_summary


def test_format_job_summary_includes_watch_reminder():
    summary = _format_job_summary(
        "job-d63c4cf4",
        "codex",
        "story-e528c886",
        0,
        123,
        3916492,
        33996,
        12.26,
        files_touched=["a.py"],
    )
    assert "synlynk watch" in summary
    assert "$12.26" in summary


def test_format_job_summary_falls_back_when_jobs_not_allowlisted(monkeypatch):
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "_pkg",
        lambda name, default=None: ((lambda: {"fenced_commands": []}) if name == "load_config" else default),
    )
    summary = _format_job_summary(
        "job-x",
        "codex",
        None,
        0,
        10,
        100,
        50,
        0.01,
        files_touched=[],
    )
    assert "job job-x complete" in summary
    assert "synlynk watch" not in summary


def test_exec_command_prints_fence_when_exec_allowlisted(tmp_path, monkeypatch, capsys):
    import synlynk as sl
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(sl, "generate_context", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(sl, "set_state", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(sl, "log_telemetry_event", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_sentinel_patterns", lambda **kw: None)
    monkeypatch.setattr(sl, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(sl, "WatchDaemon", None)
    monkeypatch.setattr(sl, "update_costs", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": ["exec"]})

    exec_command(["echo", "--print", "Input tokens: 10 Output tokens: 5"])

    captured = capsys.readouterr()
    assert "-- exec complete" in captured.out
    assert "cost:" in captured.out


def test_exec_command_falls_back_when_exec_not_allowlisted(tmp_path, monkeypatch, capsys):
    import synlynk as sl
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(sl, "generate_context", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(sl, "set_state", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(sl, "log_telemetry_event", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_sentinel_patterns", lambda **kw: None)
    monkeypatch.setattr(sl, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(sl, "WatchDaemon", None)
    monkeypatch.setattr(sl, "update_costs", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    exec_command(["echo", "--print", "Input tokens: 10 Output tokens: 5"])

    captured = capsys.readouterr()
    assert "⚡ Tokens: 10 in / 5 out" in captured.out
    assert "-- exec complete" not in captured.out


def test_dispatch_agent_auto_provisions_story_id_when_not_given(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import synlynk.story_provisioning as sp

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sp.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")))

    job = sl.dispatch_agent("claude", "rebind DB_PATH per #395", context_mode="none")

    assert job["story_id"] == "story-issue-395"
    conn = sl._get_db()
    row = conn.execute(
        "SELECT story_id FROM stories WHERE story_id=?",
        ("story-issue-395",)
    ).fetchone()
    conn.close()
    assert row is not None


def test_dispatch_agent_reuses_existing_story_id_for_repeat_issue_dispatch(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import synlynk.story_provisioning as sp

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sp.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("gh not found")))

    job1 = sl.dispatch_agent("claude", "first pass on #395", context_mode="none")
    job2 = sl.dispatch_agent("codex", "follow-up fix on #395", context_mode="none")

    assert job1["story_id"] == job2["story_id"] == "story-issue-395"


def test_dispatch_agent_explicit_story_id_bypasses_auto_provisioning(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "resolve_or_create_story_id", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("resolver should not be called")))

    job = sl.dispatch_agent("claude", "task text with #999", story_id="story-manual-1", context_mode="none")

    assert job["story_id"] == "story-manual-1"
