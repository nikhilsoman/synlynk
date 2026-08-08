import pytest

from synlynk.dispatch import _format_job_summary


def test_cli_dispatch_dry_run_prints_preview_and_creates_no_job(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.cli as cli_mod

    called = {"dispatch_agent": False}
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: called.__setitem__("dispatch_agent", True))
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "claude", "--task", "Fix issue #720", "--dry-run"],
    )

    cli_mod.main()

    captured = capsys.readouterr()
    assert called["dispatch_agent"] is False
    assert "agent:" in captured.out
    assert "claude" in captured.out
    assert "task_sha256:" in captured.out
    assert "no job, worktree, or cost entry created" in captured.out


def test_cli_dispatch_dry_run_empty_task_fails_closed_before_preview(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.cli as cli_mod

    called = {"dispatch_agent": False}
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: called.__setitem__("dispatch_agent", True))
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "claude", "--task", "   ", "--dry-run"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli_mod.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "empty or whitespace-only" in captured.out
    assert "task_sha256:" not in captured.out
    assert called["dispatch_agent"] is False


def test_render_dispatch_preview_includes_task_digest_and_no_context_file(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview
    import hashlib

    monkeypatch.chdir(tmp_path)
    task = "Fix issue #720 fail-closed on empty tasks"

    preview = _render_dispatch_preview("claude", task, "task")

    expected_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
    assert preview["agent"] == "claude"
    assert preview["task"] == task
    assert preview["task_len"] == len(task)
    assert preview["task_sha256"] == expected_digest
    assert preview["context_mode"] == "task"
    assert preview["context_digest"] is None
    assert preview["context_bytes"] is None


def test_render_dispatch_preview_includes_context_digest_when_context_md_exists(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview
    import hashlib

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    context_bytes = b"# Context\nactive tasks here\n"
    (tmp_path / ".synlynk" / "context.md").write_bytes(context_bytes)

    preview = _render_dispatch_preview("claude", "some task", "full")

    assert preview["context_digest"] == hashlib.sha256(context_bytes).hexdigest()
    assert preview["context_bytes"] == len(context_bytes)


def test_render_dispatch_preview_skips_context_when_mode_none(tmp_path, monkeypatch):
    from synlynk.dispatch import _render_dispatch_preview

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "context.md").write_bytes(b"unused")

    preview = _render_dispatch_preview("claude", "some task", "none")

    assert preview["context_digest"] is None
    assert preview["context_bytes"] is None


def test_render_task_receipt_instruction_contains_marker_and_digest():
    import synlynk.dispatch as dispatch_mod

    instruction = dispatch_mod._render_task_receipt_instruction("abc123")

    assert "SYNLYNK_TASK_RECEIVED: abc123" in instruction
    assert "very first output" in instruction


def test_format_prompt_for_agent_prepends_receipt_instruction_for_all_agents():
    import synlynk.dispatch as dispatch_mod

    for agent in ("claude", "codex", "agy", "grok"):
        prompt = dispatch_mod._format_prompt_for_agent(
            agent, "context", "story-1", "do the thing", "", "",
            task_sha256="deadbeef",
        )
        assert prompt.startswith("## Task Receipt (required)")
        assert "SYNLYNK_TASK_RECEIVED: deadbeef" in prompt
        assert "do the thing" in prompt


def test_dispatch_agent_writes_receipt_instruction_to_prompt_file(tmp_path, monkeypatch):
    import hashlib
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        dispatch_mod,
        "_create_job_worktree",
        lambda *a, **kw: {
            "path": str(tmp_path),
            "branch": "dispatch/test/job-x",
            "base_branch": "main",
            "base_sha": "deadbeef",
        },
    )
    monkeypatch.setattr(sl, "generate_context", lambda *a, **kw: "context")
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "Popen",
        lambda *a, **kw: type("P", (), {"pid": 99999999})(),
    )

    task = "implement the receipt protocol"
    expected_digest = hashlib.sha256(task.encode("utf-8")).hexdigest()

    dispatch_mod.dispatch_agent("claude", task, force_agent=True, skip_preflight=True)

    prompt_files = list(tmp_path.glob(".synlynk/prompts/*"))
    assert prompt_files, "expected a prompt file to be written"
    prompt_text = prompt_files[0].read_text()
    assert f"SYNLYNK_TASK_RECEIVED: {expected_digest}" in prompt_text


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


def test_format_job_summary_includes_base_and_suite_result_when_present():
    from synlynk.dispatch import _format_job_summary

    summary = _format_job_summary(
        "job-abc",
        "codex",
        "story-1",
        0,
        12.5,
        100,
        200,
        0.01,
        files_touched=["a.py"],
        base_branch="feat/example",
        base_sha="deadbeefcafe",
        suite_result={"passed": 5, "failed": 0, "skipped": 1, "ran_at": "2026-07-23T00:00:00"},
    )

    assert "base:     feat/example @ deadbeef" in summary
    assert "suite:    5 passed, 0 failed, 1 skipped" in summary


def test_format_job_summary_includes_task_sha256_and_preview_when_present():
    summary = _format_job_summary(
        "job-abc",
        "codex",
        "story-1",
        0,
        12.5,
        100,
        200,
        0.01,
        files_touched=["a.py"],
        task_sha256="a3f9c2e1b8d4",
        task_preview="Fix issue #720 fail-closed on empty tasks",
    )

    assert "task_sha256: a3f9c2e1b8d4" in summary
    assert "task:     Fix issue #720 fail-closed on empty tasks" in summary


def test_format_job_summary_omits_task_fields_when_absent():
    summary = _format_job_summary(
        "job-abc",
        "codex",
        "story-1",
        0,
        12.5,
        100,
        200,
        0.01,
        files_touched=["a.py"],
    )

    assert "task_sha256:" not in summary
    assert "task:     " not in summary


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


def test_dispatch_agent_explicit_story_id_provisions_missing_story(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    job = sl.dispatch_agent("claude", "task text with #999", story_id="story-manual-1", context_mode="none")

    assert job["story_id"] == "story-manual-1"
    conn = sl._get_db()
    try:
        assert conn.execute(
            "SELECT 1 FROM stories WHERE story_id=?", ("story-manual-1",)
        ).fetchone() is not None
    finally:
        conn.close()


def test_dispatch_agent_requires_gh_write_false_is_noop(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent("agy", "write docs", story_id="story-manual-1", context_mode="none")

    assert job["agent"] == "agy"


def test_dispatch_agent_stores_scope_paths_and_requires_gh_write_on_job(project_dir, monkeypatch):
    monkeypatch.chdir(project_dir)
    import synlynk.dispatch as dispatch_mod

    saved = {}

    def fake_save_jobs(jobs):
        saved["jobs"] = jobs

    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: {
        "_load_jobs": lambda: [],
        "_save_jobs": fake_save_jobs,
    }.get(name, default))

    class FakeProc:
        pid = 12345

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", lambda agent, perms: [])
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_permissions", lambda *a, **kw: [])

    job = dispatch_mod.dispatch_agent(
        "codex", "write a spec only",
        scope_paths=["docs/superpowers/specs/**"],
        requires_gh_write=False,
        skip_preflight=True,
    )

    assert job["scope_paths"] == ["docs/superpowers/specs/**"]
    assert job["requires_gh_write"] is False


def test_dispatch_agent_rejects_empty_task(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    called = {"worktree": False}
    monkeypatch.setattr(
        dispatch_mod, "_create_job_worktree",
        lambda *a, **kw: called.__setitem__("worktree", True) or {"path": "/tmp/x", "base_branch": "main", "base_sha": "abc"}
    )

    with pytest.raises(ValueError, match=r"empty or whitespace-only"):
        sl.dispatch_agent("claude", "", context_mode="none")

    assert called["worktree"] is False


def test_dispatch_agent_rejects_whitespace_only_task(project_dir, monkeypatch):
    import synlynk as sl

    with pytest.raises(ValueError, match=r"empty or whitespace-only"):
        sl.dispatch_agent("claude", "   \n\t  ", context_mode="none")


def test_cli_dispatch_passes_requires_gh_write_flag(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["requires_gh_write"] = kwargs.get("requires_gh_write")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "grok", "--task", "review and merge PR #500",
         "--requires-gh-write", "--force-agent"],
    )

    cli_mod.main()

    assert captured["requires_gh_write"] is True


def test_create_job_worktree_anchors_to_base_tip_sha_and_returns_details(git_worktree_repo, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import subprocess
    import os as _os

    monkeypatch.chdir(git_worktree_repo)
    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)
    tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    result = dispatch_mod._create_job_worktree("job-test1", "codex")

    assert result["path"] == _os.path.join("worktrees", "job-test1")
    assert result["base_branch"] == "feat/example"
    assert result["base_sha"] == tip
    assert _os.path.isdir(result["path"])


def test_dispatch_agent_records_base_branch_and_sha_on_job(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 4242

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "reasons": []})
    monkeypatch.setattr(
        dispatch_mod, "_create_job_worktree",
        lambda job_id, agent, base=None: {
            "path": "worktrees/job-fake",
            "branch": f"dispatch/{agent}/job-fake",
            "base_branch": base or "feat/example",
            "base_sha": "deadbeef",
        },
    )

    job = dispatch_mod.dispatch_agent("codex", "do the thing", force_agent=True, base="feat/example")

    assert job["base_branch"] == "feat/example"
    assert job["base_sha"] == "deadbeef"
    assert job["suite_result"] is None


def test_cli_dispatch_passes_base_flag(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch(agent, task, **kwargs):
        captured.update(kwargs)
        return {"id": "job-x", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "do it", "--base", "feat/example", "--force-agent"],
    )

    cli_mod.main()

    assert captured["base"] == "feat/example"


def test_build_subprocess_env_allowlists_base_vars_only(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leaked-if-present")
    monkeypatch.setenv("SOME_RANDOM_API_TOKEN", "also-leaked-if-present")

    env = _build_subprocess_env("codex", {}, requires_gh_write=False, story_id="story-1")

    assert env.get("PATH") == "/usr/bin"
    assert env.get("HOME") == "/home/test"
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "SOME_RANDOM_API_TOKEN" not in env


def test_build_subprocess_env_includes_env_passthrough_vars(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setenv("MY_AGENT_TOKEN", "should-be-included")
    fake_baselines = {
        "codex": {"env_passthrough": ["MY_AGENT_TOKEN"], "headless_contract": {}},
    }
    monkeypatch.setattr(dispatch_mod, "AGENT_CAPABILITY_BASELINES", fake_baselines)

    env = _build_subprocess_env("codex", {}, requires_gh_write=False, story_id="story-1")

    assert env.get("MY_AGENT_TOKEN") == "should-be-included"


def test_build_subprocess_env_applies_headless_contract_required_vars():
    from synlynk.dispatch import _build_subprocess_env
    import synlynk.dispatch as dispatch_mod

    fake_baselines = {
        "agy": {"env_passthrough": [], "headless_contract": {"env_vars_required": ["PYTHONUNBUFFERED=1"]}},
    }
    dispatch_mod_patch_target = dispatch_mod.AGENT_CAPABILITY_BASELINES
    dispatch_mod.AGENT_CAPABILITY_BASELINES = fake_baselines
    try:
        env = _build_subprocess_env("agy", {}, requires_gh_write=False, story_id="story-1")
        assert env.get("PYTHONUNBUFFERED") == "1"
    finally:
        dispatch_mod.AGENT_CAPABILITY_BASELINES = dispatch_mod_patch_target


def test_build_subprocess_env_overrides_win_over_allowlist(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env

    monkeypatch.setenv("PATH", "/usr/bin")

    env = _build_subprocess_env("codex", {"env": {"PATH": "/custom/bin"}}, requires_gh_write=False, story_id="story-1")

    assert env.get("PATH") == "/custom/bin"


def test_dispatch_agent_requires_gh_write_true_capable_agent_unchanged(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "grok", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert job["agent"] == "grok"


def test_dispatch_agent_requires_gh_write_reroutes_incapable_agent(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "agy", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True,
    )

    assert job["agent"] == "claude"
    assert sl.AGENT_CAPABILITY_BASELINES[job["agent"]]["can_gh_write"] is True
    captured = capsys.readouterr()
    assert "rerouted" in captured.out
    assert "#426" in captured.out


def test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    job = sl.dispatch_agent(
        "codex", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert job["agent"] == "codex"
    captured = capsys.readouterr()
    assert "codex" in captured.err
    assert "#426" in captured.err


def test_dispatch_agent_requires_gh_write_raises_when_no_capable_agent(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    no_capable = {
        name: {**baseline, "can_gh_write": False}
        for name, baseline in sl.AGENT_CAPABILITY_BASELINES.items()
    }
    monkeypatch.setattr(sl, "AGENT_CAPABILITY_BASELINES", no_capable)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    with pytest.raises(ValueError, match="can_gh_write"):
        sl.dispatch_agent(
            "agy", "review and merge PR #500", story_id="story-manual-1",
            context_mode="none", requires_gh_write=True,
        )


def test_permissions_to_flags_agy_warns_on_empty_permissions(capsys):
    from synlynk.dispatch import _permissions_to_flags

    assert _permissions_to_flags("agy", []) == []
    out = capsys.readouterr().out
    assert "no write/run permissions granted" in out


def test_permissions_to_flags_agy_write_permissions_keep_skip_flag_without_warning(capsys):
    from synlynk.dispatch import _permissions_to_flags

    assert _permissions_to_flags("agy", ["write:src/"]) == ["--dangerously-skip-permissions"]
    out = capsys.readouterr().out
    assert out == ""


def test_permissions_to_flags_agy_raises_on_read_only_permissions():
    from synlynk.dispatch import _permissions_to_flags, PermissionEnforcementError

    with pytest.raises(PermissionEnforcementError, match="agy"):
        _permissions_to_flags("agy", ["read:*"])


def test_permissions_to_flags_local_raises_on_any_permissions():
    from synlynk.dispatch import _permissions_to_flags, PermissionEnforcementError

    with pytest.raises(PermissionEnforcementError, match="local"):
        _permissions_to_flags("local", ["read:*"])

    with pytest.raises(PermissionEnforcementError, match="local"):
        _permissions_to_flags("local", ["write:src/"])


def test_permissions_to_flags_local_no_permissions_is_noop():
    from synlynk.dispatch import _permissions_to_flags

    assert _permissions_to_flags("local", []) == []
    assert _permissions_to_flags("local", None) == []


def test_resolve_dispatch_base_ref_stacks_on_current_feature_branch(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto"
    )

    assert base_ref == "feat/example"


def test_resolve_dispatch_base_ref_falls_back_to_mainline_on_main_branch(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)

    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no remote")
        return real_run(cmd, **kw)

    monkeypatch.setattr(dispatch_mod.subprocess, "run", fake_run)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto"
    )

    assert base_ref == "main"


def test_resolve_dispatch_base_ref_stacking_never_always_uses_mainline(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="never"
    )

    assert base_ref == "main"


def test_resolve_dispatch_base_ref_stacking_always_errors_on_mainline(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess
    import pytest

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)

    with pytest.raises(RuntimeError, match="stacking is 'always'"):
        dispatch_mod._resolve_dispatch_worktree_base_ref(
            str(git_worktree_repo), stacking_mode="always"
        )


def test_resolve_dispatch_base_ref_explicit_base_wins(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto", explicit_base="main"
    )

    assert base_ref == "main"


def test_run_dispatch_gate_parses_pytest_summary_and_flags_failures(tmp_path, monkeypatch):
    import synlynk
    import synlynk.dispatch as dispatch_mod

    class FakeResult:
        returncode = 1
        stdout = "2 passed, 1 failed, 1 skipped in 0.05s"
        stderr = ""

    monkeypatch.setattr(dispatch_mod.subprocess, "run", lambda *a, **kw: FakeResult())

    job = {"worktree_path": str(tmp_path)}
    result = dispatch_mod._run_dispatch_gate(job, "pytest tests/ -q")

    assert result == {"passed": 2, "failed": 1, "skipped": 1}


def test_run_dispatch_gate_returns_none_when_no_gate_cmd_configured(tmp_path):
    import synlynk
    import synlynk.dispatch as dispatch_mod

    job = {"worktree_path": str(tmp_path)}
    result = dispatch_mod._run_dispatch_gate(job, "")

    assert result is None


def test_check_dispatch_base_still_fresh_true_when_sha_matches_current_tip(git_worktree_repo):
    import synlynk
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    job = {"base_branch": "main", "base_sha": tip}
    assert dispatch_mod._check_dispatch_base_still_fresh(job, repo_path=str(git_worktree_repo)) is True


def test_check_dispatch_base_still_fresh_false_when_branch_advanced(git_worktree_repo):
    import synlynk
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    old_tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    (git_worktree_repo / "new_file.txt").write_text("more work\n")
    subprocess.run(["git", "add", "."], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "advance branch"], cwd=git_worktree_repo, capture_output=True, check=True)

    job = {"base_branch": "main", "base_sha": old_tip}
    assert dispatch_mod._check_dispatch_base_still_fresh(job, repo_path=str(git_worktree_repo)) is False


def test_sequential_dispatch_jobs_stack_with_zero_conflicts(git_worktree_repo, monkeypatch, tmp_path):
    """Simulates Task N and Task N+1 of a plan: job2 should be anchored to
    the tip left behind after job1's commit is merged, so merging job2
    produces no conflicts even though both jobs touch the same file
    """
    import synlynk
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    monkeypatch.chdir(git_worktree_repo)

    # --- Job 1 ---
    worktree1 = dispatch_mod._create_job_worktree("job-seq1", "codex")
    shared_file = os_path_join(worktree1["path"], "shared.py")
    with open(shared_file, "w") as f:
        f.write("value = 1\n")
    subprocess.run(["git", "add", "."], cwd=worktree1["path"], capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "job1: set value=1"], cwd=worktree1["path"], capture_output=True, check=True)

    # Simulate the reviewer merging job1's commit back onto the feature branch
    subprocess.run(["git", "checkout", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)
    merge1 = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge job1", worktree1["branch"]],
        cwd=git_worktree_repo, capture_output=True, text=True,
    )
    assert merge1.returncode == 0, merge1.stderr

    # --- Job 2, dispatched after job1 merged ---
    worktree2 = dispatch_mod._create_job_worktree("job-seq2", "codex")

    assert worktree2["base_branch"] == "feat/example"
    new_tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "feat/example"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert worktree2["base_sha"] == new_tip

    with open(os_path_join(worktree2["path"], "shared.py"), "w") as f:
        f.write("value = 1\nextra = 2\n")
    subprocess.run(["git", "add", "."], cwd=worktree2["path"], capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "job2: add extra=2"], cwd=worktree2["path"], capture_output=True, check=True)

    merge2 = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge job2", worktree2["branch"]],
        cwd=git_worktree_repo, capture_output=True, text=True,
    )
    assert merge2.returncode == 0, merge2.stderr
    assert "CONFLICT" not in (merge2.stdout + merge2.stderr)


def os_path_join(*parts):
    import os
    return os.path.join(*parts)


def test_check_dispatch_base_still_fresh_true_when_no_base_recorded():
    import synlynk
    import synlynk.dispatch as dispatch_mod

    job = {"base_branch": None, "base_sha": None}
    assert dispatch_mod._check_dispatch_base_still_fresh(job) is True
