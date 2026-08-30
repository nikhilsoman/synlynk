import pytest
import synlynk as sl

from synlynk.dispatch import _format_job_summary


def test_dispatch_agent_raises_when_task_type_not_in_policy_allocation_table(tmp_path, monkeypatch, isolated_db):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with pytest.raises(RuntimeError, match="not an authorized task_type"):
        sl.dispatch_agent(
            "codex", "do something", task_type="not_a_real_task_type",
            context_mode="none",
        )


def test_format_job_summary_flags_cancelled_github_mcp_write():
    summary = _format_job_summary(
        "job-gh-cancelled", "codex", None, 0, 1.0, 0, 0, 0.0,
        log_text='{"error":{"message":"user cancelled MCP tool call"}}',
    )

    assert "status:   OK (exit 0) — GH WRITE CANCELLED" in summary


def test_format_job_summary_does_not_false_positive_on_success():
    summary = _format_job_summary(
        "job-success", "codex", None, 0, 1.0, 0, 0, 0.0,
        log_text="review submitted successfully",
    )

    assert "status:   OK (exit 0)\n" in summary
    assert "GH WRITE CANCELLED" not in summary


def test_format_job_summary_does_not_double_flag_failed_job():
    summary = _format_job_summary(
        "job-gh-failed", "codex", None, 1, 1.0, 0, 0, 0.0,
        log_text='{"error":{"message":"user cancelled MCP tool call"}}',
    )

    assert "status:   FAILED (exit 1)" in summary
    assert "GH WRITE CANCELLED" not in summary


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


def test_format_prompt_for_agent_adds_codex_gh_write_guardrail():
    import synlynk.dispatch as dispatch_mod

    prompt = dispatch_mod._format_prompt_for_agent(
        "codex", "context", "story-1", "review the pull request", "", "",
        requires_gh_write=True,
    )

    assert "gh pr review" in prompt
    assert "add_review_to_pr" not in prompt
    assert "add_comment_to_issue" not in prompt


def test_format_prompt_for_agent_omits_codex_gh_write_guardrail_by_default():
    import synlynk.dispatch as dispatch_mod

    prompt = dispatch_mod._format_prompt_for_agent(
        "codex", "context", "story-1", "review the local code", "", "",
    )

    assert "gh pr review" not in prompt


def test_format_prompt_for_agent_auto_detects_issue_closing_task_shape():
    import synlynk.dispatch as dispatch_mod

    task = (
        "Close GitHub issues #935 and #701, citing the implementation PR "
        "and verification job."
    )

    assert dispatch_mod._task_requires_gh_write(task) is True
    prompt = dispatch_mod._format_prompt_for_agent(
        "grok", "context", "story-1", task, "", "",
        requires_gh_write=False,
    )

    assert "GitHub Write Instructions (MANDATORY)" in prompt
    assert "gh issue close" in prompt
    assert "Do not use MCP GitHub tools" in prompt
    assert "close_issue" in prompt


def test_gh_write_instruction_present_for_grok_when_required():
    from synlynk.dispatch import _format_prompt_for_agent

    prompt = _format_prompt_for_agent(
        "grok", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt
    assert "Do not use MCP GitHub tools" in prompt


def test_gh_write_instruction_present_for_agy_when_required():
    from synlynk.dispatch import _format_prompt_for_agent

    prompt = _format_prompt_for_agent(
        "agy", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt


def test_gh_write_instruction_present_for_codex_when_required():
    from synlynk.dispatch import _format_prompt_for_agent

    prompt = _format_prompt_for_agent(
        "codex", "context", "story-1", "review PR 1038", "", "",
        requires_gh_write=True,
    )
    assert "GitHub Write Instructions" in prompt


def test_gh_write_instruction_absent_when_not_required():
    from synlynk.dispatch import _format_prompt_for_agent

    for agent in ("codex", "agy", "grok"):
        prompt = _format_prompt_for_agent(
            agent, "context", "story-1", "review code locally", "", "",
            requires_gh_write=False,
        )
        assert "GitHub Write Instructions" not in prompt


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


def test_exec_command_context_includes_charter(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(tmp_path / "fake_home")))
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary",
        "---\nschema_version: 1\nrole: pm\ndescription: test\n"
        "durability: dispatch-only\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nDo PM things.\n\n"
        "## Authority & Escalation\n\nEscalates per policy.\n\n"
        "## Workflow Ownership\n\nOwns this test.\n",
        actor="test", parent_revision=0,
    )
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

    exec_command(["echo", "hi"])
    context_text = (project_dir / ".synlynk" / "context.md").read_text()
    assert "## Role Charter" in context_text
    assert "Do PM things." in context_text


def test_dispatch_agent_auto_provisions_story_id_when_not_given(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import synlynk.story_provisioning as sp

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
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


def test_dispatch_agent_defers_when_quota_exhausted(project_dir, monkeypatch):
    """Even with --force-agent, dispatch_agent must not bypass the quota gate."""
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=1_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    result = sl.dispatch_agent(
        "codex", "do a small task", force_agent=True, skip_preflight=True
    )

    assert result.get("deferred") is True
    assert result["reason"]
    assert "retry_after" in result

    row = conn.execute(
        "SELECT status, blocked_reason FROM daemon_jobs WHERE agent='codex' "
        "ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    assert row == ("queued", "quota_exhausted")
    conn.close()


def test_dispatch_agent_existing_job_quota_exhaustion_updates_row(project_dir):
    import synlynk as sl

    conn = sl._get_db()
    job_id = "job-existing-quota-exhausted"
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at) "
        "VALUES (?, ?, ?, 'running', ?)",
        (job_id, "codex", "queued task", "2026-08-08T00:00:00"),
    )
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=1_000, used_tokens=1_000, unit="tokens", conn=conn
    )

    result = sl.dispatch_agent(
        "codex", "retry queued task", job_id=job_id, force_agent=True, skip_preflight=True
    )

    assert result["deferred"] is True
    row = conn.execute(
        "SELECT status, blocked_reason FROM daemon_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    assert row == ("queued", "quota_exhausted")
    assert conn.execute("SELECT COUNT(*) FROM daemon_jobs WHERE job_id=?", (job_id,)).fetchone()[0] == 1
    conn.close()


def test_dispatch_agent_reuses_existing_open_reservation(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )
    job_id = "job-existing-reservation"
    sl._open_reservation(conn, "codex", 2_000, scope="plan", scope_id="run-1", job_id=job_id)
    before = conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE job_id=? AND status='open'", (job_id,)
    ).fetchone()[0]

    class _P:
        pid = 12345

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *args, **kwargs: _P())
    sl.dispatch_agent("codex", "dispatch reserved task", job_id=job_id, force_agent=True, skip_preflight=True)

    after = conn.execute(
        "SELECT COUNT(*) FROM harness_reservations WHERE job_id=? AND status='open'", (job_id,)
    ).fetchone()[0]
    assert after == before == 1
    conn.close()


def test_dispatch_agent_opens_reservation_when_headroom_exists(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=100_000, used_tokens=0, unit="tokens", conn=conn
    )

    class _P:
        pid = 12345

    monkeypatch.setattr(sl.subprocess, "Popen", lambda *args, **kwargs: _P())

    sl.dispatch_agent("codex", "do a small task", force_agent=True, skip_preflight=True)

    reservations = conn.execute(
        "SELECT harness, status FROM harness_reservations WHERE harness='codex'"
    ).fetchall()
    assert len(reservations) == 1
    assert reservations[0] == ("codex", "open")
    conn.close()


def test_dispatch_agent_reuses_existing_story_id_for_repeat_issue_dispatch(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import synlynk.story_provisioning as sp

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
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
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
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
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

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


def test_cli_dispatch_passes_task_type_flag(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["task_type"] = kwargs.get("task_type")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "check PR #935",
         "--task-type", "review", "--force-agent"],
    )

    cli_mod.main()

    assert captured["task_type"] == "review"


def test_cli_dispatch_infers_pr_gh_write_target_for_review(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["gh_write_target_kind"] = kwargs.get("gh_write_target_kind")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "review PR 1038",
         "--task-type", "review", "--requires-gh-write", "--issue", "1038"],
    )

    cli_mod.main()

    assert captured["gh_write_target_kind"] == "pr"


def test_cli_dispatch_explicitly_overrides_gh_write_target_kind(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["gh_write_target_kind"] = kwargs.get("gh_write_target_kind")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "review PR 1038",
         "--task-type", "review", "--gh-write-target-kind", "issue"],
    )

    cli_mod.main()

    assert captured["gh_write_target_kind"] == "issue"


def test_cli_dispatch_defaults_gh_write_target_to_issue(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["gh_write_target_kind"] = kwargs.get("gh_write_target_kind")
        return {"id": "job-test", "pid": 1, "fence": None}

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr(
        "sys.argv",
        ["synlynk", "dispatch", "codex", "--task", "do the work"],
    )

    cli_mod.main()

    assert captured["gh_write_target_kind"] == "issue"


def test_review_dispatch_job_stores_task_type(project_dir, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    saved = {}

    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: {
        "_load_jobs": lambda: [],
        "_save_jobs": lambda jobs: saved.setdefault("jobs", jobs),
    }.get(name, default))

    class FakeProc:
        pid = 12345

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", lambda agent, perms: [])
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_permissions", lambda *a, **kw: [])

    job = dispatch_mod.dispatch_agent(
        "codex", "check PR #935", task_type="review", skip_preflight=True,
    )

    assert job["task_type"] == "review"
    assert saved["jobs"][0]["task_type"] == "review"


_AGY_WRITE_BUNDLE_ROLES = ["implement", "test", "css", "templates", "content"]
_AGY_DEFAULT_PERMISSIONS = ["read:*", "run:tests", "write:docs/", "write:src/"]


def _dispatch_capturing_permissions(monkeypatch, *, task_type=None, grants=None):
    """Dispatch agy with its write-capable default roles and capture permissions."""
    import synlynk.dispatch as dispatch_mod

    real_pkg = dispatch_mod._pkg
    saved = {}
    captured = {}

    def fake_pkg(name, default=None):
        if name == "_load_jobs":
            return lambda: []
        if name == "_save_jobs":
            return lambda jobs: saved.setdefault("jobs", jobs)
        if name == "_get_db":
            return lambda: None
        if name == "load_config":
            return lambda: {"roles": {"agy": list(_AGY_WRITE_BUNDLE_ROLES)}}
        return real_pkg(name, default)

    def capture_flags(agent, perms):
        captured["permissions"] = list(perms)
        return []

    monkeypatch.setattr(dispatch_mod, "_pkg", fake_pkg)
    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", capture_flags)

    class FakeProc:
        pid = 12345

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())

    kwargs = {"skip_preflight": True, "grants": grants}
    if task_type is not None:
        kwargs["task_type"] = task_type
    dispatch_mod.dispatch_agent("agy", "review this PR", **kwargs)
    return captured.get("permissions")


def test_review_task_type_scopes_permissions_to_read_only(project_dir, monkeypatch):
    permissions = _dispatch_capturing_permissions(monkeypatch, task_type="review")

    assert permissions == ["read:*"]
    assert not any(perm.startswith("write:") for perm in permissions)


def test_review_task_type_still_applies_explicit_grants(project_dir, monkeypatch):
    permissions = _dispatch_capturing_permissions(
        monkeypatch, task_type="review", grants=["run:tests"],
    )

    assert "read:*" in permissions
    assert "run:tests" in permissions
    assert not any(perm.startswith("write:") for perm in permissions)


@pytest.mark.parametrize("task_type", [None, "", "implement"])
def test_non_review_task_type_keeps_default_role_bundle_permissions(
    project_dir, monkeypatch, task_type,
):
    permissions = _dispatch_capturing_permissions(monkeypatch, task_type=task_type)

    assert permissions == _AGY_DEFAULT_PERMISSIONS
    assert "write:src/" in permissions
    assert "write:docs/" in permissions


@pytest.mark.parametrize(
    ("task_type", "age_minutes", "expected_killed"),
    [("review", 60, False), ("review", 100, True), (None, 60, True)],
)
def test_check_job_stall_uses_review_timeout_without_changing_default(
    tmp_path, monkeypatch, task_type, age_minutes, expected_killed,
):
    import os
    import signal
    import time
    import synlynk as sl

    log_file = tmp_path / "job-stall.log"
    log_file.write_bytes(b"")
    old_time = time.time() - age_minutes * 60
    os.utime(log_file, (old_time, old_time))
    job = {
        "id": "job-stall",
        "agent": "codex",
        "status": "running",
        "pid": 12345,
        "started_at": old_time,
        "log_file": str(log_file),
    }
    if task_type is not None:
        job["task_type"] = task_type

    killed = []
    monkeypatch.setattr(sl.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: None)

    result = sl._check_job_stall(
        job,
        {"stall_timeout_minutes": 30},
        str(tmp_path / "sentinel.md"),
    )

    assert result is expected_killed
    assert bool(killed) is expected_killed
    if expected_killed:
        assert killed == [(12345, signal.SIGKILL)]
    else:
        assert job["status"] == "running"


def test_check_job_stall_extends_timeout_when_gh_write_verified_true(project_dir, monkeypatch, tmp_path):
    import os
    import time as _time
    import synlynk.dispatch as dispatch_mod

    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": 999999,
        "requires_gh_write": True, "gh_write_target": "issue:701",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: True)
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is False
    assert job["status"] == "running"


def test_check_job_stall_kills_when_gh_write_verified_false(project_dir, monkeypatch, tmp_path):
    import os
    import time as _time
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": None,
        "requires_gh_write": True, "gh_write_target": "issue:701",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: False)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: None)
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is True
    assert job["status"] == "failed"
    assert job.get("gh_write_verified") == "false"


def test_check_job_stall_falls_through_to_git_state_when_gh_write_unknown(project_dir, monkeypatch, tmp_path):
    import os
    import time as _time
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    log_file = tmp_path / "job.log"
    log_file.write_text("working...")
    old_mtime = _time.time() - 3600
    os.utime(log_file, (old_mtime, old_mtime))
    job = {
        "id": "job-abc123", "status": "running", "log_file": str(log_file),
        "agent": "grok", "pid": None,
        "requires_gh_write": True, "gh_write_target": "issue:701",
        "worktree_path": "/tmp/fake-wt", "worktree_branch": "dispatch/grok/job-abc123",
        "started_at": "2026-08-15T00:00:00",
    }
    monkeypatch.setattr(dispatch_mod, "gh_write_verified", lambda target, expect, **kw: None)
    monkeypatch.setattr(
        sl, "_inspect_worktree_git_state",
        lambda *a, **kw: {"has_activity": True, "commits_ahead": 1, "dirty": False},
    )
    stalled = dispatch_mod._check_job_stall(job, {"stall_timeout_minutes": 30}, str(tmp_path / "sentinel.md"))
    assert stalled is False


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

    assert result["path"] == _os.path.abspath(_os.path.join("worktrees", "job-test1"))
    assert result["base_branch"] == "feat/example"
    assert result["base_sha"] == tip
    assert _os.path.isdir(result["path"])


def test_create_job_worktree_serializes_git_ref_operation_and_retries_contention(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    monkeypatch.chdir(git_worktree_repo)
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda *a: ("worktrees/wt", "branch"))
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_worktree_base_ref", lambda *a, **k: "HEAD")
    monkeypatch.setattr(dispatch_mod, "_assert_dispatch_worktree_base_is_fresh", lambda *a: None)

    lock_events = []
    lock_held = {"value": False}
    class FakeLock:
        def __enter__(self):
            lock_held["value"] = True
            lock_events.append("acquire")
        def __exit__(self, *exc):
            lock_held["value"] = False
            lock_events.append("release")
    monkeypatch.setattr(dispatch_mod, "git_ref_operation_lock", lambda *a: FakeLock())
    monkeypatch.setattr(dispatch_mod.random, "uniform", lambda *a: 0.01)
    monkeypatch.setattr(dispatch_mod.time, "sleep", lambda delay: lock_events.append(("sleep", delay)))

    add_attempts = []
    def fake_run(cmd, **kwargs):
        if cmd[1:3] == ["worktree", "add"]:
            add_attempts.append(lock_held["value"])
            if len(add_attempts) < 3:
                return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "File exists"})()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(dispatch_mod.subprocess, "run", fake_run)

    result = dispatch_mod._create_job_worktree("job-test", "codex")

    assert result["branch"] == "branch"
    assert len(add_attempts) == 3
    assert all(add_attempts)
    assert lock_events[0] == "acquire"
    assert lock_events[-1] == "release"


def test_create_job_worktree_contention_exhaustion_raises_runtime_error(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    monkeypatch.chdir(git_worktree_repo)
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda *a: ("worktrees/wt", "branch"))
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_worktree_base_ref", lambda *a, **k: "HEAD")
    monkeypatch.setattr(dispatch_mod, "_assert_dispatch_worktree_base_is_fresh", lambda *a: None)
    monkeypatch.setattr(dispatch_mod, "git_ref_operation_lock", lambda *a: __import__("contextlib").nullcontext())
    monkeypatch.setattr(dispatch_mod.time, "sleep", lambda *a: None)
    monkeypatch.setattr(
        dispatch_mod.subprocess, "run",
        lambda cmd, **kwargs: type("Result", (), {"returncode": 1, "stdout": "", "stderr": "Operation not permitted"})(),
    )

    with pytest.raises(RuntimeError, match=r"after 3 attempts\. Operation not permitted"):
        dispatch_mod._create_job_worktree("job-test", "codex")


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
    monkeypatch.setattr(dispatch_mod, "HARNESS_CAPABILITY_BASELINES", fake_baselines)

    env = _build_subprocess_env("codex", {}, requires_gh_write=False, story_id="story-1")

    assert env.get("MY_AGENT_TOKEN") == "should-be-included"


def test_build_subprocess_env_applies_headless_contract_required_vars():
    from synlynk.dispatch import _build_subprocess_env
    import synlynk.dispatch as dispatch_mod

    fake_baselines = {
        "agy": {"env_passthrough": [], "headless_contract": {"env_vars_required": ["PYTHONUNBUFFERED=1"]}},
    }
    dispatch_mod_patch_target = dispatch_mod.HARNESS_CAPABILITY_BASELINES
    dispatch_mod.HARNESS_CAPABILITY_BASELINES = fake_baselines
    try:
        env = _build_subprocess_env("agy", {}, requires_gh_write=False, story_id="story-1")
        assert env.get("PYTHONUNBUFFERED") == "1"
    finally:
        dispatch_mod.HARNESS_CAPABILITY_BASELINES = dispatch_mod_patch_target


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
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    # #569 fail-closed: tests without Apps must mock a minted token
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    job = sl.dispatch_agent(
        "grok", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True, role="qa",
    )

    assert job["agent"] == "grok"


def test_daemon_jobs_migration_adds_requires_gh_write_and_gh_write_target(project_dir):
    from synlynk import _get_db
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "requires_gh_write" in cols
    assert "gh_write_target" in cols
    conn.close()


def test_daemon_jobs_migration_adds_agent_id_column(project_dir):
    from synlynk import _get_db
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "agent_id" in cols
    conn.close()


def test_dispatch_agent_persists_requires_gh_write_and_target_on_daemon_jobs(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "run",
        lambda *a, **kw: dispatch_mod.subprocess.CompletedProcess(
            a[0], 0, stdout='{"title":"close stale issues","body":"","labels":[]}', stderr=""
        ),
    )
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")
    sl.dispatch_agent("codex", "close stale issues", force_agent=True, requires_gh_write=True, issue=701, role="qa")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT requires_gh_write, gh_write_target FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == "issue:701"


def test_dispatch_agent_extracts_pr_target_from_task_for_gh_write(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "run",
        lambda *a, **kw: dispatch_mod.subprocess.CompletedProcess(
            a[0], 0, stdout='{"title":"review PR","body":"","labels":[]}', stderr=""
        ),
    )
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_bot_login", lambda role: "qa-bot")

    sl.dispatch_agent(
        "codex", "post a review on PR #1180", force_agent=True,
        requires_gh_write=True, task_type="review", role="qa",
    )

    conn = sl._get_db()
    row = conn.execute(
        "SELECT gh_write_target, gh_write_author, gh_write_expect FROM daemon_jobs "
        "ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == "pr:1180"
    assert row[1]
    assert row[2] == "review_posted"


def test_dispatch_agent_warns_and_falls_back_without_gh_write_target(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "run",
        lambda *a, **kw: dispatch_mod.subprocess.CompletedProcess(
            a[0], 0, stdout='{"title":"sign-off note","body":"","labels":[]}', stderr=""
        ),
    )
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    sl.dispatch_agent(
        "codex", "post the requested sign-off note", force_agent=True,
        requires_gh_write=True, role="qa",
    )

    captured = capsys.readouterr()
    assert "no numbered PR/issue target" in captured.err
    conn = sl._get_db()
    row = conn.execute(
        "SELECT gh_write_target, gh_write_author FROM daemon_jobs "
        "ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] is None
    assert row[1] is None


def test_dispatch_agent_explicit_issue_takes_precedence_over_task_target(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(
        dispatch_mod.subprocess,
        "run",
        lambda *a, **kw: dispatch_mod.subprocess.CompletedProcess(
            a[0], 0, stdout='{"title":"explicit issue","body":"","labels":[]}', stderr=""
        ),
    )
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    sl.dispatch_agent(
        "codex", "post a review on PR #1180 and reference issue #1200", force_agent=True,
        requires_gh_write=True, issue=1300, gh_write_target_kind="issue", role="qa",
    )

    conn = sl._get_db()
    row = conn.execute(
        "SELECT gh_write_target FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == "issue:1300"


def test_dispatch_agent_persists_agent_id_on_daemon_jobs(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    agent_id = agent_cli.cmd_agent_init("dev")

    sl.dispatch_agent(
        "codex", "do work", agent_id=agent_id, force_agent=True, context_mode="none",
    )

    conn = sl._get_db()
    row = conn.execute(
        "SELECT agent_id FROM daemon_jobs ORDER BY enqueued_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row[0] == agent_id


def test_dispatch_agent_requires_gh_write_reroutes_incapable_agent(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    job = sl.dispatch_agent(
        "grok", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, role="qa",
    )

    assert job["agent"] == "claude"
    assert sl.HARNESS_CAPABILITY_BASELINES[job["agent"]]["can_gh_write"] is True
    captured = capsys.readouterr()
    assert "rerouted" in captured.out
    assert "#426" in captured.out


def test_dispatch_agent_requires_gh_write_force_agent_warns_and_proceeds(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    job = sl.dispatch_agent(
        "grok", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, force_agent=True, role="qa",
    )

    assert job["agent"] == "grok"
    captured = capsys.readouterr()
    assert "grok" in captured.err
    assert "#426" in captured.err


def test_dispatch_agent_requires_gh_write_allows_codex_without_reroute(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")

    job = sl.dispatch_agent(
        "codex", "review and merge PR #500", story_id="story-manual-1",
        context_mode="none", requires_gh_write=True, role="qa",
    )

    assert job["agent"] == "codex"
    captured = capsys.readouterr()
    assert "#426" not in captured.out + captured.err


def test_dispatch_agent_requires_gh_write_blocks_agy_when_tc7_fails(project_dir, monkeypatch, capsys):
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "_run_tc7",
        lambda: {"passed": False, "missing": ["command(gh pr merge)"], "error": ""},
    )
    with pytest.raises(SystemExit):
        dispatch_mod.dispatch_agent("agy", "review PR 964", force_agent=True, requires_gh_write=True, role="qa")
    out = capsys.readouterr().out
    assert "TC-7" in out or "allow-rule" in out


def test_dispatch_agent_requires_gh_write_allows_agy_when_tc7_passes(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1

    monkeypatch.setattr(
        dispatch_mod,
        "_run_tc7",
        lambda: {"passed": True, "missing": [], "error": ""},
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")
    monkeypatch.setattr(
        sl,
        "_preflight_dispatch",
        lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {
            "passed": True,
            "sentinel": None,
            "reason": None,
        },
    )
    result = dispatch_mod.dispatch_agent("agy", "review PR 964", force_agent=True, requires_gh_write=True, role="qa")
    assert result is not None


def test_dispatch_agent_requires_gh_write_raises_when_no_capable_agent(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    no_capable = {
        name: {**baseline, "can_gh_write": False}
        for name, baseline in sl.HARNESS_CAPABILITY_BASELINES.items()
    }
    monkeypatch.setattr(sl, "HARNESS_CAPABILITY_BASELINES", no_capable)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    with pytest.raises(ValueError, match="can_gh_write"):
        sl.dispatch_agent(
            "agy", "review and merge PR #500", story_id="story-manual-1",
            context_mode="none", requires_gh_write=True, role="qa",
        )


def test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted():
    from synlynk.dispatch import _grok_permission_flags

    shell_flags = _grok_permission_flags(["read:*", "run:shell"])
    test_flags = _grok_permission_flags(["read:*", "run:tests"])

    assert shell_flags == ["--always-approve"]
    assert test_flags == ["--always-approve"]
    assert "--permission-mode" not in shell_flags
    assert "dontAsk" not in shell_flags
    assert "--permission-mode" not in test_flags
    assert "dontAsk" not in test_flags


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
    """Without origin, --base main falls back to local main."""
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto", explicit_base="main"
    )

    # No remote → local main (still honors explicit base over stacking).
    assert base_ref == "main"


def test_explicit_base_main_uses_origin_tip_when_local_main_stale(
    git_worktree_repo, tmp_path, monkeypatch
):
    """#832: --base main must follow origin/main after fetch, not stale local main."""
    import subprocess
    from pathlib import Path
    import synlynk.dispatch as dispatch_mod

    repo = Path(git_worktree_repo)
    monkeypatch.chdir(repo)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=True)

    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)],
        cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=repo, capture_output=True, check=True,
    )
    old = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    (repo / "advance.txt").write_text("ahead of local main\n")
    subprocess.run(["git", "add", "advance.txt"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "advance origin tip"],
        cwd=repo, capture_output=True, check=True,
    )
    new = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "push", "origin", "main"], cwd=repo, capture_output=True, check=True,
    )
    # Leave local main behind origin/main
    subprocess.run(
        ["git", "reset", "--hard", old], cwd=repo, capture_output=True, check=True,
    )
    local_now = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert local_now == old
    assert local_now != new

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(repo), stacking_mode="auto", explicit_base="main"
    )
    assert base_ref == "origin/main"
    tip = subprocess.run(
        ["git", "rev-parse", base_ref], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert tip == new

    # Worktree created from --base main must land on the fresh tip
    wt = dispatch_mod._create_job_worktree("job-fresh-base", "codex", base="main")
    assert wt["base_branch"] == "origin/main"
    assert wt["base_sha"] == new
    head = subprocess.run(
        ["git", "-C", wt["path"], "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head == new


def test_explicit_base_origin_main_still_works(git_worktree_repo, tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path
    import synlynk.dispatch as dispatch_mod

    repo = Path(git_worktree_repo)
    monkeypatch.chdir(repo)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, capture_output=True, check=True)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)], cwd=repo, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"], cwd=repo, capture_output=True, check=True,
    )

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(repo), stacking_mode="auto", explicit_base="origin/main"
    )
    assert base_ref == "origin/main"


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


def test_dispatch_persists_context_mode_and_bytes(project_dir, monkeypatch):
    """dispatch_agent writes context_mode + context_bytes onto daemon_jobs."""
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from unittest.mock import MagicMock

    # Minimal stubs so dispatch reaches the DB write without spawning.
    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda *a, **k: {
        "path": str(project_dir / "wt"),
        "base_branch": "main",
        "base_sha": "abc12345",
    })
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda *a, **k: ("wt", "branch"))
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "# ctx\n" + ("x" * 100))
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **k: "test-model")
    monkeypatch.setattr(sl, "_warn_context_size", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_load_jobs", lambda: [])
    monkeypatch.setattr(sl, "_save_jobs", lambda jobs: None)
    monkeypatch.setattr(sl, "log_telemetry_event", lambda *a, **k: None)

    # Fake Popen
    proc = MagicMock()
    proc.pid = 424242
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: proc)

    # Avoid heavy preflight
    monkeypatch.setattr(
        dispatch_mod,
        "_preflight_dispatch",
        lambda *a, **k: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(sl, "_quota_status_for_agent", lambda *a, **k: {"status": "ok"})

    # ensure worktree dirs
    (project_dir / "wt").mkdir(exist_ok=True)

    job = dispatch_mod.dispatch_agent(
        "codex",
        "do a small thing",
        force_agent=True,
        context_mode="task",
        job_id="job-ctxmode1",
        skip_preflight=True,
    )
    assert job.get("context_mode") == "task"
    assert job.get("context_bytes", 0) > 0

    conn = sl._get_db()
    row = conn.execute(
        "SELECT context_mode, context_bytes FROM daemon_jobs WHERE job_id=?",
        ("job-ctxmode1",),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "task"
    assert int(row[1]) > 0


def test_cost_entry_inherits_context_mode_from_job(project_dir):
    import synlynk as sl
    from synlynk.db import _insert_cost_row

    conn = sl._get_db()
    # migration should add columns
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daemon_jobs)")}
    assert "context_mode" in cols
    assert "context_bytes" in cols
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, "
        "enqueued_at, context_mode, context_bytes) VALUES (?,?,?,?,?,?,?,?,?)",
        ("job-cm-cost", "claude", "t", "done", 5, "[]", "2026-08-09T00:00:00", "full", 50000),
    )
    conn.commit()
    conn.close()

    _insert_cost_row(
        session_date="2026-08-09",
        agent="claude",
        model="test",
        input_tokens=100,
        output_tokens=10,
        cache_read_tokens=0,
        cost_source="actual",
        total_cost_usd=0.01,
        job_id="job-cm-cost",
    )
    conn = sl._get_db()
    row = conn.execute(
        "SELECT context_mode FROM cost_entries WHERE job_id=?",
        ("job-cm-cost",),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "full"


def test_dispatch_agent_with_unregistered_agent_id_raises(project_dir):
    import synlynk as sl

    with pytest.raises(ValueError, match="unregistered"):
        sl.dispatch_agent(
            "codex", "do work", agent_id="nonexistent-id", force_agent=True, context_mode="none",
        )


def test_dispatch_agent_with_disabled_agent_id_raises(project_dir):
    import synlynk as sl
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    agent_store.set_agent_disabled(agent_id, actor="test")

    with pytest.raises(ValueError, match="disabled"):
        sl.dispatch_agent(
            "codex", "do work", agent_id=agent_id, force_agent=True, context_mode="none",
        )


def test_dispatch_agent_id_auto_selects_harness_by_mapped_role(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    agent_id = agent_cli.cmd_agent_init("qa")  # qa -> "verifier" -> agy

    job = sl.dispatch_agent(
        "claude", "run the test suite", agent_id=agent_id,
        force_agent=False, context_mode="none",
    )

    assert job["agent"] == "agy"


def test_harness_for_org_role_ignores_non_core_fleet_baselines(monkeypatch):
    import synlynk.dispatch as dispatch_mod

    fake_baselines = {
        "aardvark": {"roles": ["builder"], "can_gh_write": False},
        "agy": {"roles": ["builder", "verifier"], "can_gh_write": False},
    }

    result = dispatch_mod._harness_for_org_role("dev", fake_baselines)
    assert result == "agy"


def test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    captured_roles = []
    monkeypatch.setattr(
        dispatch_mod, "_resolve_dispatch_gh_token",
        lambda role: captured_roles.append(role) or "test-gh-token",
    )

    agent_id = agent_cli.cmd_agent_init("dev")

    sl.dispatch_agent(
        "grok", "review and merge PR #500", agent_id=agent_id, story_id="story-with-different-role",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert captured_roles == ["dev"]


def test_dispatch_agent_story_id_wins_over_agent_id_role_for_harness_selection(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli, agent_store

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda harness_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(
        agent_store, "_workspace_root",
        lambda workspace_id: str(project_dir / ".synlynk" / "workspaces" / workspace_id),
    )

    agent_id = agent_cli.cmd_agent_init("dev")
    monkeypatch.setattr(sl, "_best_agent_for_story", lambda story_id: "grok")

    job = sl.dispatch_agent(
        "claude", "implement the feature", agent_id=agent_id,
        story_id="story-with-capability-match", force_agent=False,
        context_mode="none",
    )

    assert job["agent"] == "grok"
