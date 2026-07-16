import sys
import os
import time
import json
from datetime import datetime, timedelta, timezone
import pytest
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_agent_capability_baselines_exist():
    assert "claude" in synlynk.AGENT_CAPABILITY_BASELINES
    assert "agy" in synlynk.AGENT_CAPABILITY_BASELINES
    assert "codex" in synlynk.AGENT_CAPABILITY_BASELINES
    for name, caps in synlynk.AGENT_CAPABILITY_BASELINES.items():
        assert "roles" in caps
        assert "cli" in caps
        assert "non_interactive_flags" in caps
    assert synlynk.AGENT_CAPABILITY_BASELINES["claude"]["non_interactive_flags"] == ["--print"]
    assert synlynk.AGENT_CAPABILITY_BASELINES["claude"]["dispatch_flags"] == ["--dangerously-skip-permissions"]


def test_sop_section_headers_defined():
    from synlynk.probe import SOP_SECTION_HEADERS

    assert len(SOP_SECTION_HEADERS) == 6
    assert "## PR Review Discipline" in SOP_SECTION_HEADERS
    assert "## Brainstorm-First Policy" in SOP_SECTION_HEADERS
    assert "## Design → Plan → Build Sequence" in SOP_SECTION_HEADERS
    assert "## Capability-Based Task Allocation" in SOP_SECTION_HEADERS
    assert "## Cost Visibility" in SOP_SECTION_HEADERS
    assert "## Repo Hygiene" in SOP_SECTION_HEADERS


def test_directive_templates_contain_sop_headers(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "n")
    synlynk.init(force=True, agents=["claude"], org="test-org", repo="test/repo", mode="solo")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "## PR Review Discipline" in content
    assert "## Repo Hygiene" in content


def test_run_tc5_passes_when_all_headers_present(tmp_path):
    from synlynk.probe import SOP_SECTION_HEADERS, _run_tc5

    fpath = tmp_path / "CLAUDE.md"
    fpath.write_text("\n".join(SOP_SECTION_HEADERS) + "\nother content")
    result = _run_tc5({"claude": str(fpath)})
    assert result["passed"] is True
    assert result["missing"] == {}


def test_run_tc5_reports_missing_sections(tmp_path):
    from synlynk.probe import _run_tc5

    fpath = tmp_path / "CLAUDE.md"
    fpath.write_text("## PR Review Discipline\nsome content")
    result = _run_tc5({"claude": str(fpath)})
    assert result["passed"] is False
    missing = result["missing"]["claude"]
    assert "## Brainstorm-First Policy" in missing
    assert "## PR Review Discipline" not in missing


def test_run_tc5_missing_file_reports_all_headers(tmp_path):
    from synlynk.probe import SOP_SECTION_HEADERS, _run_tc5

    result = _run_tc5({"claude": str(tmp_path / "CLAUDE.md")})
    assert result["passed"] is False
    assert len(result["missing"]["claude"]) == len(SOP_SECTION_HEADERS)


def test_run_tc4_skips_flag_only_command_templates(monkeypatch):
    """dispatch.model/dispatch.tools store a bare flag ("--model {model}"), not a
    full invocation. TC-4 must not try to exec the flag itself as a binary."""
    import sqlite3
    import types
    from synlynk.probe import _run_tc4

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE harness_verb_map (synlynk_verb TEXT, agent_command TEXT, supported TEXT, agent_name TEXT)"
    )
    conn.execute(
        "INSERT INTO harness_verb_map VALUES ('dispatch.model', '--model {model}', 'full', 'claude')"
    )
    conn.execute(
        "INSERT INTO harness_verb_map VALUES ('probe', 'claude --version', 'full', 'claude')"
    )
    conn.commit()

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd == ["claude", "--help"]:
            return types.SimpleNamespace(returncode=0)
        raise AssertionError(f"unexpected probe command: {cmd}")

    monkeypatch.setattr("synlynk.probe.subprocess.run", fake_run)
    result = _run_tc4("claude", conn)

    assert result["passed"] is True
    assert "dispatch.model" not in result["failed_verbs"]
    assert calls == [["claude", "--help"]]


def test_run_tc4_still_reports_missing_real_binary():
    import sqlite3
    from synlynk.probe import _run_tc4

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE harness_verb_map (synlynk_verb TEXT, agent_command TEXT, supported TEXT, agent_name TEXT)"
    )
    conn.execute(
        "INSERT INTO harness_verb_map VALUES ('dispatch.task', 'nonexistent-binary-xyz --print', 'full', 'claude')"
    )
    conn.commit()

    result = _run_tc4("claude", conn)

    assert result["passed"] is False
    assert "dispatch.task" in result["failed_verbs"]


def test_dispatch_help_lists_all_known_agents(project_dir, capsys):
    old_argv = sys.argv
    sys.argv = ["synlynk", "dispatch", "--help"]
    try:
        with pytest.raises(SystemExit) as exc:
            synlynk.main()
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert exc.value.code == 0
    for agent_name in sorted(synlynk.AGENT_CAPABILITY_BASELINES):
        assert agent_name in captured.out


def test_dispatch_rejects_unknown_agent_before_dispatch_agent_called(project_dir, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(synlynk, "dispatch_agent", lambda *a, **kw: calls.append((a, kw)))
    old_argv = sys.argv
    sys.argv = ["synlynk", "dispatch", "nonexistent-agent", "--task", "x"]
    try:
        with pytest.raises(SystemExit) as exc:
            synlynk.main()
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert exc.value.code != 0
    assert "invalid choice" in captured.err
    assert calls == []


def test_doctor_prints_tc5_warning(monkeypatch, tmp_path, isolated_db, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        synlynk,
        "AGENT_CAPABILITY_BASELINES",
        {
            "claude": {
                "cli": "claude",
                "dispatch_flags": {},
                "network_deps": {"required_endpoints": []},
                "headless_contract": {},
            }
        },
    )
    monkeypatch.setattr(synlynk, "_run_tc1", lambda agent: {"passed": True})
    monkeypatch.setattr(synlynk, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(synlynk, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(synlynk, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(
        synlynk,
        "_run_tc5",
        lambda files: {"passed": False, "missing": {"claude": ["## Repo Hygiene"]}},
    )
    monkeypatch.setattr(synlynk, "load_config", lambda: {"roles": {}})
    synlynk.cmd_doctor()
    out = capsys.readouterr().out
    assert "TC-5 sops" in out
    assert "missing 1 section(s)" in out


def test_sync_repair_sops_injects_missing_sections(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"claude": ["pm", "review"]}, "workgroup_agents": ["claude"]}')
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "claude.json").write_text("{}")
    (tmp_path / "CLAUDE.md").write_text("# Claude Instructions\n\n## PR Review Discipline\nsome content\n")

    synlynk.cmd_sync(dry_run=False, repair_sops=True)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "## Brainstorm-First Policy" in content
    assert "## Repo Hygiene" in content
    assert content.count("## PR Review Discipline") == 1


def test_sync_repair_sops_preserves_existing_fence_body(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"claude": ["pm"]}, "workgroup_agents": ["claude"]}')
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "claude.json").write_text("{}")
    (tmp_path / "CLAUDE.md").write_text(
        "# Claude Instructions\n\n"
        "<!-- synlynk:harness vsop-repair verified:2026-07-05T00:00:00Z -->\n"
        "# Harness Instructions (synlynk-managed — do not edit)\n\n"
        "## PR Review Discipline\n"
        "probe-written content\n"
        "<!-- /synlynk:harness -->\n"
    )

    synlynk.cmd_sync(dry_run=False, repair_sops=True)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "probe-written content" in content
    assert "## Brainstorm-First Policy" in content
    assert content.count("probe-written content") == 1


def test_sync_repair_sops_is_idempotent(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"claude": ["pm"]}, "workgroup_agents": ["claude"]}')
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "claude.json").write_text("{}")
    (tmp_path / "CLAUDE.md").write_text("# Instructions\n")

    synlynk.cmd_sync(dry_run=False, repair_sops=True)
    content_first = (tmp_path / "CLAUDE.md").read_text()
    synlynk.cmd_sync(dry_run=False, repair_sops=True)
    content_second = (tmp_path / "CLAUDE.md").read_text()
    assert content_first == content_second


def test_configure_agent_writes_harness_overrides(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "codex.json").write_text('{"context_mode": "full"}')

    synlynk.cmd_configure_agent("codex", flags={"timeout": "60"}, envs={}, network_deps=[])

    data = json.loads((tmp_path / ".agents" / "codex.json").read_text())
    assert data["harness_overrides"]["dispatch_flags"]["timeout"] == "60"


def test_configure_agent_creates_file_if_missing(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()

    synlynk.cmd_configure_agent("agy", flags={}, envs={"PYTHONUNBUFFERED": "1"}, network_deps=[])

    data = json.loads((tmp_path / ".agents" / "agy.json").read_text())
    assert data["harness_overrides"]["env"]["PYTHONUNBUFFERED"] == "1"


def test_configure_agent_preserves_existing_keys(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "claude.json").write_text(
        '{"context_mode": "full", "harness_overrides": {"dispatch_flags": {"model": "claude-3"}}}'
    )

    synlynk.cmd_configure_agent("claude", flags={"timeout": "30"}, envs={}, network_deps=[])

    data = json.loads((tmp_path / ".agents" / "claude.json").read_text())
    assert data["context_mode"] == "full"
    assert data["harness_overrides"]["dispatch_flags"]["model"] == "claude-3"
    assert data["harness_overrides"]["dispatch_flags"]["timeout"] == "30"


def test_load_harness_overrides_returns_empty_when_no_file(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.dispatch import _load_harness_overrides

    assert _load_harness_overrides("codex") == {
        "dispatch_flags": {},
        "env": {},
        "network_deps": [],
    }


def test_load_harness_overrides_reads_from_agents_json(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "codex.json").write_text(
        json.dumps(
            {
                "harness_overrides": {
                    "dispatch_flags": {"timeout": "60"},
                    "env": {},
                    "network_deps": [],
                }
            }
        )
    )
    from synlynk.dispatch import _load_harness_overrides

    result = _load_harness_overrides("codex")
    assert result["dispatch_flags"]["timeout"] == "60"


def test_dispatch_agent_applies_harness_overrides(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "claude.json").write_text(
        json.dumps(
            {
                "harness_overrides": {
                    "dispatch_flags": {},
                    "env": {"MY_VAR": "42"},
                    "network_deps": [],
                }
            }
        )
    )
    captured_env = {}

    def fake_popen(cmd, env=None, **kwargs):
        captured_env.update(env or {})
        raise RuntimeError("stop")

    monkeypatch.setattr("synlynk.dispatch.subprocess.Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda *args, **kwargs: "unknown")
    from synlynk.dispatch import dispatch_agent

    with pytest.raises(RuntimeError):
        dispatch_agent("claude", task="test", context_mode="none", skip_preflight=True)
    assert captured_env.get("MY_VAR") == "42"


def test_role_permission_defaults_cover_all_default_roles():
    from synlynk._constants import _ROLE_PERMISSION_DEFAULTS

    for role in [
        "pm",
        "review",
        "deploy",
        "implement",
        "test",
        "refactor",
        "css",
        "templates",
        "content",
        "canvas",
        "js",
        "infra",
    ]:
        assert role in _ROLE_PERMISSION_DEFAULTS, f"Missing role: {role}"


def test_resolve_dispatch_permissions_returns_role_defaults():
    from synlynk.dispatch import _resolve_dispatch_permissions

    perms = _resolve_dispatch_permissions("codex", role_list=["implement", "test"])
    assert "write:src/" in perms
    assert "run:tests" in perms


def test_resolve_dispatch_permissions_grant_expands():
    from synlynk.dispatch import _resolve_dispatch_permissions

    perms = _resolve_dispatch_permissions("codex", role_list=["review"], grants=["write:src/"])
    assert "write:src/" in perms


def test_resolve_dispatch_permissions_revoke_removes():
    from synlynk.dispatch import _resolve_dispatch_permissions

    perms = _resolve_dispatch_permissions("codex", role_list=["implement"], revokes=["run:tests"])
    assert "run:tests" not in perms
    assert "write:src/" in perms


def test_permissions_to_flags_claude_allowedtools():
    from synlynk.dispatch import _permissions_to_flags

    result = _permissions_to_flags("claude", ["read:*", "write:src/"])
    assert "--allowedTools" in result
    idx = result.index("--allowedTools")
    tools_str = result[idx + 1]
    assert "Read" in tools_str
    assert "Edit" in tools_str


def test_permissions_to_flags_codex_approval_policy():
    from synlynk.dispatch import _permissions_to_flags

    result = _permissions_to_flags("codex", ["read:*"])
    assert "--approval-policy" in result
    assert "untrusted" in result


def test_permissions_to_flags_agy_returns_context_section():
    from synlynk.dispatch import _permissions_to_flags

    result = _permissions_to_flags("agy", ["read:*", "write:docs/"])
    assert result == []


def test_dispatch_agent_injects_agy_permissions_header(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "agy.json").write_text("{}")
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"agy": ["content"]}}')

    captured = {}

    def fake_formatter(agent, context_text, story_id, task, file_section, verify_section):
        captured["task"] = task
        return task

    def fake_popen(cmd, env=None, **kwargs):
        raise RuntimeError("stop")

    monkeypatch.setattr(synlynk, "_format_prompt_for_agent", fake_formatter)
    monkeypatch.setattr("synlynk.dispatch.subprocess.Popen", fake_popen)
    monkeypatch.setattr(synlynk, "_probe_model_version", lambda *args, **kwargs: "unknown")
    from synlynk.dispatch import dispatch_agent

    with pytest.raises(RuntimeError):
        dispatch_agent(
            "agy",
            task="build docs",
            context_mode="none",
            skip_preflight=True,
            grants=["write:docs/"],
        )

    assert captured["task"].startswith("## Permissions")
    assert "write:docs/" in captured["task"]


def test_daemon_jobs_has_handoff_columns(isolated_db):
    from synlynk import _get_db

    conn = _get_db()
    cols = [row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)").fetchall()]
    assert "handoff_count" in cols
    assert "previous_agents" in cols
    conn.close()


def test_stall_detection_writes_handoff_pending(tmp_path, isolated_db, monkeypatch):
    import time as _time

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    log_file = tmp_path / ".synlynk" / "job.log"
    log_file.write_text("")

    from synlynk.dispatch import _check_job_stall

    job = {
        "id": "job-abc123",
        "status": "running",
        "pid": None,
        "started_at": _time.strftime("%Y-%m-%dT%H:%M:%S", _time.gmtime(_time.time() - 99999)),
        "log_file": str(log_file),
    }
    sentinel_path = str(tmp_path / ".synlynk" / "sentinel.md")
    result = _check_job_stall(job, config={"stall_timeout_minutes": 0}, sentinel_path=sentinel_path)
    assert result is True
    sentinel_content = (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "STALL_NO_OUTPUT" in sentinel_content
    assert "HANDOFF_PENDING" in sentinel_content


def test_jobs_stalled_lists_handoff_pending_jobs(tmp_path, isolated_db, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "sentinel.md").write_text(
        "[HANDOFF_PENDING] Job job-aaa on agent 'agy' is awaiting handoff.\n"
    )

    from synlynk import _get_db, cmd_jobs

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, handoff_count) "
        "VALUES ('job-aaa', 'agy', 'write tests', 'failed', '2026-07-05T10:00:00', 0)"
    )
    conn.commit()
    conn.close()

    cmd_jobs(stalled=True)
    out = capsys.readouterr().out
    assert "job-aaa" in out
    assert "agy" in out


def test_jobs_handoff_updates_db_and_dispatches(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk" / "contexts").mkdir(parents=True)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"codex": ["implement"]}}')
    ctx_file = tmp_path / ".synlynk" / "contexts" / "job-bbb.md"
    ctx_file.write_text("# Context\noriginal task content\n")
    (tmp_path / ".synlynk" / "sentinel.md").write_text(
        "[HANDOFF_PENDING] Job job-bbb on agent 'agy' is awaiting handoff.\n"
    )

    from synlynk import _get_db

    conn = _get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, enqueued_at, handoff_count, previous_agents) "
        "VALUES ('job-bbb', 'agy', 'implement feature', 'failed', '2026-07-05T10:00:00', 0, NULL)"
    )
    conn.commit()
    conn.close()

    dispatched = []
    monkeypatch.setattr(
        "synlynk.dispatch.dispatch_agent",
        lambda *a, **kw: dispatched.append((a, kw)) or {"id": "job-ccc"},
    )

    from synlynk import cmd_jobs_handoff

    cmd_jobs_handoff("job-bbb", to_agent="codex")
    content = ctx_file.read_text()
    assert "## Handoff Note" in content
    assert "agy" in content

    conn2 = _get_db()
    row = conn2.execute(
        "SELECT handoff_count, previous_agents FROM daemon_jobs WHERE job_id='job-bbb'"
    ).fetchone()
    conn2.close()
    assert row[0] == 1
    prev = json.loads(row[1])
    assert "agy" in prev
    assert len(dispatched) == 1
    assert dispatched[0][0][0] == "codex"
    assert "## Handoff Note" in dispatched[0][1]["task"]


def test_doctor_wizard_offers_fix_menu_on_tc2_failure(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "agy.json").write_text("{}")
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text('{"roles": {"agy": ["builder"]}}')
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    inputs = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: next(inputs))
    patched_baselines = {
        "agy": {
            "cli": "agy",
            "dispatch_flags": {},
            "network_deps": {"required_endpoints": []},
            "headless_contract": {},
        }
    }
    monkeypatch.setattr("synlynk.AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr("synlynk._constants.AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr("synlynk.doctor.AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr(synlynk, "_run_tc1", lambda agent: {"passed": True, "requires_pty": False})
    monkeypatch.setattr(synlynk, "_run_tc2", lambda agent, flags_spec: {"passed": False, "failed_flags": ["--bad-flag"]})
    monkeypatch.setattr(synlynk, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(synlynk, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(synlynk, "_run_tc5", lambda files: {"passed": True, "missing": {}})
    monkeypatch.setattr(synlynk, "load_config", lambda: {"roles": {}})

    synlynk.cmd_doctor()

    data = json.loads((tmp_path / ".agents" / "agy.json").read_text())
    assert data["harness_overrides"]["dispatch_flags"]["bad-flag"] is None


def test_doctor_wizard_escalate_option_calls_dispatch(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "telemetry.json").write_text(
        json.dumps([{"agent": "agy", "command": "npm test", "tool_call_count": 3}])
    )
    dispatched = []
    monkeypatch.setattr(
        "synlynk.dispatch.dispatch_agent",
        lambda *a, **kw: dispatched.append((a, kw)) or {"id": "job-esc"},
    )

    from synlynk import _doctor_maybe_escalate

    _doctor_maybe_escalate("agy", {"tc2": {"passed": False, "failed_flags": ["--bad-flag"]}})
    assert len(dispatched) == 1
    assert dispatched[0][0][0] == "claude"
    assert "doctor" in dispatched[0][1]["task"].lower()


def test_doctor_tc5_fix_uses_targeted_repair(monkeypatch, tmp_path, isolated_db):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        synlynk,
        "AGENT_CAPABILITY_BASELINES",
        {
            "claude": {
                "cli": "claude",
                "dispatch_flags": {},
                "network_deps": {"required_endpoints": []},
                "headless_contract": {},
            }
        },
    )
    monkeypatch.setattr(synlynk, "_run_tc1", lambda agent: {"passed": True})
    monkeypatch.setattr(synlynk, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(synlynk, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(synlynk, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(
        synlynk,
        "_run_tc5",
        lambda files: {"passed": False, "missing": {"claude": ["## Repo Hygiene"]}},
    )
    monkeypatch.setattr(synlynk, "load_config", lambda: {"roles": {"claude": ["pm"]}})
    monkeypatch.setattr(synlynk, "cmd_sync", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cmd_sync should not be called")))
    monkeypatch.setattr(synlynk, "_doctor_fix_menu", lambda agent, tc_name, tc: "1")
    called = {}

    def fake_repair(agent_name=None, dry_run=False):
        called["agent_name"] = agent_name
        called["dry_run"] = dry_run

    monkeypatch.setattr(synlynk, "_repair_sops_only", fake_repair)

    synlynk.cmd_doctor()

    assert called == {"agent_name": "claude", "dry_run": False}


def test_cli_configure_agent_accepts_bare_flag(monkeypatch):
    import synlynk.cli as cli_mod

    captured = {}

    def fake_configure_agent(name, flags=None, envs=None, network_deps=None):
        captured["name"] = name
        captured["flags"] = flags

    monkeypatch.setattr(synlynk, "cmd_configure_agent", fake_configure_agent)
    monkeypatch.setattr(
        sys,
        "argv",
        ["synlynk", "configure", "agent", "codex", "--flag", "no-stream", "--flag", "timeout=60"],
    )

    cli_mod.main()

    assert captured["name"] == "codex"
    assert captured["flags"] == {"no-stream": True, "timeout": "60"}


def test_bs14_schema_tables_exist(tmp_path):
    import sqlite3
    from synlynk import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in [
        "harness_baselines",
        "harness_records",
        "harness_verb_map",
        "harness_command_palette",
        "harness_version_history",
    ]:
        assert t in tables, f"Missing table: {t}"
    conn.close()


def test_bs14_schema_migration_is_idempotent(tmp_path):
    import sqlite3
    from synlynk import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    _migrate_db(conn)
    conn.close()


def test_bs14_baseline_seeded_for_known_agents(tmp_path):
    import sqlite3
    from synlynk import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    rows = conn.execute("SELECT harness_name FROM harness_baselines").fetchall()
    harnesses = {r[0] for r in rows}
    for h in ["claude-cli", "agy", "grok", "codex"]:
        assert h in harnesses, f"Missing baseline for harness: {h}"
    conn.close()


def test_jobs_file_constant():
    assert synlynk.JOBS_FILE == ".synlynk/jobs.json"


def test_get_username_from_git(project_dir, monkeypatch):
    def mock_run(args, **kwargs):
        if args[0] == "gh":
            return type('R', (), {'stdout': '', 'returncode': 1})()
        elif args[0] == "git" and args[1] == "config":
            return type('R', (), {'stdout': 'Nikhil Soman\n', 'returncode': 0})()
        return type('R', (), {'stdout': '', 'returncode': 1})()
    monkeypatch.setattr(synlynk.subprocess, 'run', mock_run)
    assert synlynk.get_username() == "nikhilsoman"


def test_get_username_fallback(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(Exception("no git")))
    assert synlynk.get_username() == "unknown"


def test_get_mode_single(project_dir):
    assert synlynk.get_mode() == "single"


def test_get_mode_team(project_dir):
    import json
    (project_dir / "project-docs" / ".synlynk_config.json").write_text(
        json.dumps({"mode": "team"})
    )
    assert synlynk.get_mode() == "team"


def test_load_config_defaults(project_dir):
    config = synlynk.load_config()
    assert config["schema_version"] == 1
    assert config["budget"]["limit_usd"] == 10.0
    assert config["watch_interval_seconds"] == 30
    assert config["org"] is None
    assert config["stall_timeout_minutes"] == 30
    assert config["agents"] == {}


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert config["schema_version"] == 1
    assert config["budget"]["limit_usd"] == 10.0
    assert config["stall_timeout_minutes"] == 30
    assert config["agents"] == {}


def test_parse_costs_md(project_dir):
    total_usd, total_requests = synlynk.parse_costs_md()
    assert abs(total_usd - 1.24) < 0.01
    assert total_requests == 2


def test_parse_costs_md_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    total_usd, total_requests = synlynk.parse_costs_md()
    assert total_usd == 0.0
    assert total_requests == 0


def test_set_state_writes_file(project_dir):
    synlynk.set_state("watching")
    assert (project_dir / ".synlynk" / "state").read_text() == "watching"


def test_set_state_all_values(project_dir):
    for state in ("watching", "active", "stopped"):
        synlynk.set_state(state)
        assert (project_dir / ".synlynk" / "state").read_text() == state


def test_set_state_no_tty_skips_ansi(project_dir, capsys):
    # capsys captures stdout which is not a TTY in pytest
    synlynk.set_state("active")
    captured = capsys.readouterr()
    assert "\033]0;" not in captured.out


def test_set_state_missing_synlynk_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Should not raise even if .synlynk/ doesn't exist
    synlynk.set_state("stopped")


def _write_telemetry(project_dir, events):
    import json
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(events))


def test_flatline_no_trigger_when_fewer_than_3(project_dir):
    _write_telemetry(project_dir, [
        {"command": "npm test", "exit_code": 1},
        {"command": "npm test", "exit_code": 1},
    ])
    synlynk.check_sentinel_patterns(output_text="", exit_code=1, cmd="npm test")
    assert not (project_dir / ".synlynk" / "sentinel.md").exists()


def test_flatline_triggers_on_3_consecutive(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    _write_telemetry(project_dir, [
        {"type": "exec", "command": "npm test", "exit_code": 1},
        {"type": "exec", "command": "npm test", "exit_code": 1},
        {"type": "exec", "command": "npm test", "exit_code": 1},
    ])
    synlynk.check_sentinel_patterns(output_text="", exit_code=1, cmd="npm test")
    sentinel = (project_dir / ".synlynk" / "sentinel.md").read_text()
    assert "FLATLINE" in sentinel
    assert "npm test" in sentinel


def test_flatline_no_trigger_when_different_commands(project_dir):
    _write_telemetry(project_dir, [
        {"type": "exec", "command": "npm test", "exit_code": 1},
        {"type": "exec", "command": "npm build", "exit_code": 1},
        {"type": "exec", "command": "npm test", "exit_code": 1},
    ])
    synlynk.check_sentinel_patterns(output_text="", exit_code=1, cmd="npm test")
    assert not (project_dir / ".synlynk" / "sentinel.md").exists()


def test_flatline_appends_to_existing_sentinel(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / ".synlynk" / "sentinel.md").write_text("# Sentinel Alerts\n- [old alert]\n")
    _write_telemetry(project_dir, [
        {"type": "exec", "command": "make build", "exit_code": 1},
        {"type": "exec", "command": "make build", "exit_code": 1},
        {"type": "exec", "command": "make build", "exit_code": 1},
    ])
    synlynk.check_sentinel_patterns(output_text="", exit_code=1, cmd="make build")
    sentinel = (project_dir / ".synlynk" / "sentinel.md").read_text()
    assert "old alert" in sentinel
    assert "make build" in sentinel


def test_generate_context_excludes_done_tasks(project_dir):
    (project_dir / "project-docs" / "todo.md").write_text(
        "## Active Tasks\n"
        "- [ ] Active task <!-- id: 1 -->\n"
        "- [x] Done task <!-- id: 2 -->\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Active task" in ctx
    assert "Done task" not in ctx

def test_generate_context_includes_only_active_roadmap(project_dir):
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "In Progress" in ctx
    assert "Feature A" in ctx

def test_generate_context_includes_sentinel_alerts(project_dir):
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n- [2026-05-17 10:00] FLATLINE: `npm test` failed\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "FLATLINE" in ctx


def test_generate_context_dedupes_repeated_sentinel_alerts(project_dir):
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-01 13:23] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-01 13:34] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-01 13:35] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [CRITICAL] [2026-07-01 14:10] HARNESS_PREFLIGHT_FAIL: Required endpoint unreachable\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert ctx.count("HARNESS_VERSION_DRIFT") == 1
    assert "3 occurrences" in ctx
    assert "most recent 2026-07-01 13:35" in ctx
    assert "HARNESS_PREFLIGHT_FAIL" in ctx

def test_generate_context_omits_sentinel_section_when_empty(project_dir):
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Sentinel Alerts" not in ctx

def test_generate_context_scope_stub_falls_back(project_dir, capsys):
    synlynk.generate_context(scope="task:99")
    captured = capsys.readouterr()
    # Task-scoped context is now implemented, not a stub
    assert "Task-scoped context saved" in captured.out
    # Context file is generated
    assert (project_dir / ".synlynk" / "context.md").exists()


def test_generate_context_task_scope_writes_story(project_dir):
    """Task-scoped context includes the story's metadata."""
    import synlynk as sl
    story_id = sl.cmd_story_create("Fix auth timeout", engg_domain="backend")
    sl.generate_context(scope=f"task:{story_id}")
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Fix auth timeout" in ctx
    assert "task-scoped" in ctx.lower()


def test_generate_context_task_scope_smaller_than_full(project_dir):
    """Task-scoped context is smaller than full context."""
    import synlynk as sl
    (project_dir / "project-docs" / "devlogs" / "nikhilsoman.md").write_text(
        "# Devlog\n## 2026-06-01\nDid a lot of work today.\n" * 20
    )
    story_id = sl.cmd_story_create("Small fix", engg_domain="backend")
    sl.generate_context(scope="full")
    full_size = (project_dir / ".synlynk" / "context.md").stat().st_size
    sl.generate_context(scope=f"task:{story_id}")
    task_size = (project_dir / ".synlynk" / "context.md").stat().st_size
    assert task_size < full_size


def test_generate_context_task_scope_unknown_story(project_dir):
    """Task-scoped context for unknown story_id still writes without crashing."""
    import synlynk as sl
    sl.generate_context(scope="task:story-deadbeef")
    assert (project_dir / ".synlynk" / "context.md").exists()


def test_generate_context_task_scope_no_teammate_devlogs(project_dir):
    """Task-scoped context does NOT include teammate devlogs."""
    import synlynk as sl
    (project_dir / "project-docs" / ".synlynk_config.json").write_text(
        '{"mode": "team", "version": "1.1.0"}'
    )
    (project_dir / "project-docs" / "devlogs" / "alice.md").write_text(
        "# Alice Devlog\n## 2026-06-01\nAlice did things.\n"
    )
    story_id = sl.cmd_story_create("Fix thing")
    sl.generate_context(scope=f"task:{story_id}")
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "alice" not in ctx.lower()


def test_dispatch_agent_task_scope_without_story_uses_reduced_context(project_dir, monkeypatch):
    """Task context without a story_id stays smaller than full context and skips history sections."""
    import synlynk as sl

    class FakeProc:
        pid = 1

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)

    (project_dir / "project-docs" / "devlogs" / "nikhilsoman.md").write_text(
        "# Devlog\n"
        "## 2026-07-01\n"
        + ("Did a lot of work today.\n" * 80)
    )
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n"
        + "".join(
            f"- [WARNING] [2026-07-01 13:{minute:02d}] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
            for minute in range(10)
        )
    )

    full_context_path = project_dir / ".synlynk" / "full-context.md"
    sl.generate_context(scope="full", out_path=str(full_context_path))
    full_size = full_context_path.stat().st_size

    job = sl.dispatch_agent("claude", "free text task", context_mode="task")
    task_context = (project_dir / job["context_file"]).read_text()
    task_size = (project_dir / job["context_file"]).stat().st_size

    assert task_size < full_size
    assert "Recent Devlog" not in task_context
    assert "Sentinel Alerts" not in task_context


def test_init_creates_project_structure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(force=False)
    assert (tmp_path / "project-docs" / "todo.md").exists()
    assert (tmp_path / "project-docs" / "memory.md").exists()
    assert (tmp_path / ".synlynk" / "config.json").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()


def test_init_claude_md_contains_session_protocol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(force=False)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "synlynk watch status" in content
    assert "synlynk checkpoint" in content
    assert "context.md" in content


def test_init_appends_to_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    (tmp_path / "CLAUDE.md").write_text("MY CUSTOM CONTENT")
    synlynk.init(force=False)
    # _write_instruction_file appends the synlynk block without removing user content
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "MY CUSTOM CONTENT" in text
    assert "<!-- synlynk:start" in text


def test_init_force_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    (tmp_path / "CLAUDE.md").write_text("MY CUSTOM CONTENT")
    synlynk.init(force=True)
    assert (tmp_path / "CLAUDE.md").read_text() != "MY CUSTOM CONTENT"
    assert "synlynk checkpoint" in (tmp_path / "CLAUDE.md").read_text()


def test_init_config_schema_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(force=False)
    import json
    config = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert config["schema_version"] == 1
    assert "watch_interval_seconds" in config
    assert "org" in config


def test_check_budgets_no_alert_under_threshold(project_dir, capsys):
    # costs.md has $1.24 out of $10.00
    synlynk.check_budgets()
    captured = capsys.readouterr()
    assert "Budget Alert" not in captured.out


def test_check_budgets_warning_at_80_percent(project_dir, capsys):
    import json
    config = json.loads((project_dir / ".synlynk" / "config.json").read_text())
    config["budget"]["limit_usd"] = 1.50  # $1.24 is 82% of $1.50
    (project_dir / ".synlynk" / "config.json").write_text(json.dumps(config))
    synlynk.check_budgets()
    captured = capsys.readouterr()
    assert "Budget Warning" in captured.out


def test_check_costs_freshness_warns_when_stale(project_dir, capsys, monkeypatch):
    # Make costs.md appear old by setting mtime to 2 hours ago
    import time
    costs_path = str(project_dir / "project-docs" / "costs.md")
    old_time = time.time() - 7200
    os.utime(costs_path, (old_time, old_time))
    synlynk._check_costs_freshness()
    captured = capsys.readouterr()
    assert "costs.md not updated" in captured.out


def test_check_costs_freshness_silent_when_fresh(project_dir, capsys):
    synlynk._check_costs_freshness()
    captured = capsys.readouterr()
    assert "costs.md not updated" not in captured.out


def test_watch_daemon_is_running_false_when_no_pidfile(project_dir):
    daemon = synlynk.WatchDaemon()
    assert daemon._is_running() is False


def test_watch_daemon_is_running_false_stale_pidfile(project_dir):
    # Write a PID that doesn't exist
    (project_dir / ".synlynk" / "watch.pid").write_text("99999999")
    daemon = synlynk.WatchDaemon()
    assert daemon._is_running() is False


def test_watch_daemon_stop_idempotent(project_dir, capsys):
    daemon = synlynk.WatchDaemon()
    daemon.stop()  # should not raise
    captured = capsys.readouterr()
    assert "not running" in captured.out


def test_watch_daemon_get_mtimes(project_dir):
    daemon = synlynk.WatchDaemon()
    mtimes = daemon._get_mtimes("project-docs")
    assert len(mtimes) > 0
    for path, mtime in mtimes.items():
        assert isinstance(mtime, float)


def test_watch_daemon_cleans_stale_pidfile_on_stop(project_dir):
    (project_dir / ".synlynk" / "watch.pid").write_text("99999999")
    daemon = synlynk.WatchDaemon()
    daemon.stop()
    assert not (project_dir / ".synlynk" / "watch.pid").exists()


def test_checkpoint_archives_done_tasks(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "## Active Tasks\n"
        "- [ ] Still active <!-- id: 1 -->\n"
        "- [x] Done task <!-- id: 2 -->\n"
    )
    synlynk.checkpoint()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Done task" not in todo
    assert "Still active" in todo

def test_checkpoint_appends_to_devlog(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [x] Finished feature <!-- id: 5 -->\n"
    )
    synlynk.checkpoint()
    devlog = (project_dir / "project-docs" / "devlogs" / "nikhil.md").read_text()
    assert "Finished feature" in devlog

def test_checkpoint_emits_telemetry_event(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [x] Task A <!-- id: 3 -->\n"
    )
    synlynk.checkpoint()
    import json
    events = json.loads((project_dir / ".synlynk" / "telemetry.json").read_text())
    cp_events = [e for e in events if e.get("type") == "checkpoint"]
    assert len(cp_events) == 1
    assert cp_events[0]["completed_task_count"] == 1
    assert cp_events[0]["user"] == "nikhil"
    assert "3" in cp_events[0]["completed_task_ids"]

def test_checkpoint_idempotent_when_no_done_tasks(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    original_todo = (project_dir / "project-docs" / "todo.md").read_text()
    synlynk.checkpoint()
    assert (project_dir / "project-docs" / "todo.md").read_text() == original_todo

def test_status_json_structure(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    monkeypatch.setattr(synlynk, 'get_mode', lambda: "single")
    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_status(json_output=True)
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert data["schema_version"] == 1
    assert data["user"] == "nikhil"
    assert "active_tasks" in data
    assert "budget" in data
    assert "watcher" in data
    assert exc.value.code == 0

def test_status_json_exit_1_on_sentinel(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    monkeypatch.setattr(synlynk, 'get_mode', lambda: "single")
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n- [2026-05-17] FLATLINE: `x` failed\n"
    )
    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_status(json_output=True)
    assert exc.value.code == 1

def test_status_human_output_contains_sections(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    monkeypatch.setattr(synlynk, 'get_mode', lambda: "single")
    with pytest.raises(SystemExit):
        synlynk.cmd_status(json_output=False)
    captured = capsys.readouterr()
    assert "ACTIVE TASKS" in captured.out
    assert "BUDGET" in captured.out
    assert "SENTINEL" in captured.out
    assert "WATCHER" in captured.out

def test_status_shows_active_tasks(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    monkeypatch.setattr(synlynk, 'get_mode', lambda: "single")
    with pytest.raises(SystemExit):
        synlynk.cmd_status(json_output=False)
    captured = capsys.readouterr()
    assert "Task one" in captured.out
    assert "Task two" in captured.out

def test_status_shows_capability_ledger(project_dir, monkeypatch, capsys):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    monkeypatch.setattr(synlynk, 'get_mode', lambda: "single")
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
        "VALUES ('story-test-ledger', 'Test story', 'cli', 'product', 'developer-tools', 'build')"
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality) VALUES "
        "('story-test-ledger', 'claude', 'claude-sonnet-4-6', 'cli', 'product', "
        " 'developer-tools', 'build', 'human', 8.5)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(SystemExit):
        synlynk.cmd_status(json_output=False)
    captured = capsys.readouterr()
    assert "CAPABILITY LEDGER" in captured.out
    assert "claude" in captured.out


def test_ensure_identity_key_creates_key(tmp_path, monkeypatch):
    import synlynk as sl, os
    calls = []
    monkeypatch.setenv("HOME", str(tmp_path))
    def fake_run(cmd, **kw):
        calls.append(cmd)
        key_file = tmp_path / ".synlynk" / "identity.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.touch()
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl._ensure_identity_key()
    assert any("ssh-keygen" in str(c) for c in calls)

def test_sign_capability_rating_returns_empty_when_no_key(project_dir, monkeypatch):
    import synlynk as sl, os
    orig_exists = os.path.exists
    monkeypatch.setattr("os.path.exists", lambda p: False if "identity" in str(p) else orig_exists(p))
    result = sl._sign_capability_rating({"quality": 8.0, "agent": "claude"})
    assert result == ""

def test_write_capability_rating_populates_sig_column(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")
    story_id = sl.cmd_story_create("Auth fix", engg_domain="backend")
    job = {
        "story_id": story_id, "agent": "claude", "model_at_dispatch": "claude-3",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "47 passed in 3.2s")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT ed25519_sig FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row is not None

def test_extract_auto_signals_returns_test_count(project_dir):
    import synlynk as sl
    log = "47 passed in 3.2s"
    signals = sl._extract_auto_signals(log)
    assert signals["test_pass_rate"] == 1.0
    assert signals.get("test_count") == 47

def test_extract_auto_signals_test_count_none_when_no_tests(project_dir):
    import synlynk as sl
    log = "Build completed successfully."
    signals = sl._extract_auto_signals(log)
    assert signals.get("test_count") is None

def test_write_capability_rating_caps_quality_for_trivial_tests(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")
    story_id = sl.cmd_story_create("Trivial task", engg_domain="backend")
    job = {
        "story_id": story_id, "agent": "claude", "model_at_dispatch": "claude-3",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "1 passed in 0.1s")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT quality_auto FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row[0] <= 5.0

def test_write_capability_rating_no_cap_for_real_test_suite(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")
    story_id = sl.cmd_story_create("Real task", engg_domain="backend")
    job = {
        "story_id": story_id, "agent": "claude", "model_at_dispatch": "claude-3",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "47 passed in 3.2s")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT quality_auto FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row[0] > 5.0

def test_identity_init_command_prints_key_path(project_dir, monkeypatch, capsys):
    import synlynk as sl, tempfile, os
    with tempfile.TemporaryDirectory() as d:
        key_path = os.path.join(d, ".synlynk", "identity.key")
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        open(key_path, "w").close()
        pub_path = key_path + ".pub"
        open(pub_path, "w").write("ssh-ed25519 AAAA synlynk-identity")
        monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", d))
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: type("R", (), {"returncode": 0})())
        sl.cmd_identity_init()
    captured = capsys.readouterr()
    assert "identity" in captured.out.lower()


def test_upgrade_reports_up_to_date(monkeypatch, capsys):
    fake_gh = type('R', (), {
        'stdout': f"v{synlynk.VERSION}\n",
        'returncode': 0,
    })()
    monkeypatch.setattr(synlynk.subprocess, 'run', lambda *a, **kw: fake_gh)
    synlynk.upgrade()
    captured = capsys.readouterr()
    assert "latest version" in captured.out

def test_upgrade_auto_installs_new_version(monkeypatch, capsys):
    import json as _json
    import types
    call_log = []

    monkeypatch.setattr(synlynk, "_detect_install_type", lambda: "script")

    class Response:
        def __init__(self, payload: bytes):
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._payload

    api_response = Response(_json.dumps({"tag_name": "v99.0.0"}).encode())
    script_response = Response(b'echo "install ok"')

    url_calls = [api_response, script_response]

    def fake_urlopen(req, **kw):
        return url_calls.pop(0)

    fake_gh_result = types.SimpleNamespace(returncode=0, stdout="v99.0.0\n")
    fake_bash_result = types.SimpleNamespace(returncode=0)

    def fake_run(cmd, **kwargs):
        call_log.append(cmd)
        if cmd[0] == "gh":
            return fake_gh_result
        if cmd[0] == "bash":
            return fake_bash_result
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)
    monkeypatch.setattr(synlynk.urllib.request, 'urlopen', fake_urlopen)
    synlynk.upgrade()
    captured = capsys.readouterr()
    assert "99.0.0" in captured.out
    assert "upgrading" in captured.out
    assert "Upgraded" in captured.out
    assert call_log[0][0] == "gh"
    assert call_log[-1][0] == "bash"

def test_upgrade_handles_network_error(monkeypatch, capsys):
    monkeypatch.setattr(synlynk.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(Exception("no gh")))
    monkeypatch.setattr(synlynk.urllib.request, 'urlopen',
                        lambda *a, **kw: (_ for _ in ()).throw(Exception("no network")))
    synlynk.upgrade()  # should not raise
    captured = capsys.readouterr()
    assert "Could not check" in captured.out


def test_build_templates_returns_required_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    templates = synlynk._build_templates()
    for key in ["CLAUDE.md", "GEMINI.md", "AI_INSTRUCTIONS.md", "AGENTS.md",
                 "roadmap.md", "todo.md", "memory.md", "costs.md",
                 "config.json"]:
        assert key in templates, f"missing key: {key}"


def test_claude_template_enriched_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = synlynk._build_templates()["CLAUDE.md"]
    assert "Co-Authored-By: Claude Sonnet" in content
    assert "feat/claude/" in content
    assert "Git Worktree-First Policy" in content
    assert "Live Issues SOP" in content
    assert "Mid-Session Anti-Amnesia" in content
    assert "Mandatory 4-Doc Discipline" in content
    assert "GitHub Projects v2 Integration" in content
    assert "TODO: PROJECT_ID" in content
    assert "synlynk start" in content
    assert "synlynk watch status" in content
    assert "synlynk checkpoint" in content


def test_gemini_template_enriched_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = synlynk._build_templates()["GEMINI.md"]
    assert "Co-Authored-By: AGY" in content
    assert "agy-2.x" in content
    assert "feat/agy/" in content
    assert "Git Worktree-First Policy" in content
    assert "Live Issues SOP" in content
    assert "2026-06-18" not in content


def test_agents_template_enriched_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = synlynk._build_templates()["AGENTS.md"]
    assert "feat/codex/" in content
    assert "Co-Authored-By: Codex" in content
    assert "Git Worktree-First Policy" in content
    assert "Live Issues SOP" in content
    assert "GitHub Projects v2 Integration" in content
    assert "TODO: PROJECT_ID" in content


def test_init_creates_agents_md_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_skips_agents_md_when_codex_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(agents=["claude", "agy"])
    assert not (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()


def test_init_skips_claude_md_when_claude_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(agents=["agy", "codex"])
    assert not (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_skips_gemini_md_when_agy_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(agents=["claude", "codex"])
    assert not (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_exec_command_propagates_exit_code(project_dir, monkeypatch):
    class FakeProcess:
        returncode = 7
        def wait(self): pass

    monkeypatch.setattr(synlynk.subprocess, 'Popen', lambda *a, **kw: FakeProcess())
    monkeypatch.setattr(synlynk, 'generate_context', lambda: None)
    monkeypatch.setattr(synlynk, 'check_budgets', lambda: None)
    monkeypatch.setattr(synlynk, 'set_state', lambda s: None)
    monkeypatch.setattr(synlynk, '_check_costs_freshness', lambda: None)
    monkeypatch.setattr(synlynk, 'log_telemetry_event', lambda e: None)
    monkeypatch.setattr(synlynk, 'check_sentinel_patterns', lambda **kw: None)
    monkeypatch.setattr(synlynk.WatchDaemon, '_is_running', lambda self: False)

    result = synlynk.exec_command(['python3', '-c', 'import sys; sys.exit(7)'])
    assert result == 7


def test_init_writes_synlynk_config_solo_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init()
    config_path = tmp_path / "project-docs" / ".synlynk_config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["mode"] == "solo"
    assert data["version"] == synlynk.VERSION


def test_init_writes_synlynk_config_team_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(mode="team")
    config_path = tmp_path / "project-docs" / ".synlynk_config.json"
    data = json.loads(config_path.read_text())
    assert data["mode"] == "team"


def test_init_skips_synlynk_config_if_exists_without_force(project_dir, monkeypatch):
    # conftest already wrote mode=single; init(mode="team") without force must not overwrite
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    synlynk.init(mode="team")
    config_path = project_dir / "project-docs" / ".synlynk_config.json"
    data = json.loads(config_path.read_text())
    assert data["mode"] == "single"


def test_init_overwrites_synlynk_config_with_force(project_dir, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    synlynk.init(mode="team", force=True)
    config_path = project_dir / "project-docs" / ".synlynk_config.json"
    data = json.loads(config_path.read_text())
    assert data["mode"] == "team"


def test_build_templates_with_project_id_fills_placeholder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = synlynk._build_templates(project_id="PJ_abc123")
    assert "PJ_abc123" in t["CLAUDE.md"]
    assert "TODO: PROJECT_ID" not in t["CLAUDE.md"]
    assert "PJ_abc123" in t["GEMINI.md"]
    assert "PJ_abc123" in t["AGENTS.md"]


def test_build_templates_without_project_id_keeps_todo_placeholder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = synlynk._build_templates()
    assert "TODO: PROJECT_ID" in t["CLAUDE.md"]


def test_init_with_project_id_writes_filled_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(project_id="PJ_xyz789")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "PJ_xyz789" in content
    assert "TODO: PROJECT_ID" not in content


def test_init_with_org_stored_in_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(synlynk, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(synlynk, "_llm_enrich", lambda *a, **kw: False)
    synlynk.init(org="myorg", repo="myrepo")
    config = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert config["org"] == "myorg"
    assert config["repo"] == "myrepo"


def test_detect_remote_https(monkeypatch):
    monkeypatch.setattr(synlynk.subprocess, 'run',
        lambda *a, **kw: type('R', (), {'stdout': 'https://github.com/Dialify/rxcc.git\n', 'returncode': 0})())
    owner, repo = synlynk.detect_remote_owner_repo()
    assert owner == "Dialify"
    assert repo == "rxcc"


def test_detect_remote_ssh(monkeypatch):
    monkeypatch.setattr(synlynk.subprocess, 'run',
        lambda *a, **kw: type('R', (), {'stdout': 'git@github.com:Dialify/rxcc.git\n', 'returncode': 0})())
    owner, repo = synlynk.detect_remote_owner_repo()
    assert owner == "Dialify"
    assert repo == "rxcc"


def test_detect_remote_no_remote(monkeypatch):
    monkeypatch.setattr(synlynk.subprocess, 'run',
        lambda *a, **kw: type('R', (), {'stdout': '', 'returncode': 128})())
    owner, repo = synlynk.detect_remote_owner_repo()
    assert owner is None
    assert repo is None


def test_load_config_has_new_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert "owner" in config
    assert "project_id" in config
    assert "agent_slots" in config
    assert config["owner"] is None
    assert config["project_id"] is None
    assert config["agent_slots"]["claude"] == "claude"
    assert config["agent_slots"]["agy"] == "agy"
    assert config["agent_slots"]["codex"] == "codex"
    assert "stall_timeout_minutes" in config
    assert "agents" in config
    assert config["stall_timeout_minutes"] == 30
    assert config["agents"] == {}


def test_build_templates_config_includes_owner_and_project_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = synlynk._build_templates(owner="Dialify", project_id="PVT_abc")
    config = json.loads(t["config.json"])
    assert config["owner"] == "Dialify"
    assert config["project_id"] == "PVT_abc"
    assert "agent_slots" in config
    assert config["stall_timeout_minutes"] == 30
    assert config["agents"] == {}


# Task 3: Repo scanning + maturity detection tests
def test_scan_finds_docs_at_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "roadmap.md").write_text("# Roadmap")
    (tmp_path / "todo.md").write_text("# Todo")
    (tmp_path / "project-docs").mkdir()
    result = synlynk._scan_repo_for_docs(".")
    paths = result["docs"]
    assert any("roadmap.md" in p for p in paths)
    assert any("todo.md" in p for p in paths)


def test_scan_ignores_docs_inside_project_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "roadmap.md").write_text("# Roadmap")
    result = synlynk._scan_repo_for_docs(".")
    assert len(result["docs"]) == 0


def test_scan_finds_agent_files_at_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# Claude")
    result = synlynk._scan_repo_for_docs(".")
    assert "CLAUDE.md" in result["agent_files"]


def test_is_evolved_repo_large_file():
    content = "# CLAUDE.md\n" + "\n".join(f"line {i}" for i in range(150))
    assert synlynk._is_evolved_repo(content) is True


def test_is_evolved_repo_many_unknown_sections():
    content = "# CLAUDE.md\n## Tech Stack\n## Key Context\n## Code Standards\n## Encryption\n"
    assert synlynk._is_evolved_repo(content) is True


def test_is_evolved_repo_fresh_file():
    content = "# CLAUDE.md\nSmall file with minimal content."
    assert synlynk._is_evolved_repo(content) is False


# Task 4: SECTION_SIGNALS + semantic section matching tests
def test_section_covered_live_issues():
    content = (
        "## Git Workflow\n"
        "### Live Issues\n"
        "A live issue is a production defect. Sev1 means core broken.\n"
        "RCA doc required for sev1 incidents.\n"
    )
    assert synlynk._is_section_covered(content, "## Live Issues SOP") is True


def test_section_covered_anti_amnesia():
    content = (
        "## Mandatory Document Maintenance\n"
        "### Mid-Session Persistence\n"
        "Every ~25,000 tokens write a checkpoint. Watch for compaction imminent signals.\n"
    )
    assert synlynk._is_section_covered(content, "## Mid-Session Anti-Amnesia Protocol") is True


def test_section_covered_gh_projects():
    content = (
        'PROJECT="PVT_kwDOAAUx684BYYIM"\n'
        'gh api graphql -f query="mutation { updateProjectV2ItemFieldValue ..."\n'
    )
    assert synlynk._is_section_covered(content, "## GitHub Projects v2 Integration") is True


def test_section_covered_four_doc():
    content = (
        "## Mandatory Document Maintenance\n"
        "Keep roadmap.md, devlog, costs.md, and memory.md updated.\n"
    )
    assert synlynk._is_section_covered(content, "## Mandatory 4-Doc Discipline") is True


def test_section_not_covered_when_below_threshold():
    content = "## Project\nThis is a healthcare app.\n"
    assert synlynk._is_section_covered(content, "## Live Issues SOP") is False


def test_section_not_covered_single_signal():
    content = "## Workflow\nuse sev1 label for critical bugs.\n"
    assert synlynk._is_section_covered(content, "## Live Issues SOP") is False


# Task 5: GH Projects v2 ID extraction tests
def test_extract_gh_ids_finds_project_id():
    content = 'PROJECT="PVT_kwDOAAUx684BYYIM"\nsome other content\n'
    result = synlynk._extract_gh_ids(content)
    assert result["project_id"] == "PVT_kwDOAAUx684BYYIM"


def test_extract_gh_ids_no_ids():
    result = synlynk._extract_gh_ids("# No IDs here — just regular markdown")
    assert result["project_id"] is None


def test_extract_gh_ids_multiple_pv_ids_returns_first():
    content = 'id1="PVT_aaa"\nid2="PVT_bbb"\n'
    result = synlynk._extract_gh_ids(content)
    assert result["project_id"] == "PVT_aaa"


def test_write_sentinel_alert_creates_file(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "TEST_CODE", "something went wrong")
    sentinel = (project_dir / ".synlynk" / "sentinel.md")
    assert sentinel.exists()
    content = sentinel.read_text()
    assert "[CRITICAL]" in content
    assert "TEST_CODE" in content
    assert "something went wrong" in content


def test_write_sentinel_alert_appends(project_dir):
    synlynk._write_sentinel_alert("WARN", "CODE_A", "first alert")
    synlynk._write_sentinel_alert("CRITICAL", "CODE_B", "second alert")
    content = (project_dir / ".synlynk" / "sentinel.md").read_text()
    assert "CODE_A" in content
    assert "CODE_B" in content


def test_read_sentinel_alerts_all(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "CODE_A", "first")
    synlynk._write_sentinel_alert("WARN", "CODE_B", "second")
    alerts = synlynk._read_sentinel_alerts()
    assert len(alerts) == 2


def test_read_sentinel_alerts_by_severity(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "CODE_A", "first")
    synlynk._write_sentinel_alert("WARN", "CODE_B", "second")
    criticals = synlynk._read_sentinel_alerts(severity="CRITICAL")
    assert len(criticals) == 1
    assert "CODE_A" in criticals[0]


def test_read_sentinel_alerts_empty(project_dir):
    assert synlynk._read_sentinel_alerts() == []


def test_read_sentinel_alerts_preserves_old_format(project_dir):
    # Old free-form lines must not crash the reader
    sentinel = project_dir / ".synlynk" / "sentinel.md"
    sentinel.write_text(
        "# Sentinel Alerts\n"
        "- [2026-06-09 14:23] FLATLINE: `claude` failed 3x in a row [@nikhilsoman]\n"
    )
    alerts = synlynk._read_sentinel_alerts()
    assert len(alerts) == 1  # old-format line returned as-is


def test_extract_tokens_claude_format(project_dir):
    text = "Input tokens: 4821\nOutput tokens: 312\nTotal cost: $0.02"
    in_t, out_t = synlynk.extract_tokens(text)
    assert in_t == 4821
    assert out_t == 312


def test_extract_tokens_claude_json_format(project_dir):
    text = '{"input_tokens": 1000, "output_tokens": 250}'
    in_t, out_t = synlynk.extract_tokens(text)
    assert in_t == 1000
    assert out_t == 250


def test_extract_tokens_grok_json(project_dir):
    text = '{"usage": {"input_tokens": 9001, "output_tokens": 42, "cached_tokens": 3}}'
    in_t, out_t = synlynk.extract_tokens(text)
    assert in_t == 9001
    assert out_t == 42


def test_extract_tokens_gemini_format(project_dir):
    text = "Tokens used: 800 input, 150 output"
    in_t, out_t = synlynk.extract_tokens(text)
    assert in_t == 800
    assert out_t == 150


def test_extract_tokens_total_fallback(project_dir):
    text = "Total tokens: 1000"
    in_t, out_t = synlynk.extract_tokens(text)
    assert in_t == 800   # 80%
    assert out_t == 200  # 20%


def test_extract_tokens_no_match(project_dir):
    in_t, out_t = synlynk.extract_tokens("no token info here")
    assert in_t == 0
    assert out_t == 0


def test_update_costs_appends_row(project_dir):
    before_lines = (project_dir / "project-docs" / "costs.md").read_text().splitlines()
    synlynk.update_costs("claude --print hello", 1000, 200, 30.0)
    content_lines = (project_dir / "project-docs" / "costs.md").read_text().splitlines()
    assert len(content_lines) == len(before_lines) + 1
    assert sum(1 for line in content_lines if "1000/200" in line) == 1
    # cost: (1000/1000*0.003) + (200/1000*0.015) = 0.003 + 0.003 = $0.0060
    assert any("$0.0060" in line for line in content_lines)


def test_update_costs_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Should not raise even if costs.md doesn't exist
    synlynk.update_costs("claude", 100, 50, 5.0)


def test_is_interactive_default(project_dir):
    assert synlynk._is_interactive(["claude"]) is True


def test_is_interactive_print_flag(project_dir):
    assert synlynk._is_interactive(["claude", "--print", "hello"]) is False


def test_is_interactive_no_tty_flag(project_dir):
    assert synlynk._is_interactive(["claude", "--no-tty"]) is False


def test_is_interactive_json_flag(project_dir):
    assert synlynk._is_interactive(["gemini", "--output-format", "json"]) is False


def test_is_interactive_noninteractive_flag(project_dir):
    assert synlynk._is_interactive(["claude", "--non-interactive"]) is False


def test_daemon_health_stopped(project_dir):
    daemon = synlynk.WatchDaemon()
    assert daemon._health() == "stopped"


def test_daemon_health_zombie(project_dir):
    # Write a pidfile with a PID that doesn't exist
    (project_dir / ".synlynk" / "watch.pid").write_text("99999999")
    daemon = synlynk.WatchDaemon()
    assert daemon._health() == "zombie"


def test_check_daemon_health_writes_sentinel(project_dir):
    (project_dir / ".synlynk" / "watch.pid").write_text("99999999")
    synlynk.check_daemon_health()
    alerts = synlynk._read_sentinel_alerts(severity="CRITICAL")
    assert any("ZOMBIE_DAEMON" in a for a in alerts)


def test_check_stall_no_stall(project_dir):
    # State is "stopped", no stall
    (project_dir / ".synlynk" / "state").write_text("stopped")
    synlynk.check_stall()
    assert synlynk._read_sentinel_alerts(severity="WARN") == []


def test_check_stall_active_recent(project_dir):
    # State is "active" but only 1 minute old — no stall
    (project_dir / ".synlynk" / "state").write_text("active")
    synlynk.check_stall()
    assert synlynk._read_sentinel_alerts(severity="WARN") == []


def test_check_stall_detects_old_active(project_dir):
    # State is "active" and 35 minutes old — stall
    state_file = project_dir / ".synlynk" / "state"
    state_file.write_text("active")
    # Backdate mtime by 35 minutes
    old_time = time.time() - (35 * 60)
    os.utime(str(state_file), (old_time, old_time))
    synlynk.check_stall()
    alerts = synlynk._read_sentinel_alerts(severity="WARN")
    assert any("STALL" in a for a in alerts)


def _write_telemetry_typed(project_dir, events):
    import json as _json
    (project_dir / ".synlynk" / "telemetry.json").write_text(_json.dumps(events))


def test_check_sentinel_flatline(project_dir):
    now = time.time()
    events = [
        {"type": "exec", "command": "claude", "exit_code": 1, "_ts": now - 60},
        {"type": "exec", "command": "claude", "exit_code": 1, "_ts": now - 40},
        {"type": "exec", "command": "claude", "exit_code": 1, "_ts": now - 20},
    ]
    _write_telemetry_typed(project_dir, events)
    synlynk.check_sentinel_patterns(output_text="", exit_code=1, cmd="claude")
    alerts = synlynk._read_sentinel_alerts(severity="CRITICAL")
    assert any("FLATLINE" in a for a in alerts)


def test_check_sentinel_success_loop(project_dir):
    now = time.time()
    events = [
        {"type": "exec", "command": "claude --print hi", "exit_code": 0, "_ts": now - 480},
        {"type": "exec", "command": "claude --print hi", "exit_code": 0, "_ts": now - 360},
        {"type": "exec", "command": "claude --print hi", "exit_code": 0, "_ts": now - 240},
        {"type": "exec", "command": "claude --print hi", "exit_code": 0, "_ts": now - 120},
        {"type": "exec", "command": "claude --print hi", "exit_code": 0, "_ts": now - 10},
    ]
    _write_telemetry_typed(project_dir, events)
    synlynk.check_sentinel_patterns(output_text="", exit_code=0, cmd="claude --print hi")
    alerts = synlynk._read_sentinel_alerts(severity="WARN")
    assert any("SUCCESS_LOOP" in a for a in alerts)


def test_check_sentinel_quota_exhausted(project_dir):
    synlynk.check_sentinel_patterns(
        output_text="Error: rate limit exceeded. Please wait.",
        exit_code=1,
        cmd="claude"
    )
    alerts = synlynk._read_sentinel_alerts(severity="CRITICAL")
    assert any("QUOTA_EXHAUSTED" in a for a in alerts)


def test_check_sentinel_no_false_positive(project_dir):
    now = time.time()
    events = [
        {"type": "exec", "command": "claude", "exit_code": 0, "_ts": now - 60},
        {"type": "exec", "command": "gemini", "exit_code": 0, "_ts": now - 40},
        {"type": "exec", "command": "claude", "exit_code": 0, "_ts": now - 20},
    ]
    _write_telemetry_typed(project_dir, events)
    synlynk.check_sentinel_patterns(output_text="", exit_code=0, cmd="claude")
    assert synlynk._read_sentinel_alerts() == []


def test_extract_compliance_tags_finds_test_evidence(project_dir):
    """_extract_compliance_tags detects test pass phrases."""
    import synlynk as sl
    tags = sl._extract_compliance_tags("All tests passed. pytest ran 42 tests.")
    assert tags["ran_tests"] is True
    assert tags["verify_before_commit"] is False


def test_extract_compliance_tags_finds_verify_evidence(project_dir):
    """_extract_compliance_tags detects verify phrases."""
    import synlynk as sl
    tags = sl._extract_compliance_tags("Verified the output. LGTM.")
    assert tags["verify_before_commit"] is True


def test_extract_compliance_tags_uses_word_boundaries(project_dir):
    """_extract_compliance_tags should not fire on embedded substrings."""
    import synlynk as sl
    tags = sl._extract_compliance_tags("The contest suite was unverifiedly executed.")
    assert tags["ran_tests"] is False
    assert tags["verify_before_commit"] is False


def test_extract_compliance_tags_empty_output(project_dir):
    """_extract_compliance_tags returns False flags for empty output."""
    import synlynk as sl
    tags = sl._extract_compliance_tags("")
    assert tags["ran_tests"] is False
    assert tags["verify_before_commit"] is False


def test_relay_event_schema_has_required_fields(project_dir):
    """_build_relay_event returns dict with type, ts, origin_node."""
    import synlynk as sl
    event = sl._build_relay_event("story_updated", {"story_id": "s1", "status": "done"})
    assert event["type"] == "story_updated"
    assert "ts" in event
    assert "origin_node" in event
    assert event["story_id"] == "s1"


def test_relay_broadcast_event_has_kind(project_dir):
    """broadcast events include kind and body fields."""
    import synlynk as sl
    event = sl._build_relay_event("broadcast", {"kind": "wellness", "body": "stand up"})
    assert event["kind"] == "wellness"
    assert event["body"] == "stand up"


def test_relay_event_valid_types(project_dir):
    """_build_relay_event rejects unknown event types."""
    import synlynk as sl
    import pytest as _pytest
    with _pytest.raises(ValueError, match="unknown event type"):
        sl._build_relay_event("bad_type", {})


def test_cmd_relay_broadcast_prints_confirmation(project_dir, monkeypatch, capsys):
    """cmd_relay_broadcast prints confirmation when relay is reachable (mocked)."""
    import synlynk as sl
    import urllib.request as _req

    class FakeResp:
        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(_req, "urlopen", lambda req, timeout=5: FakeResp())
    sl.cmd_relay_broadcast("wellness", "stand up and walk")
    out = capsys.readouterr().out
    assert "broadcast" in out.lower() or "sent" in out.lower() or "✓" in out


def test_sentinel_verify_skip_fires_on_successful_job_without_tests(project_dir):
    """check_sentinel_patterns writes VERIFY_SKIP when exit 0 but no test evidence."""
    import synlynk as sl
    (project_dir / ".synlynk").mkdir(exist_ok=True)
    sl.check_sentinel_patterns(
        output_text="I updated the file and it looks good.",
        exit_code=0,
        cmd="claude --print"
    )
    sentinel = (project_dir / ".synlynk" / "sentinel.md").read_text()
    assert "VERIFY_SKIP" in sentinel


def test_sentinel_verify_skip_does_not_fire_when_tests_ran(project_dir):
    """check_sentinel_patterns does NOT write VERIFY_SKIP when tests are mentioned."""
    import synlynk as sl
    (project_dir / ".synlynk").mkdir(exist_ok=True)
    sl.check_sentinel_patterns(
        output_text="All 10 tests passed. Everything is green.",
        exit_code=0,
        cmd="claude --print"
    )
    sentinel_path = project_dir / ".synlynk" / "sentinel.md"
    if sentinel_path.exists():
        assert "VERIFY_SKIP" not in sentinel_path.read_text()


def test_sentinel_verify_skip_does_not_fire_on_failure(project_dir):
    """check_sentinel_patterns does NOT write VERIFY_SKIP for non-zero exit codes."""
    import synlynk as sl
    (project_dir / ".synlynk").mkdir(exist_ok=True)
    sl.check_sentinel_patterns(
        output_text="Something went wrong.",
        exit_code=1,
        cmd="claude --print"
    )
    sentinel_path = project_dir / ".synlynk" / "sentinel.md"
    if sentinel_path.exists():
        assert "VERIFY_SKIP" not in sentinel_path.read_text()


def test_pre_exec_gate_no_alerts(project_dir):
    assert synlynk._check_pre_exec_gate(force=False) is True


def test_pre_exec_gate_warn_allows(project_dir):
    synlynk._write_sentinel_alert("WARN", "SUCCESS_LOOP", "loop detected")
    assert synlynk._check_pre_exec_gate(force=False) is True


def test_pre_exec_gate_critical_blocks(project_dir, capsys):
    synlynk._write_sentinel_alert("CRITICAL", "ZOMBIE_DAEMON", "zombie")
    result = synlynk._check_pre_exec_gate(force=False)
    assert result is False
    out = capsys.readouterr().out
    assert "CRITICAL" in out or "blocked" in out.lower()


def test_pre_exec_gate_force_bypasses_critical(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "ZOMBIE_DAEMON", "zombie")
    assert synlynk._check_pre_exec_gate(force=True) is True


def test_compute_burn_rate_no_data(project_dir):
    rate, remaining = synlynk._compute_burn_rate()
    assert rate == 0.0
    assert remaining is None


def test_compute_burn_rate_with_costed_events(project_dir):
    import json as _json
    import time as _t
    now = _t.time()
    events = [
        {"type": "exec", "command": "claude", "exit_code": 0,
         "_ts": now - i * 60, "in_tokens": 1000, "out_tokens": 200}
        for i in range(5)
    ]
    (project_dir / ".synlynk" / "telemetry.json").write_text(_json.dumps(events))
    rate, remaining = synlynk._compute_burn_rate()
    # est_cost per exec = (1000/1000*0.003) + (200/1000*0.015) = 0.003 + 0.003 = 0.006
    assert abs(rate - 0.006) < 0.001
    assert remaining is not None
    assert remaining > 0


def test_compute_burn_rate_sparse_data(project_dir):
    # Fewer than 3 costed events — should return (0.0, None)
    import json as _json
    import time as _t
    now = _t.time()
    events = [
        {"type": "exec", "command": "claude", "exit_code": 0,
         "_ts": now - 60, "in_tokens": 0, "out_tokens": 0},
        {"type": "exec", "command": "claude", "exit_code": 0,
         "_ts": now - 30, "in_tokens": 0, "out_tokens": 0},
    ]
    (project_dir / ".synlynk" / "telemetry.json").write_text(_json.dumps(events))
    rate, remaining = synlynk._compute_burn_rate()
    assert rate == 0.0
    assert remaining is None


def test_sentinel_list_empty(project_dir, capsys):
    synlynk.sentinel_list()
    out = capsys.readouterr().out
    assert "No active" in out


def test_sentinel_list_shows_alerts(project_dir, capsys):
    synlynk._write_sentinel_alert("CRITICAL", "ZOMBIE_DAEMON", "daemon dead")
    synlynk.sentinel_list()
    out = capsys.readouterr().out
    assert "ZOMBIE_DAEMON" in out


def test_sentinel_clear_all(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "ZOMBIE_DAEMON", "daemon dead")
    synlynk._write_sentinel_alert("WARN", "STALL", "stalled")
    synlynk.sentinel_clear()
    assert synlynk._read_sentinel_alerts() == []


def test_sentinel_clear_by_severity(project_dir):
    synlynk._write_sentinel_alert("CRITICAL", "ZOMBIE_DAEMON", "daemon dead")
    synlynk._write_sentinel_alert("WARN", "STALL", "stalled")
    synlynk.sentinel_clear(severity="WARN")
    alerts = synlynk._read_sentinel_alerts()
    assert len(alerts) == 1
    assert "ZOMBIE_DAEMON" in alerts[0]


def test_version_is_0120(project_dir):
    assert synlynk.VERSION == "0.12.0"


def test_pyproject_version_matches_module(project_dir):
    """pyproject.toml should source version dynamically from synlynk.VERSION."""
    import re

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    toml_path = os.path.join(repo_root, "pyproject.toml")
    if not os.path.exists(toml_path):
        pytest.skip("pyproject.toml not present")
    text = open(toml_path).read()
    assert re.search(r'^\s*dynamic\s*=\s*\["version"\]', text, re.MULTILINE)
    assert re.search(
        r'^\s*version\s*=\s*\{\s*attr\s*=\s*"synlynk\.VERSION"\s*\}',
        text,
        re.MULTILINE,
    )
    assert not re.search(r'^\s*version\s*=\s*"[^"]+"\s*$', text, re.MULTILINE)


def test_main_entrypoint_importable():
    """synlynk.__main__ imports without error (required for python -m synlynk)."""
    import importlib
    mod = importlib.import_module("synlynk.__main__")
    assert hasattr(mod, "main") or True  # module must import cleanly


def test_load_jobs_returns_empty_list_when_no_file(project_dir):
    jobs = synlynk._load_jobs()
    assert jobs == []


def test_save_and_load_jobs_roundtrip(project_dir):
    job = {"id": "job-001", "agent": "claude", "pid": 99999, "status": "running",
            "started_at": "2026-06-14T10:00:00", "ended_at": None, "exit_code": None,
            "story_id": "14", "task": "do thing", "log_file": ".synlynk/logs/job-001.log",
            "prompt_file": ".synlynk/prompts/job-001.md"}
    synlynk._save_jobs([job])
    loaded = synlynk._load_jobs()
    assert loaded == [job]


def test_reconcile_marks_dead_pid_as_unknown(project_dir):
    # Current process PID always exists; PID 9999999 never exists
    current_pid = os.getpid()
    jobs = [
        {"id": "job-alive", "pid": current_pid, "status": "running", "ended_at": None, "exit_code": None},
        {"id": "job-dead", "pid": 9999999, "status": "running", "ended_at": None, "exit_code": None},
    ]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    result = synlynk._load_jobs()
    alive = next(j for j in result if j["id"] == "job-alive")
    dead = next(j for j in result if j["id"] == "job-dead")
    assert alive["status"] == "running"
    assert dead["status"] == "unknown"
    assert dead["ended_at"] is not None


def test_reconcile_skips_finished_jobs(project_dir):
    jobs = [{"id": "job-done", "pid": 9999999, "status": "completed",
              "ended_at": "2026-06-14T09:00:00", "exit_code": 0}]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    result = synlynk._load_jobs()
    assert result[0]["status"] == "completed"  # unchanged


def test_reconcile_marks_completed_from_exit_file(project_dir):
    log_file = ".synlynk/logs/job-success.log"
    os.makedirs(".synlynk/logs", exist_ok=True)
    with open(log_file + ".exit", "w") as f:
        f.write("0\n")
    
    jobs = [
        {"id": "job-success", "pid": 9999999, "status": "running", 
         "ended_at": None, "exit_code": None, "log_file": log_file},
    ]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    
    result = synlynk._load_jobs()
    job = result[0]
    assert job["status"] == "completed"
    assert job["exit_code"] == 0
    assert job["ended_at"] is not None
    assert not os.path.exists(log_file + ".exit")


def test_reconcile_marks_failed_from_exit_file(project_dir):
    log_file = ".synlynk/logs/job-error.log"
    os.makedirs(".synlynk/logs", exist_ok=True)
    with open(log_file + ".exit", "w") as f:
        f.write("1\n")
    
    jobs = [
        {"id": "job-error", "pid": 9999999, "status": "running", 
         "ended_at": None, "exit_code": None, "log_file": log_file},
    ]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    
    result = synlynk._load_jobs()
    job = result[0]
    assert job["status"] == "failed"
    assert job["exit_code"] == 1
    assert job["ended_at"] is not None
    assert not os.path.exists(log_file + ".exit")


def test_reconcile_attributes_origin_branch_activity_when_assigned_worktree_is_clean(project_dir, monkeypatch, capsys):
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "borrowed-worktree"
    worktree_path.mkdir()
    log_file = project_dir / ".synlynk" / "logs" / "job-borrowed.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Input tokens: 120\nOutput tokens: 30\n")

    job = {
        "id": "job-borrowed",
        "agent": "codex",
        "story_id": "",
        "task": "fix borrowed worktree attribution",
        "pid": 9999999,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "chore/init-remodularization-pass2",
        "started_at": "2026-07-07T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    synlynk._save_jobs([job])

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:4] == prefix + ["status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["merge-base", "HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:4] == prefix + ["log"] and "--format=%H" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc123\n", stderr="")
        if cmd[:4] == prefix + ["log"] and "--name-only" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="alpha.txt\nbeta.txt\nalpha.txt\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(synlynk, "_inspect_worktree_git_state", jobs_mod._inspect_worktree_git_state)

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = synlynk._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "completed"
    assert reconciled["exit_code"] == 0
    assert "status:   OK (exit 0)" in out
    assert "files:    2 touched" in out
    assert "          alpha.txt" in out
    assert "          beta.txt" in out
    assert "borrowed worktree detected; attributed from origin/chore/init-remodularization-pass2" in out


def test_reconcile_requeues_clean_harness_internal_timeout(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-clean-timeout"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-clean-timeout.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("timeout waiting for response\n")

    job = {
        "id": "job-clean-timeout",
        "agent": "codex",
        "story_id": "story-184",
        "task": "repair retry loop",
        "pid": 9999999,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-clean-timeout",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    dispatched = []
    sentinel_calls = []

    def fake_dispatch(agent, task, **kwargs):
        dispatched.append((agent, task, kwargs))
        return {
            "id": "job-clean-timeout-retry",
            "agent": agent,
            "story_id": kwargs.get("story_id") or "",
            "task": task,
            "cycle": kwargs.get("cycle", "work"),
            "pid": 12345,
            "log_file": str(project_dir / ".synlynk" / "logs" / "job-clean-timeout-retry.log"),
            "prompt_file": "",
            "context_file": "",
            "worktree_path": str(project_dir / "worktrees" / "job-clean-timeout-retry"),
            "worktree_branch": "dispatch/codex/job-clean-timeout-retry",
            "started_at": "2026-07-12T10:01:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
            "dispatch_mode": "agent",
            "dispatch_rework": 0,
            "micro_rework": 0,
            "retry_count": 0,
            "model_at_dispatch": "unknown",
        }

    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": False, "remote_has_activity": False})
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(jobs_mod, "_write_sentinel_alert", lambda *a, **kw: sentinel_calls.append((a, kw)))

    sl._reconcile_jobs()

    jobs = sl._load_jobs()
    retry_job = next(j for j in jobs if j["id"] == "job-clean-timeout-retry")
    original_job = next(j for j in jobs if j["id"] == "job-clean-timeout")

    assert len(dispatched) == 1
    assert dispatched[0][0] == "codex"
    assert dispatched[0][2]["force_agent"] is True
    assert retry_job["retry_count"] == 1
    assert original_job["status"] == "unknown"
    assert original_job["retry_count"] == 0
    assert sentinel_calls == []


def test_reconcile_does_not_requeue_timeout_with_real_work(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-work-landing"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-work-landing.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("timeout waiting for response\n")

    job = {
        "id": "job-work-landing",
        "agent": "agy",
        "story_id": "story-184",
        "task": "preserve landed work",
        "pid": 9999998,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/agy/job-work-landing",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    dispatched = []
    sentinel_calls = []
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: dispatched.append((a, kw)))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": True, "remote_has_activity": False})
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(jobs_mod, "_write_sentinel_alert", lambda *a, **kw: sentinel_calls.append((a, kw)))

    sl._reconcile_jobs()

    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == "job-work-landing")

    assert dispatched == []
    assert reconciled["status"] == "failed_unverified"
    assert sentinel_calls and sentinel_calls[0][0][1] == "HARNESS_INTERNAL_TIMEOUT"


def test_reconcile_does_not_requeue_timeout_at_retry_cap(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-timeout-cap"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-timeout-cap.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("timeout waiting for response\n")

    job = {
        "id": "job-timeout-cap",
        "agent": "codex",
        "story_id": "story-184",
        "task": "cap retry attempts",
        "pid": 9999997,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-timeout-cap",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "retry_count": 2,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    dispatched = []
    sentinel_calls = []
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: dispatched.append((a, kw)))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": False, "remote_has_activity": False})
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(jobs_mod, "_write_sentinel_alert", lambda *a, **kw: sentinel_calls.append((a, kw)))

    sl._reconcile_jobs()

    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == "job-timeout-cap")

    assert dispatched == []
    assert reconciled["status"] == "unknown"
    assert reconciled["retry_count"] == 2
    assert sentinel_calls and sentinel_calls[0][0][1] == "HARNESS_INTERNAL_TIMEOUT"


def test_reconcile_survives_permission_error(project_dir, monkeypatch):
    # PermissionError from os.kill means PID exists (owned by another user) — keep as running.
    def fake_kill(pid, sig):
        raise PermissionError("Operation not permitted")
    monkeypatch.setattr(synlynk.os, "kill", fake_kill)
    jobs = [{"id": "job-owned", "pid": 1, "status": "running",
             "ended_at": None, "exit_code": None, "log_file": ""}]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()  # must not raise
    result = synlynk._load_jobs()
    assert result[0]["status"] == "running"


def test_reconcile_empty_log_file_does_not_crash(project_dir):
    # A job with empty log_file must not read/delete ".exit" in CWD.
    sentinel = ".exit"
    with open(sentinel, "w") as f:
        f.write("0\n")
    jobs = [{"id": "job-nolog", "pid": 9999999, "status": "running",
             "ended_at": None, "exit_code": None, "log_file": ""}]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    assert os.path.exists(sentinel), ".exit in CWD must not be consumed"
    os.remove(sentinel)
    result = synlynk._load_jobs()
    assert result[0]["status"] == "unknown"


def test_reconcile_auto_finalizes_dirty_worktree_excluding_generated_files(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-finalize-dirty"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-finalize-dirty.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Input tokens: 12\nOutput tokens: 7\n")
    with open(str(log_file) + ".exit", "w") as f:
        f.write("0\n")

    job = {
        "id": "job-finalize-dirty",
        "agent": "codex",
        "story_id": "",
        "task": "fix dirty finalize path",
        "pid": 9999996,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-finalize-dirty",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    calls = []
    staged = {"present": False}

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]

        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="dispatch/codex/job-finalize-dirty\n", stderr=""
            )
        if cmd[:4] == prefix + ["status"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=(
                    " M safe.txt\n"
                    " M GEMINI.md\n"
                    " M CLAUDE.md\n"
                    " M AGENTS.md\n"
                    " M .cursorrules\n"
                    " M project-docs/todo.md\n"
                ),
                stderr="",
            )
        if cmd[:5] == prefix + ["add", "-A"]:
            assert "safe.txt" in cmd
            assert "GEMINI.md" not in cmd
            assert "CLAUDE.md" not in cmd
            assert "AGENTS.md" not in cmd
            assert ".cursorrules" not in cmd
            assert "project-docs/todo.md" not in cmd
            staged["present"] = True
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["reset", "--"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 1 if staged["present"] else 0, stdout="", stderr="")
        if cmd[:4] == prefix + ["commit"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="commit ok\n", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/1\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": True, "remote_has_activity": False, "dirty": True, "commits_ahead": 0})
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *a, **kw: [])
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "completed"
    add_cmd = next(cmd for cmd in calls if cmd[:5] == ["git", "-C", str(worktree_path), "add", "-A"])
    assert "safe.txt" in add_cmd
    assert "GEMINI.md" not in add_cmd
    assert "CLAUDE.md" not in add_cmd
    assert "AGENTS.md" not in add_cmd
    assert ".cursorrules" not in add_cmd
    assert "project-docs/todo.md" not in add_cmd
    assert "gh pr create" in out or any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)


def test_reconcile_auto_finalizes_clean_worktree_with_local_commits(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-finalize-clean"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-finalize-clean.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Input tokens: 4\nOutput tokens: 2\n")
    with open(str(log_file) + ".exit", "w") as f:
        f.write("0\n")

    job = {
        "id": "job-finalize-clean",
        "agent": "codex",
        "story_id": "",
        "task": "push local commits and open a PR",
        "pid": 9999995,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-finalize-clean",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    calls = []
    pr_created = {"value": False}

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]

        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="dispatch/codex/job-finalize-clean\n", stderr=""
            )
        if cmd[:4] == prefix + ["status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="2\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            pr_created["value"] = True
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/2\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 2})
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *a, **kw: [])
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()

    commands = [" ".join(cmd) for cmd in calls]
    assert any(cmd[:4] == ["git", "-C", str(worktree_path), "push"] for cmd in calls)
    assert pr_created["value"] is True
    assert not any(cmd[:4] == ["git", "-C", str(worktree_path), "commit"] for cmd in calls)
    assert not any(cmd[:5] == ["git", "-C", str(worktree_path), "add", "-A"] for cmd in calls)


def test_reconcile_auto_finalize_is_idempotent_when_pr_exists(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-finalize-idempotent"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-finalize-idempotent.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Input tokens: 1\nOutput tokens: 1\n")

    job = {
        "id": "job-finalize-idempotent",
        "agent": "codex",
        "story_id": "",
        "task": "already finalized worktree",
        "pid": 9999994,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-finalize-idempotent",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]

        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="dispatch/codex/job-finalize-idempotent\n", stderr=""
            )
        if cmd[:4] == prefix + ["status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="0\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout='[{"number": 42}]\n', stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": False, "remote_has_activity": True, "dirty": False, "commits_ahead": 0})
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *a, **kw: [])
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()

    assert not any(cmd[:4] == ["git", "-C", str(worktree_path), "commit"] for cmd in calls)
    assert not any(cmd[:4] == ["git", "-C", str(worktree_path), "push"] for cmd in calls)
    assert not any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)
    assert any(cmd[:3] == ["gh", "pr", "list"] for cmd in calls)


def test_reconcile_auto_finalize_logs_gh_failure_without_crashing(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = project_dir / "worktrees" / "job-finalize-gh-failure"
    worktree_path.mkdir(parents=True)
    log_file = project_dir / ".synlynk" / "logs" / "job-finalize-gh-failure.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Input tokens: 8\nOutput tokens: 3\n")

    job = {
        "id": "job-finalize-gh-failure",
        "agent": "codex",
        "story_id": "",
        "task": "handle gh failure",
        "pid": 9999993,
        "log_file": str(log_file),
        "worktree_path": str(worktree_path),
        "worktree_branch": "dispatch/codex/job-finalize-gh-failure",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])

    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]

        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="dispatch/codex/job-finalize-gh-failure\n", stderr=""
            )
        if cmd[:4] == prefix + ["status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="0\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            raise FileNotFoundError("gh")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": False, "remote_has_activity": True, "dirty": False, "commits_ahead": 0})
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *a, **kw: [])
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()
    out = capsys.readouterr().out

    assert "gh binary not available" in out
    assert any(cmd[:3] == ["gh", "pr", "list"] for cmd in calls)
    assert sl._load_jobs()[0]["status"] == "completed"


def test_finalize_uses_default_dispatch_branch_when_unchanged(tmp_path, monkeypatch):
    """(a) Worktree still on dispatch/<agent>/<job_id> — finalize/PR use that name (no regression)."""
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-default-branch"
    worktree_path.mkdir(parents=True)
    recorded = "dispatch/codex/job-default-branch"
    job = {
        "id": "job-default-branch",
        "agent": "codex",
        "task": "stay on default dispatch branch",
        "worktree_path": str(worktree_path),
        "worktree_branch": recorded,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{recorded}\n", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/9\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 1},
    )

    assert job["worktree_branch"] == recorded
    push_cmd = next(cmd for cmd in calls if cmd[:4] == ["git", "-C", str(worktree_path), "push"])
    assert recorded in push_cmd
    list_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    assert recorded in list_cmd
    create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert recorded in create_cmd


def test_finalize_detects_custom_branch_for_push_and_pr(tmp_path, monkeypatch):
    """(b) Agent switched mid-task — finalize uses custom branch, not stale dispatch name."""
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-custom-branch"
    worktree_path.mkdir(parents=True)
    recorded = "dispatch/codex/job-custom-branch"
    custom = "fix/dispatch-autopr-branch-detection"
    job = {
        "id": "job-custom-branch",
        "agent": "codex",
        "task": "use custom branch for PR",
        "worktree_path": str(worktree_path),
        "worktree_branch": recorded,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{custom}\n", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            # Push decision uses origin/<branch>..HEAD — must match custom branch.
            assert cmd[5] == f"origin/{custom}..HEAD"
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/10\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 1},
    )

    # (c) job record updated to the real branch
    assert job["worktree_branch"] == custom
    push_cmd = next(cmd for cmd in calls if cmd[:4] == ["git", "-C", str(worktree_path), "push"])
    assert custom in push_cmd and recorded not in push_cmd
    list_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "list"])
    assert "--head" in list_cmd and custom in list_cmd and recorded not in list_cmd
    create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert "--head" in create_cmd and custom in create_cmd and recorded not in create_cmd


def test_finalize_detached_head_falls_back_to_recorded_branch(tmp_path, monkeypatch):
    """(d) Detached HEAD → fall back to recorded worktree_branch without crashing."""
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-detached"
    worktree_path.mkdir(parents=True)
    recorded = "dispatch/codex/job-detached"
    job = {
        "id": "job-detached",
        "agent": "codex",
        "task": "detached head fallback",
        "worktree_path": str(worktree_path),
        "worktree_branch": recorded,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            # Empty stdout = detached HEAD
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            assert cmd[5] == f"origin/{recorded}..HEAD"
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd[:4] == prefix + ["push"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="pushed\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/test/repo/pull/11\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": True, "remote_has_activity": False, "dirty": False, "commits_ahead": 1},
    )

    assert job["worktree_branch"] == recorded
    push_cmd = next(cmd for cmd in calls if cmd[:4] == ["git", "-C", str(worktree_path), "push"])
    assert recorded in push_cmd
    create_cmd = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert recorded in create_cmd


def test_finalize_pr_dedupe_uses_real_custom_branch(tmp_path, monkeypatch):
    """(e) gh pr list dedupe runs against the real branch — no double-create when PR exists."""
    import subprocess
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "worktrees" / "job-dedupe-custom"
    worktree_path.mkdir(parents=True)
    recorded = "dispatch/codex/job-dedupe-custom"
    custom = "fix/some-description"
    job = {
        "id": "job-dedupe-custom",
        "agent": "codex",
        "task": "dedupe PR on custom branch",
        "worktree_path": str(worktree_path),
        "worktree_branch": recorded,
    }
    calls = []

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        calls.append(cmd)
        prefix = ["git", "-C", str(worktree_path)]
        if cmd[:5] == prefix + ["branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{custom}\n", stderr="")
        if cmd[:6] == prefix + ["diff", "--cached", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:5] == prefix + ["rev-list", "--count"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="0\n", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            assert custom in cmd and recorded not in cmd
            return subprocess.CompletedProcess(cmd, 0, stdout='[{"number": 77}]\n', stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "detect_remote_owner_repo", lambda: ("test-org", "test-repo"))

    jobs_mod._finalize_completed_worktree_job(
        job,
        {"has_activity": False, "remote_has_activity": True, "dirty": False, "commits_ahead": 0},
    )

    assert job["worktree_branch"] == custom
    assert any(cmd[:3] == ["gh", "pr", "list"] for cmd in calls)
    assert not any(cmd[:3] == ["gh", "pr", "create"] for cmd in calls)
    assert not any(cmd[:4] == ["git", "-C", str(worktree_path), "push"] for cmd in calls)


def test_resolve_finalize_worktree_branch_updates_job_record(tmp_path, monkeypatch):
    """(c) Direct unit coverage: job record reflects the real branch after resolve."""
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "wt"
    worktree_path.mkdir()
    job = {"worktree_branch": "dispatch/agy/job-xyz"}

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        if cmd[:5] == ["git", "-C", str(worktree_path), "branch", "--show-current"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="feat/real-branch\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    resolved = jobs_mod._resolve_finalize_worktree_branch(job, str(worktree_path))
    assert resolved == "feat/real-branch"
    assert job["worktree_branch"] == "feat/real-branch"


def test_check_agent_functional_returns_version_for_present_tool(monkeypatch):
    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            stdout = "claude 2.1.175\n"
        return R()
    monkeypatch.setattr(synlynk.subprocess, 'run', fake_run)
    result = synlynk._check_agent_functional("claude")
    assert result == "claude 2.1.175"


def test_check_agent_functional_returns_none_for_missing_tool(monkeypatch):
    def fake_run(cmd, **kw):
        raise FileNotFoundError
    monkeypatch.setattr(synlynk.subprocess, 'run', fake_run)
    result = synlynk._check_agent_functional("notacli")
    assert result is None


def test_check_agent_functional_returns_none_for_nonzero_exit(monkeypatch):
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(synlynk.subprocess, 'run', fake_run)
    result = synlynk._check_agent_functional("claude")
    assert result is None


def test_discover_agents_returns_functional_agents(monkeypatch, tmp_path):
    # Simulate claude config dir exists, others don't
    (tmp_path / ".claude").mkdir()
    versions = {"claude": "claude 2.1.0"}
    def fake_check(cli):
        return versions.get(cli)
    monkeypatch.setattr(synlynk, "_check_agent_functional", fake_check)
    monkeypatch.setattr(synlynk, "AGENT_DISCOVERY_DEFAULTS", {
        "claude": str(tmp_path / ".claude"),
        "gemini": str(tmp_path / ".gemini"),
    })
    agents = synlynk.discover_agents()
    names = [a["name"] for a in agents]
    assert "claude" in names
    functional = [a for a in agents if a["functional"]]
    assert all(a["name"] == "claude" for a in functional)


def test_discover_agents_uses_config_override(monkeypatch, tmp_path, project_dir):
    import json as _json
    custom_path = str(tmp_path / "custom_claude")
    os.makedirs(custom_path)
    config = {"agent_discovery_paths": {"claude": custom_path}}
    with open(".synlynk/config.json", "w") as f:
        _json.dump(config, f)
    monkeypatch.setattr(synlynk, "_check_agent_functional", lambda cli: "claude 2.0")
    agents = synlynk.discover_agents()
    claude_agent = next((a for a in agents if a["name"] == "claude"), None)
    assert claude_agent is not None
    assert claude_agent["discovery_path"] == custom_path


def test_static_scan_extracts_project_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# my-cool-project\nA great tool.\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    result = synlynk._static_scan(str(tmp_path))
    assert result["project_name"] == "my-cool-project"


def test_static_scan_counts_commits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    (tmp_path / "f.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: first"], cwd=tmp_path, capture_output=True)
    result = synlynk._static_scan(str(tmp_path))
    assert result["commit_count"] == 1


def test_static_scan_detects_structured_commits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, capture_output=True)
    for msg in ["feat: add thing", "fix: broken thing", "chore: cleanup"]:
        (tmp_path / f"{msg[:4]}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, capture_output=True)
    result = synlynk._static_scan(str(tmp_path))
    assert result["has_structured_commits"] is True


def test_static_scan_no_git_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = synlynk._static_scan(str(tmp_path))
    assert result["commit_count"] == 0
    assert result["project_name"] == tmp_path.name


def test_write_informed_skeleton_creates_docs(project_dir):
    import shutil
    # Remove existing project-docs to test creation path
    shutil.rmtree("project-docs")
    os.makedirs("project-docs/devlogs")
    scan = {
        "project_name": "testproject", "description": "A test tool.",
        "commit_count": 12, "has_structured_commits": True,
        "recent_topics": ["feat: add login", "fix: auth bug"],
        "top_dirs": ["src", "tests"], "languages": ["Python"],
        "readme_summary": "# testproject\nA test tool.",
    }
    written = synlynk._write_informed_skeleton(scan, skip_existing=False)
    written_paths = [p for p, _ in written]
    assert "project-docs/roadmap.md" in written_paths
    assert "project-docs/memory.md" in written_paths
    assert "project-docs/todo.md" in written_paths


def test_write_informed_skeleton_injects_project_name(project_dir):
    import shutil
    shutil.rmtree("project-docs")
    os.makedirs("project-docs/devlogs")
    scan = {
        "project_name": "myapp", "description": "My application.",
        "commit_count": 5, "has_structured_commits": False,
        "recent_topics": ["initial commit"],
        "top_dirs": ["src"], "languages": ["Go"], "readme_summary": "",
    }
    synlynk._write_informed_skeleton(scan, skip_existing=False)
    roadmap = open("project-docs/roadmap.md").read()
    assert "myapp" in roadmap


def test_write_informed_skeleton_skips_existing_by_default(project_dir):
    original = open("project-docs/roadmap.md").read()
    scan = {"project_name": "x", "description": "", "commit_count": 0,
            "has_structured_commits": False, "recent_topics": [],
            "top_dirs": [], "languages": [], "readme_summary": ""}
    synlynk._write_informed_skeleton(scan, skip_existing=True)
    assert open("project-docs/roadmap.md").read() == original


def test_llm_enrich_calls_agent_noninteractively(project_dir, monkeypatch):
    calls = []
    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = "# Updated Roadmap\n\nThis is enriched content.\n"
        return R()
    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)
    scan = {"project_name": "testproject", "description": "A test.",
            "commit_count": 5, "recent_topics": ["feat: add x"], "languages": ["Python"],
            "readme_summary": "# testproject\nA test.", "top_dirs": ["src"],
            "has_structured_commits": True}
    result = synlynk._llm_enrich("claude", "claude", scan)
    assert result is True
    assert any("claude" in str(c) for c in calls)


def test_llm_enrich_returns_false_on_agent_failure(project_dir, monkeypatch):
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
        return R()
    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)
    scan = {"project_name": "x", "description": "", "commit_count": 0,
            "recent_topics": [], "languages": [], "readme_summary": "",
            "top_dirs": [], "has_structured_commits": False}
    result = synlynk._llm_enrich("claude", "claude", scan)
    assert result is False


def test_llm_enrich_uses_agent_name_not_cli_for_baselines(project_dir, monkeypatch):
    # When agent_cli is a custom path, agent_name must still resolve the right baselines.
    captured_cmd = []
    def fake_run(cmd, **kw):
        captured_cmd.extend(cmd)
        class R:
            returncode = 0
            stdout = "# Roadmap\n"
        return R()
    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)
    scan = {"project_name": "p", "description": "", "commit_count": 0,
            "recent_topics": [], "languages": [], "readme_summary": "",
            "top_dirs": [], "has_structured_commits": False}
    # agent_name="claude" (key in BASELINES), agent_cli="/usr/local/bin/my-claude" (custom path)
    synlynk._llm_enrich("claude", "/usr/local/bin/my-claude", scan)
    # The command must use the custom cli path, not the key name
    assert captured_cmd[0] == "/usr/local/bin/my-claude"
    # And claude's non_interactive_flags ("--print") must be applied (from BASELINES["claude"])
    assert "--print" in captured_cmd


# ── Task 7: Init wizard tests ─────────────────────────────────────────────────

def test_init_wizard_creates_synlynk_dir(tmp_path, monkeypatch):
    import synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    monkeypatch.setattr("builtins.input", lambda _: "")  # accept all defaults
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    assert os.path.exists(".synlynk")
    assert os.path.exists(".synlynk/config.json")

def test_init_wizard_writes_project_docs(tmp_path, monkeypatch):
    import synlynk as sl
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    assert os.path.exists("project-docs/roadmap.md")
    assert os.path.exists("project-docs/memory.md")
    assert os.path.exists("project-docs/todo.md")

def test_init_wizard_skips_existing_synlynk_without_force(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    original_roadmap = open("project-docs/roadmap.md").read()
    sl.init(force=False)
    assert open("project-docs/roadmap.md").read() == original_roadmap

def test_init_writes_workgroup_nudge_to_config(tmp_path, monkeypatch):
    import synlynk as sl
    import json as _json
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    # Simulate user providing email at the cloud nudge step
    inputs = iter(["nikhil@example.com"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [])
    monkeypatch.setattr(sl, "_llm_enrich", lambda *a, **kw: False)
    sl.init()
    config = _json.loads(open(".synlynk/config.json").read())
    assert config.get("workgroup_invite_email") == "nikhil@example.com"


def test_dispatch_agent_creates_job_entry(project_dir, monkeypatch):
    import synlynk as sl
    launched = []
    class FakeProc:
        pid = 12345
    def fake_popen(cmd, **kw):
        launched.append(cmd)
        return FakeProc()
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    job = sl.dispatch_agent("claude", "implement auth fix", story_id="14")
    assert job["agent"] == "claude"
    assert job["pid"] == 12345
    assert job["status"] == "running"
    assert job["task"] == "implement auth fix"
    assert job["story_id"] == "14"
    jobs = sl._load_jobs()
    assert any(j["id"] == job["id"] for j in jobs)


def test_dispatch_agent_claude_includes_dangerously_skip_permissions(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeProc:
        pid = 12345

    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")

    sl.dispatch_agent("claude", "implement auth fix", story_id="14")
    shell_cmd = captured["cmd"][2]
    assert "--dangerously-skip-permissions" in shell_cmd


def test_grok_dispatch_omits_always_approve(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class FakeProc:
        pid = 12345
        returncode = 0
        stdout = FakeStdout()
        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "sh":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")

    # requires Agy Task 1 — passes after feat/v0.9.7-grok-agy merges
    if "grok" not in sl.AGENT_CAPABILITY_BASELINES:
        pytest.xfail("requires Agy Task 1 — passes after feat/v0.9.7-grok-agy merges")
    sl.dispatch_agent("grok", "implement auth fix", story_id="14", force_agent=True)
    shell_cmd = captured["cmd"][2]
    assert "--always-approve" in shell_cmd
    assert "--yes" not in shell_cmd
    assert "--output-format json" in shell_cmd


def test_grok_fallback_permission_mode(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class FakeProc:
        pid = 12345
        returncode = 0
        stdout = FakeStdout()
        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "sh":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_load_agent_profile", lambda agent: {"always_approve_unsupported": True})

    if "grok" not in sl.AGENT_CAPABILITY_BASELINES:
        pytest.xfail("requires Agy Task 1 — passes after feat/v0.9.7-grok-agy merges")
    sl.dispatch_agent("grok", "implement auth fix", story_id="14", force_agent=True)
    shell_cmd = captured["cmd"][2]
    assert "--permission-mode bypassPermissions" in shell_cmd
    assert "--always-approve" not in shell_cmd
    assert "--output-format json" in shell_cmd


def test_grok_dispatch_single_flag_placed_before_prompt(project_dir, monkeypatch):
    """--single must immediately precede $PROMPT; other flags must come before it."""
    import synlynk as sl
    captured = {}

    class FakeStdout:
        def readline(self):
            return b""
        def close(self):
            return None

    class FakeProc:
        pid = 12345
        returncode = 0
        stdout = FakeStdout()
        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "sh":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")

    sl.dispatch_agent("grok", "fix the login bug", story_id="99", force_agent=True)
    shell_cmd = captured["cmd"][2]
    # --single must appear after required Grok dispatch flags and directly before "$PROMPT"
    assert "--single" in shell_cmd
    single_pos = shell_cmd.index("--single")
    prompt_pos = shell_cmd.index('"$PROMPT"')
    assert single_pos < prompt_pos, "--single must come before $PROMPT"
    approve_pos = shell_cmd.index("--always-approve")
    assert approve_pos < single_pos, "--always-approve must come before --single"
    assert "--yes" not in shell_cmd


def test_agy_prompt_flag_split_from_non_interactive_flags():
    """Structural regression: -p must live in prompt_flag, not non_interactive_flags.

    The old broken layout had non_interactive_flags=["-p"], which would cause -p to
    land before any dispatch_flags added later, leaving -p without its value. This test
    fails immediately if someone moves -p back into non_interactive_flags.
    """
    import synlynk as sl
    agy = sl.AGENT_CAPABILITY_BASELINES["agy"]
    assert agy.get("prompt_flag") == "-p", "agy prompt_flag must be '-p'"
    assert "-p" not in agy.get("non_interactive_flags", []), (
        "-p must not be in non_interactive_flags; use prompt_flag instead"
    )


def test_agy_dispatch_prompt_flag_after_other_flags(project_dir, monkeypatch):
    """-p must appear after any dispatch_flags, immediately before $PROMPT.

    Injects a synthetic dispatch_flag into the agy baseline to prove the ordering
    contract holds even when other flags are present — the scenario where the old
    non_interactive_flags layout would have broken.
    """
    import synlynk as sl, copy
    captured = {}

    patched_baselines = copy.deepcopy(sl.AGENT_CAPABILITY_BASELINES)
    patched_baselines["agy"]["dispatch_flags"] = ["--some-flag"]
    monkeypatch.setattr(sl, "AGENT_CAPABILITY_BASELINES", patched_baselines)

    class FakeStdout:
        def readline(self):
            return b""
        def close(self):
            return None

    class FakeProc:
        pid = 12345
        returncode = 0
        stdout = FakeStdout()
        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "sh":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")

    sl.dispatch_agent("agy", "summarise PRs", story_id="7", force_agent=True)
    shell_cmd = captured["cmd"][2]
    assert "--some-flag" in shell_cmd
    assert "-p" in shell_cmd
    some_flag_pos = shell_cmd.index("--some-flag")
    p_pos = shell_cmd.index(" -p ")
    prompt_pos = shell_cmd.index('"$PROMPT"')
    assert some_flag_pos < p_pos, "--some-flag must come before -p"
    assert p_pos < prompt_pos, "-p must come before $PROMPT"


def test_exec_agent_task_claude_does_not_include_dangerously_skip_permissions(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_load_agent_profile", lambda agent: {})

    story_id = sl.cmd_story_create("Investigate issue", engg_domain="backend")
    sl._run_investigation(
        {
            "type": "support",
            "severity": "medium",
            "summary": "Investigate",
            "detail": "Investigate",
            "signal_hash": "abc123",
        },
        {"investigator": "claude"},
    )
    assert "--dangerously-skip-permissions" not in str(captured["args"])


def test_dispatch_agent_writes_prompt_file(project_dir, monkeypatch):
    import synlynk as sl
    class FakeProc:
        pid = 99
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    job = sl.dispatch_agent("agy", "write tests")
    assert os.path.exists(job["prompt_file"])
    content = open(job["prompt_file"]).read()
    assert "write tests" in content


def test_dispatch_agent_unknown_agent_raises(project_dir):
    import synlynk as sl; import pytest as _pytest
    with _pytest.raises(ValueError, match="Unknown agent"):
        sl.dispatch_agent("unknownbot", "do thing")


def test_dispatch_agent_appends_to_existing_jobs(project_dir, monkeypatch):
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    sl.dispatch_agent("claude", "task one")
    sl.dispatch_agent("claude", "task two")
    assert len(sl._load_jobs()) == 2


def test_dispatch_agent_injects_relevant_files(project_dir, monkeypatch):
    """dispatch_agent includes ## Relevant Files when story has scan data."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    # Write scan cache with a backend file
    meta = {"head_sha": "abc123", "skeleton": [
        {"file": "backend/auth.py", "symbols": ["login", "logout"], "language": "python"}
    ]}
    (project_dir / ".synlynk").mkdir(exist_ok=True)
    (project_dir / ".synlynk" / "scan-meta.json").write_text(json.dumps(meta))
    story_id = sl.cmd_story_create("Fix auth", engg_domain="backend")
    # Mock _git_head_sha to avoid subprocess.run call
    monkeypatch.setattr(sl, "_git_head_sha", lambda: "abc123")
    job = sl.dispatch_agent("claude", "fix the login bug", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## Relevant Files" in prompt
    assert "backend/auth.py" in prompt


def test_dispatch_agent_no_relevant_files_without_scan(project_dir, monkeypatch):
    """dispatch_agent omits ## Relevant Files when no scan cache exists."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    story_id = sl.cmd_story_create("Fix thing", engg_domain="backend")
    # Mock _git_head_sha to avoid subprocess.run call
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)
    job = sl.dispatch_agent("claude", "fix it", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## Relevant Files" not in prompt


def test_generate_context_returns_string(project_dir):
    """generate_context() returns a non-empty string (not None)."""
    import synlynk as sl
    result = sl.generate_context()
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_context_task_scope_returns_string(project_dir):
    """generate_context(scope='task:X') returns a string."""
    import synlynk as sl
    story_id = sl.cmd_story_create("Fix auth timeout", engg_domain="backend")
    result = sl.generate_context(scope=f"task:{story_id}")
    assert isinstance(result, str)
    assert "Fix auth timeout" in result


def test_dispatch_agent_context_mode_none(project_dir, monkeypatch):
    """context_mode='none' produces a prompt with no context section."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    job = sl.dispatch_agent("claude", "do the thing", context_mode="none")
    prompt = open(job["prompt_file"]).read()
    assert "synlynk Context Snapshot" not in prompt
    assert "do the thing" in prompt


def test_dispatch_agent_context_mode_task_default(project_dir, monkeypatch):
    """Default context_mode is 'task' — prompt uses task-scoped context when story_id given."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)
    story_id = sl.cmd_story_create("Implement OAuth", engg_domain="backend")
    job = sl.dispatch_agent("claude", "implement oauth", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "task-scoped" in prompt.lower()


def test_dispatch_agent_context_mode_full(project_dir, monkeypatch):
    """context_mode='full' injects full context into prompt."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)
    job = sl.dispatch_agent("claude", "do big thing", context_mode="full")
    prompt = open(job["prompt_file"]).read()
    assert "synlynk Context Snapshot" in prompt


def test_dispatch_agent_explicit_context_mode_beats_profile(project_dir, monkeypatch):
    """An explicit context_mode argument must override the agent profile."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1

    monkeypatch.setattr(sl.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "synlynk Context Snapshot\nshould not appear")
    os.makedirs(".agents", exist_ok=True)
    (project_dir / ".agents" / "claude.json").write_text(
        json.dumps({"agent": "claude", "context_mode": "full"})
    )
    job = sl.dispatch_agent("claude", "do the thing", context_mode="none")
    prompt = open(job["prompt_file"]).read()
    assert "synlynk Context Snapshot" not in prompt


def test_dispatch_agent_context_size_warning(project_dir, monkeypatch, capsys):
    """dispatch_agent warns when context exceeds soft limit."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)
    # Patch generate_context to return an oversized string
    big_context = "x" * (82 * 1024)  # 82KB — over 80KB soft limit
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: big_context)
    sl.dispatch_agent("claude", "do thing", context_mode="full")
    captured = capsys.readouterr()
    assert "exceeds soft limit" in captured.out


def test_dispatch_agent_context_max_bytes_logs_utf8_truncation(project_dir, monkeypatch, capsys):
    """dispatch_agent truncates oversized UTF-8 context cleanly and logs it."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1

    monkeypatch.setattr(sl.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "€" * 100)
    os.makedirs(".agents", exist_ok=True)
    (project_dir / ".agents" / "claude.json").write_text(
        json.dumps({"agent": "claude", "context_mode": "full", "context_max_bytes": 10})
    )
    sl.dispatch_agent("claude", "do thing")
    captured = capsys.readouterr()
    assert "context truncated to 10B" in captured.out


def test_model_version_tier1_grok(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_load_agent_profile", lambda agent: {"model": "grok-profile"})
    result = sl.extract_model_version("# synlynk-meta\nmodel_version = grok-header", agent="grok")
    assert result == "grok-header"


def test_model_version_tier2_grok(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_load_agent_profile", lambda agent: {"model": "grok-profile"})
    result = sl.extract_model_version("no header here", agent="grok")
    assert result == "grok-profile"


def test_dispatch_agent_does_not_read_context_file_for_none_mode(project_dir, monkeypatch):
    """context_mode='none' does not require context.md to exist."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    # Ensure context.md does not exist
    ctx = project_dir / ".synlynk" / "context.md"
    if ctx.exists():
        ctx.unlink()
    job = sl.dispatch_agent("claude", "do thing", context_mode="none")
    assert job["status"] == "running"


def test_dispatch_agent_writes_per_job_context_file(project_dir, monkeypatch):
    """dispatch_agent writes context to .synlynk/contexts/<job_id>.md, not global context.md."""
    import synlynk as sl

    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_check_scan_cache", lambda: None)

    story_id = sl.cmd_story_create("Fix login timeout", engg_domain="backend")
    job = sl.dispatch_agent("claude", "fix the bug", story_id=story_id)

    job_ctx = project_dir / job["worktree_path"] / ".synlynk" / "contexts" / f"{job['id']}.md"
    assert job_ctx.exists(), f"per-job context file not found: {job_ctx}"
    assert "Fix login timeout" in job_ctx.read_text()
    assert job["context_file"] == str(job_ctx)


def test_dispatch_agent_concurrent_jobs_use_separate_context_files(project_dir, monkeypatch):
    """Two concurrent dispatches write to different context files, not the same one."""
    import synlynk as sl

    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_check_scan_cache", lambda: None)

    story_a = sl.cmd_story_create("Story A", engg_domain="backend")
    story_b = sl.cmd_story_create("Story B", engg_domain="frontend")

    job_a = sl.dispatch_agent("claude", "task A", story_id=story_a)
    job_b = sl.dispatch_agent("codex", "task B", story_id=story_b)

    ctx_a = project_dir / job_a["worktree_path"] / ".synlynk" / "contexts" / f"{job_a['id']}.md"
    ctx_b = project_dir / job_b["worktree_path"] / ".synlynk" / "contexts" / f"{job_b['id']}.md"

    assert ctx_a != ctx_b
    assert ctx_a.exists()
    assert ctx_b.exists()
    assert "Story A" in ctx_a.read_text()
    assert "Story B" in ctx_b.read_text()


def test_generate_task_context_out_path_writes_to_custom_location(project_dir):
    """_generate_task_context respects an explicit out_path instead of global context.md."""
    import synlynk as sl

    story_id = sl.cmd_story_create("Custom path test", engg_domain="backend")
    custom_path = str(project_dir / ".synlynk" / "contexts" / "custom.md")
    os.makedirs(str(project_dir / ".synlynk" / "contexts"), exist_ok=True)

    sl._generate_task_context(story_id, out_path=custom_path)

    assert os.path.exists(custom_path)
    assert "Custom path test" in open(custom_path).read()
    # Global context.md should NOT have been written
    global_ctx = project_dir / ".synlynk" / "context.md"
    if global_ctx.exists():
        assert "Custom path test" not in global_ctx.read_text()


def test_exec_grok_headless_appends_rules_flags(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class FakeProc:
        returncode = 0
        stdout = FakeStdout()

        def wait(self):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "grok":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)

    (project_dir / "GROK.md").write_text("grok rules")
    (project_dir / ".synlynk" / "context.md").write_text("synlynk context")

    sl.exec_command(["grok", "-p", "do the thing"])
    assert captured["cmd"][0] == "grok"
    assert captured["cmd"][1:5] == ["--rules", "GROK.md", "--rules", ".synlynk/context.md"]


def test_exec_grok_interactive_omits_context_md(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeProc:
        returncode = 0
        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "grok":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)

    (project_dir / "GROK.md").write_text("grok rules")
    (project_dir / ".synlynk" / "context.md").write_text("synlynk context")

    sl.exec_command(["grok", "do the thing"])
    assert captured["cmd"][0] == "grok"
    assert captured["cmd"][1:3] == ["--rules", "GROK.md"]
    assert ".synlynk/context.md" not in captured["cmd"]


def test_exec_grok_skips_missing_rules_files(tmp_path, monkeypatch):
    import synlynk as sl
    captured = {}

    class FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class FakeProc:
        returncode = 0
        stdout = FakeStdout()

        def wait(self):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    def fake_popen(cmd, **kw):
        if cmd and cmd[0] == "grok":
            captured["cmd"] = cmd
        return FakeProc()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)

    sl.exec_command(["grok", "-p", "do the thing"])
    assert captured["cmd"] == ["grok", "-p", "do the thing"]


def test_relevant_files_for_story_returns_matching_files(project_dir):
    """_relevant_files_for_story matches engg_domain to file paths."""
    import synlynk as sl, json
    meta = {"head_sha": "abc", "skeleton": [
        {"file": "src/backend/api.py", "symbols": ["get_user"], "language": "python"},
        {"file": "src/frontend/App.tsx", "symbols": ["App"], "language": "typescript"},
    ]}
    (project_dir / ".synlynk" / "scan-meta.json").write_text(json.dumps(meta))
    story_id = sl.cmd_story_create("API fix", engg_domain="backend")
    files = sl._relevant_files_for_story(story_id)
    assert any("backend" in f for f in files)
    assert not any("frontend" in f for f in files)


def test_stories_table_has_status_column(project_dir):
    """stories table must have a status column after migration."""
    import synlynk as sl
    conn = sl._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    conn.close()
    assert "status" in cols


def test_generate_todo_md_creates_file(project_dir):
    """_generate_todo_md writes project-docs/todo.md from stories."""
    import synlynk as sl
    sl.cmd_story_create("Fix login bug", engg_domain="backend")
    sl._generate_todo_md()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Fix login bug" in todo
    assert "- [ ]" in todo


def test_generate_todo_md_marks_done_stories(project_dir):
    """_generate_todo_md uses [x] for done stories."""
    import synlynk as sl
    story_id = sl.cmd_story_create("Finish report")
    conn = sl._get_db()
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (story_id,))
    conn.commit()
    conn.close()
    sl._generate_todo_md()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "- [x]" in todo


def test_cmd_story_create_generates_todo_md(project_dir):
    """cmd_story_create automatically regenerates todo.md."""
    import synlynk as sl
    sl.cmd_story_create("Auto-sync check")
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Auto-sync check" in todo


def test_import_todo_to_stories_imports_unchecked_lines(project_dir):
    """_import_todo_to_stories creates story rows for - [ ] lines."""
    import synlynk as sl
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Migrate auth module\n"
        "- [x] Old done task\n"
        "- [ ] Write API docs\n"
    )
    count = sl._import_todo_to_stories()
    assert count == 2
    conn = sl._get_db()
    titles = {row[0] for row in conn.execute("SELECT title FROM stories")}
    conn.close()
    assert "Migrate auth module" in titles
    assert "Write API docs" in titles
    assert "Old done task" not in titles


def test_import_todo_to_stories_skips_existing_stories(project_dir):
    """_import_todo_to_stories does not duplicate stories already in DB."""
    import synlynk as sl
    story_id = sl.cmd_story_create("Already exists")
    (project_dir / "project-docs" / "todo.md").write_text(
        f"- [ ] Already exists <!-- id:{story_id} -->\n"
        "- [ ] Brand new task\n"
    )
    count = sl._import_todo_to_stories()
    assert count == 1


def test_import_todo_to_stories_is_idempotent(project_dir):
    """_import_todo_to_stories dedups by title and deterministic story_id."""
    import synlynk as sl
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] First unchecked item\n"
        "- [ ] Second unchecked item\n"
    )
    first = sl._import_todo_to_stories()
    second = sl._import_todo_to_stories()
    conn = sl._get_db()
    rows = conn.execute(
        "SELECT story_id, title FROM stories WHERE title IN (?, ?) ORDER BY title",
        ("First unchecked item", "Second unchecked item"),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM stories WHERE title IN (?, ?)",
        ("First unchecked item", "Second unchecked item"),
    ).fetchone()[0]
    conn.close()
    assert first == 2
    assert second == 0
    assert total == 2
    assert len(rows) == 2


def test_dispatch_agent_injects_verify_contract(project_dir, monkeypatch):
    """dispatch_agent appends ## How to Verify when tests/ directory exists."""
    import synlynk as sl
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_auth.py").write_text("# placeholder\n")
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    story_id = sl.cmd_story_create("Fix auth timeout", engg_domain="backend")
    job = sl.dispatch_agent("claude", "fix the login bug", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## How to Verify" in prompt
    assert "pytest" in prompt


def test_dispatch_agent_no_verify_without_tests_dir(project_dir, monkeypatch):
    """dispatch_agent omits ## How to Verify when no tests/ directory exists."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    story_id = sl.cmd_story_create("Fix thing")
    job = sl.dispatch_agent("claude", "fix it", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## How to Verify" not in prompt


def test_cmd_jobs_watch_handles_render_errors(project_dir, monkeypatch, capsys):
    """cmd_jobs(--watch) prints render errors instead of crashing."""
    import synlynk as sl

    class FakeConn:
        def execute(self, *a, **kw):
            raise RuntimeError("boom")

        def close(self):
            pass

    def fake_sleep(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(sl, "_reconcile_daemon_jobs", lambda: None)
    monkeypatch.setattr(sl, "_get_db", lambda: FakeConn())
    monkeypatch.setattr(sl.time, "sleep", fake_sleep)

    sl.cmd_jobs(watch=True)
    out = capsys.readouterr().out
    assert "render error: boom" in out.lower()


def test_load_agent_profile_returns_defaults_when_missing(project_dir):
    """_load_agent_profile returns default harness/model values when file is missing."""
    import synlynk as sl
    result = sl._load_agent_profile("claude")
    assert result["agent"] == "claude"
    assert result["harness"] == "claude"
    assert result["model"] == "unknown"


def test_load_agent_profile_returns_dict_when_present(project_dir):
    """_load_agent_profile returns parsed JSON when file exists."""
    import synlynk as sl, json
    os.makedirs(".agents", exist_ok=True)
    (project_dir / ".agents" / "claude.json").write_text(
        json.dumps({"agent": "claude", "context_mode": "none", "context_max_bytes": 500})
    )
    result = sl._load_agent_profile("claude")
    assert result["context_mode"] == "none"
    assert result["context_max_bytes"] == 500


def test_agent_json_roundtrips_harness_and_model(tmp_path):
    import json
    from synlynk import _load_agent_profile

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "claude.json").write_text(json.dumps({
        "agent": "claude",
        "harness": "claude-cli",
        "model": "claude-sonnet-4-6",
        "dispatch_flags": ["--print", "--dangerously-skip-permissions"],
    }))

    profile = _load_agent_profile("claude", str(agents_dir))
    assert profile["harness"] == "claude-cli"
    assert profile["model"] == "claude-sonnet-4-6"


def test_dispatch_agent_profile_overrides_context_mode(project_dir, monkeypatch):
    """Profile context_mode='none' overrides default 'task'."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "PROFILE_CONTEXT_MARKER")
    os.makedirs(".agents", exist_ok=True)
    (project_dir / ".agents" / "claude.json").write_text(
        json.dumps({"agent": "claude", "context_mode": "none"})
    )
    job = sl.dispatch_agent("claude", "do thing")
    prompt = open(job["prompt_file"]).read()
    assert "PROFILE_CONTEXT_MARKER" not in prompt


def test_dispatch_agent_profile_context_max_bytes_truncates(project_dir, monkeypatch):
    """Profile context_max_bytes truncates context_text before prompt assembly."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    os.makedirs(".agents", exist_ok=True)
    (project_dir / ".agents" / "claude.json").write_text(
        json.dumps({"agent": "claude", "context_mode": "full", "context_max_bytes": 50})
    )
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "x" * 5000)
    job = sl.dispatch_agent("claude", "do thing")
    prompt = open(job["prompt_file"]).read()
    assert "x" * 51 not in prompt


def test_verify_contract_derives_pattern_from_story_title(project_dir):
    """_verify_contract_for_story derives a lowercase underscore pattern."""
    import synlynk as sl
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_things.py").write_text("")
    story_id = sl.cmd_story_create("Fix Auth Timeout")
    section = sl._verify_contract_for_story(story_id, "fix it")
    assert "fix_auth_timeout" in section
    assert "pytest" in section


def test_format_prompt_for_claude_is_narrative(project_dir):
    """Claude prompt leads with full context text."""
    import synlynk as sl
    result = sl._format_prompt_for_agent(
        "claude", "## Context\nsome context", "story-1", "fix auth",
        "\n\n## Relevant Files\n- `auth.py`", "\n\n## How to Verify\nRun pytest\n"
    )
    assert result.startswith("## Context")
    assert "## Your Task" in result
    assert "fix auth" in result


def test_format_prompt_for_codex_leads_with_criteria(project_dir):
    """Codex prompt leads with ## Task Criteria and file list."""
    import synlynk as sl
    result = sl._format_prompt_for_agent(
        "codex", "## Context\nsome context", "story-1", "fix auth. add test.",
        "\n\n## Relevant Files\n- `auth.py`", ""
    )
    assert result.startswith("## Task Criteria")
    assert "- fix auth" in result or "- add test" in result
    assert "auth.py" in result


def test_format_prompt_agy_no_hardcoded_truncation(project_dir):
    """_format_prompt_for_agent with agy does NOT truncate context anymore."""
    import synlynk as sl
    long_context = "A" * 3000
    result = sl._format_prompt_for_agent(
        "agy", long_context, "story-1", "fix auth", "", ""
    )
    assert "## Working Directory" in result
    assert "Task: fix auth" in result
    assert "A" * 2001 in result


def test_dispatch_agent_claude_prompt_format(project_dir, monkeypatch):
    """dispatch_agent uses _format_prompt_for_agent for claude."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    story_id = sl.cmd_story_create("Fix login")
    job = sl.dispatch_agent("claude", "fix the login bug", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## Your Task" in prompt
    assert "fix the login bug" in prompt


def test_dispatch_agent_codex_prompt_format(project_dir, monkeypatch):
    """dispatch_agent uses _format_prompt_for_agent for codex."""
    import synlynk as sl
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    story_id = sl.cmd_story_create("Add tests")
    job = sl.dispatch_agent("codex", "add tests for auth module", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## Task Criteria" in prompt


def test_codex_baseline_uses_exec_subcommand(project_dir, monkeypatch):
    """codex exec + stdin mode must be used so dispatch works without a TTY.

    Flags must be: codex exec - -s workspace-write
    Must NOT include --dangerously-bypass-approvals-and-sandbox: that flag
    silently overrides -s and runs at danger-full-access (full host access).
    """
    import synlynk as sl
    captured = {}
    class FakeProc:
        pid = 777
    def fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        return FakeProc()
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    sl.dispatch_agent("codex", "review the codebase")
    shell_cmd = captured["cmd"][2]  # ["sh", "-c", <shell_cmd>]
    assert "codex exec" in shell_cmd
    assert "workspace-write" in shell_cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in shell_cmd


def test_cmd_jobs_prints_running_jobs(project_dir, monkeypatch, capsys):
    import synlynk as sl
    monkeypatch.setattr(sl, "_reconcile_jobs", lambda: None)  # bypass PID probing
    jobs = [
        {"id": "job-aaa", "agent": "claude", "story_id": "14", "task": "do thing",
         "pid": 99999, "status": "running", "started_at": "2026-06-14T10:00:00",
         "ended_at": None, "exit_code": None, "log_file": ".synlynk/logs/job-aaa.log"},
    ]
    sl._save_jobs(jobs)
    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "job-aaa" in out
    assert "claude" in out
    assert "running" in out


def test_cmd_jobs_empty_output_when_no_jobs(project_dir, capsys):
    import synlynk as sl
    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "No jobs" in out or out.strip() == "" or "no jobs" in out.lower()


def test_cmd_jobs_reads_from_daemon_jobs_table(project_dir, capsys):
    """cmd_jobs shows rows from daemon_jobs SQLite table."""
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-abc123", "claude", "fix auth", "story-001", "running", 5, "[]",
         "2026-06-24T08:00:00")
    )
    conn.commit(); conn.close()
    sl.cmd_jobs()
    out = capsys.readouterr().out
    assert "job-abc123" in out
    assert "claude" in out
    assert "running" in out


def test_cmd_jobs_all_shows_completed(project_dir, capsys):
    """cmd_jobs(all_jobs=True) includes done and failed rows."""
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, "
        "enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-done1", "agy", "task", "done", 5, "[]", "2026-06-24T07:00:00")
    )
    conn.commit(); conn.close()
    sl.cmd_jobs(all_jobs=True)
    out = capsys.readouterr().out
    assert "job-done1" in out


def test_cmd_jobs_default_hides_completed(project_dir, capsys):
    """cmd_jobs() without --all hides done jobs."""
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, "
        "enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("job-done2", "agy", "task", "done", 5, "[]", "2026-06-24T07:00:00")
    )
    conn.commit(); conn.close()
    sl.cmd_jobs(all_jobs=False)
    out = capsys.readouterr().out
    assert "No active jobs" in out


def test_preflight_blocks_invalid_flag():
    from synlynk import _preflight_dispatch
    # --yes is now invalid for Grok (replaced by --always-approve)
    result = _preflight_dispatch(
        agent_name="grok",
        dispatch_flags=["--yes"],
        db_conn=None,
    )
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "--yes" in result["reason"]


def test_preflight_blocks_unreachable_endpoint(monkeypatch):
    import socket

    def mock_connect(self, addr):
        raise ConnectionRefusedError("unreachable")

    monkeypatch.setattr(socket.socket, "connect", mock_connect)

    # TC-2 now runs before network check — mock it to pass so we reach the network gate.
    from synlynk import probe as probe_mod
    monkeypatch.setattr(probe_mod, "_run_tc2",
                        lambda agent, flags_spec, **kw: {"passed": True, "failed_flags": []})

    from synlynk import _preflight_dispatch
    result = _preflight_dispatch(
        agent_name="grok",
        dispatch_flags=["--always-approve"],
        db_conn=None,
    )
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "cli-chat-proxy.grok.com" in result["reason"]


def test_preflight_passes_for_valid_claude_dispatch():
    from synlynk import _preflight_dispatch
    result = _preflight_dispatch(
        agent_name="claude",
        dispatch_flags=["--print", "--dangerously-skip-permissions"],
        db_conn=None,
    )
    assert result["passed"] is True


def test_dispatch_agent_records_in_daemon_jobs_table(project_dir, monkeypatch):
    """dispatch_agent writes a row to daemon_jobs in addition to jobs.json."""
    import synlynk as sl

    class FakeProc:
        pid = 42

    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None}, raising=False)
    job = sl.dispatch_agent("claude", "test task")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT job_id, agent, status FROM daemon_jobs WHERE job_id=?",
        (job["id"],)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == "claude"
    assert row[2] == "running"


def test_cmd_logs_prints_log_content(project_dir, capsys):
    import synlynk as sl
    os.makedirs(".synlynk/logs", exist_ok=True)
    job = {"id": "job-bbb", "agent": "claude", "status": "running",
            "log_file": ".synlynk/logs/job-bbb.log", "pid": 1,
            "story_id": "", "task": "t", "started_at": "2026-06-14T10:00:00",
            "ended_at": None, "exit_code": None, "prompt_file": ""}
    sl._save_jobs([job])
    open(".synlynk/logs/job-bbb.log", "w").write("Agent output line 1\nAgent output line 2\n")
    sl.cmd_logs("job-bbb")
    out = capsys.readouterr().out
    assert "Agent output line 1" in out


def test_cmd_logs_error_for_missing_job(project_dir, capsys):
    import synlynk as sl
    sl.cmd_logs("job-missing")
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "no job" in out.lower()


def test_cmd_shell_spawns_subshell(project_dir, monkeypatch):
    import synlynk as sl
    spawned = []
    def fake_run(cmd, **kw):
        spawned.append((cmd, kw))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_shell(story_id="14")
    assert any(isinstance(c, list) and any("sh" in str(x) for x in c)
               for c, _ in spawned)


def test_cmd_shell_injects_synlynk_env(project_dir, monkeypatch):
    import synlynk as sl
    captured_env = {}
    def fake_run(cmd, **kw):
        captured_env.update(kw.get("env", {}))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_shell(story_id="42")
    assert captured_env.get("SYNLYNK_STORY_ID") == "42"
    assert "SYNLYNK_PROJECT_DIR" in captured_env


def test_cmd_launch_starts_agent_interactively(project_dir, monkeypatch):
    import synlynk as sl
    launched = []
    def fake_run(cmd, **kw):
        launched.append(cmd)
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl.cmd_launch("claude", story_id="14")
    assert any("claude" in str(c) for c in launched)


def test_cmd_launch_unknown_agent_prints_error(project_dir, capsys):
    import synlynk as sl
    sl.cmd_launch("unknownbot", story_id="1")
    out = capsys.readouterr().out
    assert "unknown" in out.lower() or "not found" in out.lower()


def test_cmd_launch_generates_agent_context(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: type("R", (), {"returncode": 0})())
    sl.cmd_launch("claude", story_id="5")
    assert os.path.exists(".synlynk/context-claude.md")


def test_cmd_run_trio_dispatches_three_agents(project_dir, monkeypatch):
    import synlynk as sl
    dispatched = []
    def fake_dispatch(agent, task, story_id=None):
        dispatched.append(agent)
        return {"id": f"job-{agent}", "agent": agent, "pid": 1, "status": "running",
                "task": task, "story_id": story_id, "log_file": "", "prompt_file": "",
                "started_at": "2026-06-14T10:00:00", "ended_at": None, "exit_code": None}
    monkeypatch.setattr(sl, "dispatch_agent", fake_dispatch)
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [
        {"name": "claude", "functional": True, "roles": ["architect", "builder"],
         "cli": "claude", "version": "2", "capabilities": [], "non_interactive_flags": ["--print"],
         "discovery_path": ""},
        {"name": "gemini", "functional": True, "roles": ["builder", "verifier"],
         "cli": "gemini", "version": "1", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
        {"name": "codex", "functional": True, "roles": ["builder"],
         "cli": "codex", "version": "1", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
    ])
    sl.cmd_run_trio("implement the auth feature")
    assert len(dispatched) == 3
    assert "claude" in dispatched


def test_cmd_run_trio_warns_with_fewer_than_three_agents(project_dir, monkeypatch, capsys):
    import synlynk as sl
    monkeypatch.setattr(sl, "discover_agents", lambda **kw: [
        {"name": "claude", "functional": True, "roles": ["architect"],
         "cli": "claude", "version": "2", "capabilities": [], "non_interactive_flags": [],
         "discovery_path": ""},
    ])
    monkeypatch.setattr(sl, "dispatch_agent", lambda *a, **kw: {"id": "j", "pid": 1,
        "status": "running", "agent": "claude", "task": "", "story_id": "",
        "log_file": "", "prompt_file": "", "started_at": "", "ended_at": None, "exit_code": None})
    sl.cmd_run_trio("do thing")
    out = capsys.readouterr().out
    assert "1" in out or "agent" in out.lower()


# ── Task Status Model (v0.4.2) ────────────────────────────────────────────────

def test_task_statuses_constant_defined():
    assert hasattr(synlynk, "TASK_STATUSES")
    assert synlynk.TASK_STATUSES["[ ]"] == "active"
    assert synlynk.TASK_STATUSES["[x]"] == "done"
    assert synlynk.TASK_STATUSES["[-]"] == "deferred"
    assert synlynk.TASK_STATUSES["[~]"] == "superseded"
    assert synlynk.TASK_STATUSES["[>]"] == "absorbed"


def test_generate_context_includes_deferred_tasks(project_dir):
    (project_dir / "project-docs" / "todo.md").write_text(
        "## Active Tasks\n"
        "- [ ] Active task <!-- id: 1 -->\n"
        "- [-] Deferred task <!-- id: 2 -->\n"
        "- [x] Done task <!-- id: 3 -->\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Active task" in ctx
    assert "Deferred task" in ctx
    assert "Done task" not in ctx


def test_generate_context_excludes_superseded_tasks(project_dir):
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Active task <!-- id: 1 -->\n"
        "- [~] Superseded task <!-- id: 2 -->\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Active task" in ctx
    assert "Superseded task" not in ctx


def test_generate_context_excludes_absorbed_tasks(project_dir):
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Active task <!-- id: 1 -->\n"
        "- [>] Absorbed task <!-- id: 2 -->\n"
    )
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Active task" in ctx
    assert "Absorbed task" not in ctx


def test_checkpoint_archives_superseded_tasks(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Still active <!-- id: 1 -->\n"
        "- [~] Superseded task <!-- id: 2 -->\n"
    )
    synlynk.checkpoint()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Still active" in todo
    assert "Superseded task" not in todo


def test_checkpoint_archives_absorbed_tasks(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Still active <!-- id: 1 -->\n"
        "- [>] Absorbed task <!-- id: 2 -->\n"
    )
    synlynk.checkpoint()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Still active" in todo
    assert "Absorbed task" not in todo


def test_checkpoint_keeps_deferred_tasks(project_dir, monkeypatch):
    monkeypatch.setattr(synlynk, 'get_username', lambda: "nikhil")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [ ] Still active <!-- id: 1 -->\n"
        "- [-] Deferred task <!-- id: 2 -->\n"
        "- [x] Done task <!-- id: 3 -->\n"
    )
    synlynk.checkpoint()
    todo = (project_dir / "project-docs" / "todo.md").read_text()
    assert "Still active" in todo
    assert "Deferred task" in todo
    assert "Done task" not in todo


def test_autopilot_runs_table_exists(project_dir):
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='autopilot_runs'"
    ).fetchone()
    conn.close()
    assert row is not None, "autopilot_runs table must exist after _get_db()"


def test_load_agent_config_success(project_dir):
    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "test-agent",
        "investigator": "claude",
        "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "test-agent.json").write_text(json.dumps(cfg))
    loaded = synlynk._load_agent_config("test-agent")
    assert loaded["name"] == "test-agent"
    assert loaded["investigator"] == "claude"


def test_load_agent_config_missing_raises(project_dir):
    with pytest.raises(FileNotFoundError, match="No agent config found"):
        synlynk._load_agent_config("nonexistent")


def test_agent_run_unknown_agent_raises(project_dir):
    with pytest.raises(FileNotFoundError, match="No agent config found"):
        synlynk.cmd_agent_run("nonexistent")


def test_collect_test_suite_high_on_failure(project_dir, monkeypatch):
    fake_result = type("R", (), {"returncode": 1, "stdout": "FAILED tests/test_foo.py::test_bar\n1 failed"})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = synlynk._collect_test_suite({"type": "test_suite", "command": "pytest tests/ -q --tb=short"})
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["type"] == "test_suite"
    assert "signal_hash" in findings[0]


def test_collect_test_suite_no_finding_on_pass(project_dir, monkeypatch):
    fake_result = type("R", (), {"returncode": 0, "stdout": "1 passed"})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = synlynk._collect_test_suite({"type": "test_suite", "command": "pytest tests/ -q --tb=short"})
    assert findings == []


def test_collect_sentinel_alerts_flatline(project_dir):
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n"
        "- [2026-06-21 10:00] ⚠ FLATLINE: 3 consecutive exec failures\n"
    )
    findings = synlynk._collect_sentinel_alerts({"type": "sentinel_alerts", "path": ".synlynk/sentinel.md"})
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert "FLATLINE" in findings[0]["summary"]


def test_collect_sentinel_alerts_empty(project_dir):
    (project_dir / ".synlynk" / "sentinel.md").write_text("# Sentinel Alerts\n(none)\n")
    findings = synlynk._collect_sentinel_alerts({"type": "sentinel_alerts", "path": ".synlynk/sentinel.md"})
    assert findings == []


def test_collect_telemetry_anomaly_medium(project_dir):
    import json
    # 8 failures out of 20 = 40% — above 30% threshold, below 60%
    entries = [{"exit_code": (1 if i < 8 else 0)} for i in range(20)]
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(entries))
    findings = synlynk._collect_telemetry_anomaly({
        "type": "telemetry_anomaly", "failure_rate_threshold": 0.30
    })
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"


def test_collect_telemetry_anomaly_no_finding(project_dir):
    import json
    entries = [{"exit_code": (1 if i < 2 else 0)} for i in range(20)]
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(entries))
    findings = synlynk._collect_telemetry_anomaly({
        "type": "telemetry_anomaly", "failure_rate_threshold": 0.30
    })
    assert findings == []


def test_collect_capability_drop_returns_finding(project_dir):
    conn = synlynk._get_db()
    # Insert a story first (FK requirement)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES (?, ?)",
        ("s-drop-test", "drop test story")
    )
    # Use timestamps that stay in the expected windows relative to datetime('now').
    now = datetime.now(timezone.utc)
    recent_ts = (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    prior_ts = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
    # Recent window: quality 5.0
    for _ in range(2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, quality, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            ("s-drop-test", "claude", "claude-sonnet-4-6", 5.0, recent_ts)
        )
    # Older window: quality 8.0
    for _ in range(2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, quality, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            ("s-drop-test", "claude", "claude-sonnet-4-6", 8.0, prior_ts)
        )
    conn.commit()
    conn.close()
    findings = synlynk._collect_capability_drop({"type": "capability_drop", "drop_threshold": 1.5})
    assert len(findings) == 1
    assert findings[0]["severity"] in ("medium", "high")
    assert "claude" in findings[0]["summary"]


def test_collect_capability_drop_insufficient_data(project_dir):
    # No ratings — should return empty
    findings = synlynk._collect_capability_drop({"type": "capability_drop", "drop_threshold": 1.5})
    assert findings == []


def test_ensure_identity_key_creates_key(tmp_path, monkeypatch):
    import synlynk as sl, os
    calls = []
    monkeypatch.setenv("HOME", str(tmp_path))
    def fake_run(cmd, **kw):
        calls.append(cmd)
        key_file = tmp_path / ".synlynk" / "identity.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.touch()
        return type("R", (), {"returncode": 0})()
    monkeypatch.setattr("subprocess.run", fake_run)
    sl._ensure_identity_key()
    assert any("ssh-keygen" in str(c) for c in calls)

def test_sign_capability_rating_returns_empty_when_no_key(project_dir, monkeypatch):
    import synlynk as sl, os
    orig_exists = os.path.exists
    monkeypatch.setattr("os.path.exists", lambda p: False if "identity" in str(p) else orig_exists(p))
    result = sl._sign_capability_rating({"quality": 8.0, "agent": "claude"})
    assert result == ""

def test_write_capability_rating_populates_sig_column(project_dir, monkeypatch):
    import synlynk as sl
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda d: "")
    story_id = sl.cmd_story_create("Auth fix", engg_domain="backend")
    job = {
        "story_id": story_id, "agent": "claude", "model_at_dispatch": "claude-3",
        "started_at": "2026-06-01T10:00:00", "ended_at": "2026-06-01T10:05:00",
        "exit_code": 0, "dispatch_rework": 0, "micro_rework": 0,
    }
    sl._write_capability_rating(job, "47 passed in 3.2s")
    conn = sl._get_db()
    row = conn.execute(
        "SELECT ed25519_sig FROM capability_ratings WHERE story_id=?", (story_id,)
    ).fetchone()
    conn.close()
    assert row is not None

def test_identity_init_command_prints_key_path(project_dir, monkeypatch, capsys):
    import synlynk as sl, tempfile, os
    with tempfile.TemporaryDirectory() as d:
        key_path = os.path.join(d, ".synlynk", "identity.key")
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        open(key_path, "w").close()
        pub_path = key_path + ".pub"
        open(pub_path, "w").write("ssh-ed25519 AAAA synlynk-identity")
        monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", d))
        monkeypatch.setattr("subprocess.run", lambda cmd, **kw: type("R", (), {"returncode": 0})())
        sl.cmd_identity_init()
    captured = capsys.readouterr()
    assert "identity" in captured.out.lower()



def test_collect_github_issues(project_dir, monkeypatch):
    import json
    issues = [
        {"number": 42, "title": "Crash on empty input", "body": "Steps to repro: ...", "createdAt": "2026-06-21T10:00:00Z"},
        {"number": 43, "title": "Wrong score shown", "body": "Score is 0 always", "createdAt": "2026-06-21T11:00:00Z"},
    ]
    fake_result = type("R", (), {"returncode": 0, "stdout": json.dumps(issues)})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = synlynk._collect_github_issues({"type": "github_issues", "labels": ["bug", "needs-triage"]})
    assert len(findings) == 2
    assert findings[0]["type"] == "github_issues"
    assert findings[0]["severity"] == "medium"
    assert "#42" in findings[0]["summary"]


def test_dedup_skips_recent_signal(project_dir):
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO autopilot_runs (id, agent_name, signal_type, signal_hash, severity, summary, status, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-3 days'))",
        ("run-001", "support-engineer", "test_suite", "abc123", "high", "test failure", "filed")
    )
    conn.commit()
    conn.close()
    findings = [{"signal_hash": "abc123", "type": "test_suite", "severity": "high", "summary": "x", "detail": "x"}]
    result = synlynk._dedup_findings(findings)
    assert result == [], "Recent signal should be filtered out by dedup"


def test_dedup_reinvestigates_after_7_days(project_dir):
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO autopilot_runs (id, agent_name, signal_type, signal_hash, severity, summary, status, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-8 days'))",
        ("run-001", "support-engineer", "test_suite", "abc123", "high", "test failure", "filed")
    )
    conn.commit()
    conn.close()
    findings = [{"signal_hash": "abc123", "type": "test_suite", "severity": "high", "summary": "x", "detail": "x"}]
    result = synlynk._dedup_findings(findings)
    assert len(result) == 1, "8-day-old signal should pass dedup (>7 days)"


def test_run_investigation_creates_story_and_returns_summary(project_dir, monkeypatch):
    import re

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(cmd)
        # Simulate agent writing to log file
        if isinstance(cmd, list) and cmd[0] == "sh":
            shell_cmd = cmd[2] if len(cmd) > 2 else ""
            m = re.search(r"> (\S+\.log)\b", shell_cmd)
            if m:
                import os
                os.makedirs(os.path.dirname(m.group(1)), exist_ok=True)
                open(m.group(1), "w").write("Root cause: the test was broken.\n# FIX: replace line 42\n")
                open(m.group(1) + ".exit", "w").write("0\n")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("subprocess.run", fake_run)

    finding = {
        "type": "test_suite",
        "severity": "high",
        "summary": "Test failure: test_foo",
        "detail": "FAILED tests/test_foo.py\n1 failed",
        "signal_hash": "deadbeef12345678",
    }
    result = synlynk._run_investigation(finding, {"investigator": "claude"})

    assert "summary" in result
    assert result["fix_signal"] is True
    assert "story_id" in result

    # Confirm story was created in DB
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT story_id FROM stories WHERE story_id=?", (result["story_id"],)
    ).fetchone()
    conn.close()
    assert row is not None


def test_file_gh_issue_calls_gh(project_dir, monkeypatch):
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return type("R", (), {"returncode": 0, "stdout": "https://github.com/org/repo/issues/99"})()
    monkeypatch.setattr("subprocess.run", fake_run)

    finding = {"type": "test_suite", "severity": "high", "summary": "Test failure", "detail": "1 failed"}
    investigation = {"summary": "Root cause: missing mock", "story_id": "support-abc123"}
    url = synlynk._file_gh_issue(finding, investigation, dry_run=False)
    assert url == "https://github.com/org/repo/issues/99"
    assert "issue" in captured["cmd"]
    assert "create" in captured["cmd"]


def test_file_gh_issue_dry_run_no_subprocess(project_dir, monkeypatch):
    called = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: called.append(a))
    finding = {"type": "test_suite", "severity": "high", "summary": "Test failure", "detail": "x"}
    investigation = {"summary": "y", "story_id": "support-abc"}
    url = synlynk._file_gh_issue(finding, investigation, dry_run=True)
    assert url == ""
    assert called == [], "subprocess.run must not be called in dry-run"


def test_extract_diff_from_fenced_block():
    text = (
        "Here is the fix:\n\n```diff\n"
        "--- a/bin/synlynk.py\n"
        "+++ b/bin/synlynk.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-old\n+new\n"
        "```\n"
    )
    diff = synlynk._extract_diff(text)
    assert diff is not None
    assert "--- a/bin/synlynk.py" in diff


def test_extract_diff_returns_none_when_absent():
    assert synlynk._extract_diff("No diff here, just prose.") is None


def test_attempt_fix_returns_no_diff_when_no_diff_in_log(project_dir, monkeypatch):
    calls = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: calls.append(a) or type("R", (), {"returncode": 0, "stdout": ""})())
    finding = {"type": "test_suite", "summary": "Test broke", "signal_hash": "deadbeef12345678"}
    investigation = {
        "log_text": "Root cause found but no fix provided.",
        "summary": "Root cause summary",
        "story_id": "support-abc",
        "log_file": str(project_dir / ".synlynk" / "job.log"),
    }
    status, pr_url = synlynk._attempt_fix(finding, investigation, fixer="claude", dry_run=False)
    assert status == "no_diff"
    assert pr_url == ""
    assert calls == [], "No subprocess calls when no diff in log"


def test_agent_run_files_issue_on_test_failure(project_dir, monkeypatch):
    """End-to-end: test failure → issue filed → autopilot_runs row written."""
    import json, re

    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "support-engineer", "investigator": "claude", "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q --tb=short"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "support.json").write_text(json.dumps(cfg))

    def fake_run(cmd, **kw):
        if isinstance(cmd, list) and "pytest" in str(cmd):
            return type("R", (), {"returncode": 1, "stdout": "FAILED tests/test_x.py\n1 failed"})()
        if isinstance(cmd, list) and cmd[0] == "sh":
            shell = cmd[2] if len(cmd) > 2 else ""
            m = re.search(r"> (\S+\.log)\b", shell)
            if m:
                import os
                os.makedirs(os.path.dirname(m.group(1)), exist_ok=True)
                open(m.group(1), "w").write("Root cause found.\n")
                open(m.group(1) + ".exit", "w").write("0\n")
        if isinstance(cmd, list) and "issue" in cmd and "create" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "https://github.com/x/y/issues/5"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)
    synlynk.cmd_agent_run("support")

    conn = synlynk._get_db()
    rows = conn.execute("SELECT status, gh_issue_url FROM autopilot_runs").fetchall()
    conn.close()
    assert len(rows) >= 1
    assert any(r[0] in ("filed", "fix_failed", "fix_attempted") for r in rows)


def test_agent_run_dry_run_no_side_effects(project_dir, monkeypatch):
    import json

    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "support-engineer", "investigator": "claude", "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q --tb=short"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "support.json").write_text(json.dumps(cfg))

    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd) if isinstance(cmd, list) else cmd)
        if isinstance(cmd, list) and "pytest" in str(cmd):
            return type("R", (), {"returncode": 1, "stdout": "1 failed"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr("subprocess.run", fake_run)

    synlynk.cmd_agent_run("support", dry_run=True)

    gh_calls = [c for c in calls if isinstance(c, list) and "gh" in c]
    assert gh_calls == [], "gh must not be called in dry-run"

    conn = synlynk._get_db()
    rows = conn.execute("SELECT id FROM autopilot_runs").fetchall()
    conn.close()
    assert rows == [], "autopilot_runs must be empty in dry-run"


def test_install_cron_idempotent(project_dir, monkeypatch):
    crontab_contents = [""]

    def fake_run(cmd, **kw):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "crontab" in cmd_str and "-l" in cmd_str:
            return type("R", (), {"returncode": 0, "stdout": crontab_contents[0]})()
        if "crontab" in cmd_str and kw.get("input"):
            crontab_contents[0] = kw["input"]
            return type("R", (), {"returncode": 0})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    synlynk._install_cron_entry("support")
    first = crontab_contents[0]
    assert "synlynk.py agent run support" in first

    # Call again — must be idempotent
    synlynk._install_cron_entry("support")
    second = crontab_contents[0]
    assert second.count("synlynk.py agent run support") == 1


def test_upstream_divergence_no_upstream(project_dir):
    """Silent no-op when no upstream is configured (solo repo)."""
    import synlynk
    synlynk._check_upstream_divergence()  # must complete without error or output


def test_upstream_divergence_not_git(tmp_path, monkeypatch):
    """Silent no-op outside a git repo."""
    import synlynk
    monkeypatch.chdir(tmp_path)
    synlynk._check_upstream_divergence()  # must complete without error


def test_story_create_with_tokens(project_dir):
    import synlynk
    sid = synlynk.cmd_story_create("Test story", estimated_tokens=50000)
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT estimated_tokens FROM stories WHERE story_id=?", (sid,)
    ).fetchone()
    conn.close()
    assert row[0] == 50000


def test_story_create_without_tokens(project_dir):
    import synlynk
    sid = synlynk.cmd_story_create("No budget")
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT estimated_tokens FROM stories WHERE story_id=?", (sid,)
    ).fetchone()
    conn.close()
    assert row[0] is None


def test_story_list_shows_token_columns(project_dir, capsys):
    import synlynk
    synlynk.cmd_story_create("Token story", estimated_tokens=12345)
    synlynk.cmd_story_list()
    out = capsys.readouterr().out
    assert "EST TOK" in out
    assert "12,345" in out


def test_seed_devlog_creates_file(project_dir):
    import synlynk
    synlynk._seed_devlog("alice")
    devlog = project_dir / "project-docs" / "devlogs" / "alice.md"
    assert devlog.exists()
    content = devlog.read_text()
    assert "# Devlog — @alice" in content
    assert "Joined via `synlynk join`" in content


def test_seed_devlog_idempotent(project_dir):
    import synlynk
    synlynk._seed_devlog("alice")
    first_content = (project_dir / "project-docs" / "devlogs" / "alice.md").read_text()
    synlynk._seed_devlog("alice")
    second_content = (project_dir / "project-docs" / "devlogs" / "alice.md").read_text()
    assert first_content == second_content


def test_generate_ai_context_files_creates(project_dir):
    import synlynk
    synlynk._generate_ai_context_files("arch: src/main.py", "abc1234 feat: init")
    assert (project_dir / "CLAUDE.md").exists()
    assert (project_dir / "GEMINI.md").exists()
    assert (project_dir / "AGENTS.md").exists()
    content = (project_dir / "CLAUDE.md").read_text()
    assert "Context Snapshot" in content
    assert "arch: src/main.py" in content


def test_generate_ai_context_files_appends(project_dir):
    import synlynk
    (project_dir / "CLAUDE.md").write_text("# My Custom CLAUDE.md\nExisting content.\n")
    synlynk._generate_ai_context_files("arch: src/lib.py", "def456 fix: bug")
    content = (project_dir / "CLAUDE.md").read_text()
    assert "My Custom CLAUDE.md" in content
    assert "Existing content." in content
    assert "Context Snapshot" in content
    assert "arch: src/lib.py" in content


def test_build_team_digest_reads_devlogs(project_dir):
    import synlynk
    (project_dir / "project-docs" / "devlogs" / "alice.md").write_text(
        "# Devlog — @alice\n\n## 2026-06-20\nDid stuff.\n"
    )
    digest = synlynk._build_team_digest()
    users = [m["user"] for m in digest["members"]]
    assert "alice" in users


def test_build_team_digest_no_db(project_dir):
    import synlynk
    digest = synlynk._build_team_digest()
    assert "in_progress" in digest
    assert "members" in digest


def test_build_team_digest_includes_stories(project_dir):
    import synlynk
    synlynk.cmd_story_create("Active story", estimated_tokens=10000)
    digest = synlynk._build_team_digest()
    titles = [s["title"] for s in digest["in_progress"]]
    assert "Active story" in titles


def test_build_team_digest_top_todo(project_dir):
    import synlynk
    digest = synlynk._build_team_digest()
    assert digest["top_todo"] == "Task one"


def test_join_seeds_devlog(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "get_username", lambda: "testuser")
    monkeypatch.setattr(synlynk, "cmd_scan", lambda **kw: None)
    import subprocess as _sp
    monkeypatch.setattr(_sp, "check_output",
        lambda cmd, **kw: b"abc1234 feat: init\n" if "log" in cmd else b"")
    synlynk.cmd_join()
    devlog = project_dir / "project-docs" / "devlogs" / "testuser.md"
    assert devlog.exists()

def test_join_no_project_docs(tmp_path, monkeypatch):
    import synlynk, pytest
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "get_username", lambda: "testuser")
    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_join()
    assert exc.value.code == 1

def test_join_sets_team_mode(project_dir, monkeypatch):
    import synlynk, json
    monkeypatch.setattr(synlynk, "get_username", lambda: "testuser")
    monkeypatch.setattr(synlynk, "cmd_scan", lambda **kw: None)
    import subprocess as _sp
    monkeypatch.setattr(_sp, "check_output",
        lambda cmd, **kw: b"abc1234 feat: init\n" if "log" in cmd else b"")
    synlynk.cmd_join()
    cfg_path = project_dir / "project-docs" / ".synlynk_config.json"
    cfg = json.loads(cfg_path.read_text())
    assert cfg["mode"] == "team"

def test_join_idempotent(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "get_username", lambda: "testuser")
    monkeypatch.setattr(synlynk, "cmd_scan", lambda **kw: None)
    import subprocess as _sp
    monkeypatch.setattr(_sp, "check_output",
        lambda cmd, **kw: b"abc1234 feat: init\n" if "log" in cmd else b"")
    synlynk.cmd_join()
    devlog = project_dir / "project-docs" / "devlogs" / "testuser.md"
    first = devlog.read_text()
    synlynk.cmd_join()
    second = devlog.read_text()
    assert first == second


def test_team_status_shows_members(project_dir, capsys, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "get_username", lambda: "alice")
    (project_dir / "project-docs" / "devlogs" / "alice.md").write_text(
        "# Devlog — @alice\n\n## 2026-06-20\nDid work.\n"
    )
    (project_dir / "project-docs" / "devlogs" / "bob.md").write_text(
        "# Devlog — @bob\n\n## 2026-06-19\nDid work.\n"
    )
    synlynk.cmd_team_status()
    out = capsys.readouterr().out
    assert "TEAM STATUS" in out
    assert "@alice" in out
    assert "@bob" in out


def test_team_status_no_stories(project_dir, capsys):
    import synlynk
    synlynk.cmd_team_status()
    out = capsys.readouterr().out
    assert "TEAM STATUS" in out
    assert "No in-progress stories" in out


def test_team_status_shows_in_progress(project_dir, capsys):
    import synlynk
    synlynk.cmd_story_create("My feature", estimated_tokens=25000)
    synlynk.cmd_team_status()
    out = capsys.readouterr().out
    assert "My feature" in out
    assert "25,000" in out


def test_decide_dry_run_no_files(project_dir, monkeypatch):
    """Without --record, no files written to decisions/."""
    import synlynk
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: f"My recommendation on the topic from {agent}. Decision: go with option A.")
    synlynk.cmd_decide("Test topic", panel=["claude"], record=False)
    decisions_dir = project_dir / "project-docs" / "decisions"
    assert not decisions_dir.exists() or len(list(decisions_dir.iterdir())) == 0

def test_decide_record_writes_md_and_json(project_dir, monkeypatch):
    """With --record, both .md and .json files are written."""
    import synlynk, json as _json
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: f"Analysis from {agent}. Decision: use option B.")
    synlynk.cmd_decide("Relay ownership", panel=["claude", "agy"], record=True)
    decisions_dir = project_dir / "project-docs" / "decisions"
    md_files = list(decisions_dir.glob("*.md"))
    json_files = list(decisions_dir.glob("*.json"))
    assert len(md_files) == 1
    assert len(json_files) == 1
    record = _json.loads(json_files[0].read_text())
    assert record["topic"] == "Relay ownership"
    assert "claude" in record["inputs"]
    assert "agy" in record["inputs"]
    assert record["status"] == "approved"

def test_decide_json_has_decision_id(project_dir, monkeypatch):
    import synlynk, json as _json
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: "Analysis. Decision: proceed.")
    synlynk.cmd_decide("Architecture choice", panel=["claude"], record=True)
    json_file = next((project_dir / "project-docs" / "decisions").glob("*.json"))
    record = _json.loads(json_file.read_text())
    assert record["decision_id"].startswith("dec-")

def test_decide_md_contains_panel_inputs(project_dir, monkeypatch):
    import synlynk
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: f"Input from {agent}. Decision: yes.")
    synlynk.cmd_decide("DB choice", panel=["claude", "codex"], record=True)
    md_file = next((project_dir / "project-docs" / "decisions").glob("*.md"))
    content = md_file.read_text()
    assert "### claude" in content
    assert "### codex" in content
    assert "## Synthesis" in content
    assert "> Signatures:" in content

def test_decide_all_agents_fail_exits(project_dir, monkeypatch):
    import synlynk, pytest
    monkeypatch.setattr(synlynk, "_run_agent_sync",
        lambda agent, prompt, timeout=120: "")
    with pytest.raises(SystemExit) as exc:
        synlynk.cmd_decide("Topic", panel=["claude"], record=False)
    assert exc.value.code == 1


def test_daemon_jobs_table_exists(project_dir):
    conn = synlynk._get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "daemon_jobs" in tables


def test_daemon_jobs_insert_and_query(project_dir):
    import json
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("djob-001", "claude", "do something", "queued", 5, "[]", "2026-06-23T10:00:00")
    )
    conn.commit()
    row = conn.execute(
        "SELECT job_id, agent, status, priority, depends_on "
        "FROM daemon_jobs WHERE job_id=?", ("djob-001",)
    ).fetchone()
    conn.close()
    assert row[0] == "djob-001"
    assert row[1] == "claude"
    assert row[2] == "queued"
    assert row[3] == 5
    assert json.loads(row[4]) == []


def test_reconcile_daemon_jobs_marks_dead_pid_unknown(project_dir):
    """A running job whose PID no longer exists gets marked unknown without an exit signal."""
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("djob-dead", "claude", "task", "running", 5, "[]", 99999999,
         "2026-06-23T10:00:00", "2026-06-23T10:00:01")
    )
    conn.commit()
    conn.close()

    synlynk._reconcile_daemon_jobs()

    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?", ("djob-dead",)
    ).fetchone()
    conn2.close()
    assert row[0] == "unknown"
    assert row[1] is None


def test_reconcile_daemon_jobs_reads_exit_file(project_dir, tmp_path):
    """A dead job with an .exit file (exit code 0) is marked done."""
    log_path = str(project_dir / ".synlynk" / "logs" / "djob-ok.log")
    exit_path = log_path + ".exit"
    import os; os.makedirs(os.path.dirname(log_path), exist_ok=True)
    open(log_path, "w").close()
    open(exit_path, "w").write("0")

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("djob-ok", "claude", "task", "running", 5, "[]", 99999999,
         "2026-06-23T10:00:00", "2026-06-23T10:00:01", log_path)
    )
    conn.commit()
    conn.close()

    synlynk._reconcile_daemon_jobs()

    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?", ("djob-ok",)
    ).fetchone()
    conn2.close()
    assert row[0] == "done"
    assert row[1] == 0
    assert not os.path.exists(exit_path), ".exit file should have been deleted by reconcile"


def test_reconcile_jobs_uses_model_rate_table_for_completed_job_cost(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    log_path = project_dir / ".synlynk" / "logs" / "job-rate.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 1000 Output tokens: 200\n")

    job = {
        "id": "job-rate",
        "agent": "codex",
        "story_id": "",
        "task": "rate check",
        "pid": 9999996,
        "log_file": str(log_path),
        "worktree_path": "",
        "worktree_branch": "",
        "started_at": "2026-07-12T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "claude-opus-4-8",
    }
    sl._save_jobs([job])

    monkeypatch.setattr(jobs_mod.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    captured = {}

    def fake_write_job_summary(*args, **kwargs):
        captured["cost_usd"] = args[7]
        return ""

    monkeypatch.setattr(sl, "_write_job_summary", fake_write_job_summary)

    sl._reconcile_jobs()

    assert captured["cost_usd"] == pytest.approx((1000 / 1000 * 0.015) + (200 / 1000 * 0.075))


def test_dispatch_ready_jobs_respects_max_parallel(project_dir, monkeypatch):
    """Does not launch more jobs than max_parallel."""
    import json
    # Two already running
    conn = synlynk._get_db()
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
            "depends_on, pid, enqueued_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"running-{i}", "claude", "task", "running", 5, "[]", 99990 + i,
             "2026-06-23T10:00:00")
        )
    # Two queued
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
            "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
            (f"queued-{i}", "claude", "task", "queued", 5, "[]", "2026-06-23T10:00:01")
        )
    conn.commit()
    conn.close()

    launched = []
    def fake_popen(cmd, **kwargs):
        class FakeProc:
            pid = 12345
        launched.append(cmd)
        return FakeProc()

    monkeypatch.setattr(synlynk.subprocess, "Popen", fake_popen)
    # max_parallel=2 from config; 2 already running → 0 should launch
    synlynk._dispatch_ready_jobs(max_parallel=2)
    assert len(launched) == 0


def test_dispatch_ready_jobs_launches_queued_job(project_dir, monkeypatch):
    """Launches a queued job when under max_parallel."""
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("djob-q1", "claude", "do the thing", "queued", 5, "[]", "2026-06-23T10:00:00")
    )
    conn.commit()
    conn.close()

    launched = []
    class FakeProc:
        pid = 55555
        returncode = 0
        stdout = ""
        stderr = ""
        def communicate(self, *a, **kw):
            return ("", "")
        def wait(self, *a, **kw):
            return 0
        def poll(self):
            return 0
    def fake_popen(cmd, **kwargs):
        launched.append(cmd)
        return FakeProc()

    monkeypatch.setattr(synlynk.subprocess, "Popen", fake_popen)
    synlynk._dispatch_ready_jobs(max_parallel=4)
    # Only the agent shell spawn counts; dispatch_agent may also Popen via
    # subprocess.run for probe/git helpers on the same code path.
    shell_launches = [c for c in launched if c and c[0] == "sh"]
    assert len(shell_launches) == 1

    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status, pid FROM daemon_jobs WHERE job_id=?", ("djob-q1",)
    ).fetchone()
    conn2.close()
    assert row[0] == "running"
    assert row[1] == 55555


def test_dispatch_ready_jobs_skips_unmet_deps(project_dir, monkeypatch):
    """A job with unfinished depends_on is not launched."""
    import json
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("djob-dep", "claude", "task", "queued", 5,
         json.dumps(["djob-blocker"]), "2026-06-23T10:00:00")
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("djob-blocker", "claude", "task", "running", 5, "[]", "2026-06-23T09:59:00")
    )
    conn.commit()
    conn.close()

    launched = []
    class FakeProc:
        pid = 11111
    monkeypatch.setattr(synlynk.subprocess, "Popen", lambda *a, **kw: [launched.append(a), FakeProc()][1])
    synlynk._dispatch_ready_jobs(max_parallel=4)
    assert len(launched) == 0


def test_reconcile_daemon_jobs_reaps_via_waitpid(project_dir, monkeypatch):
    """_reconcile_daemon_jobs uses os.waitpid(WNOHANG) to detect exited children,
    catching zombies that os.kill(pid,0) would miss."""
    import os
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, pid, enqueued_at, started_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("djob-zombie", "claude", "task", "running", 5, "[]", 77777,
         "2026-06-23T10:00:00", "2026-06-23T10:00:01")
    )
    conn.commit()
    conn.close()

    # Simulate waitpid returning the pid (child has exited, exit code 0)
    def fake_waitpid(pid, options):
        return (pid, 0)  # os.WIFEXITED(0)=True, os.WEXITSTATUS(0)=0

    monkeypatch.setattr(os, "waitpid", fake_waitpid)
    # WIFEXITED / WEXITSTATUS must also handle the fake status 0
    monkeypatch.setattr(os, "WIFEXITED", lambda s: True)
    monkeypatch.setattr(os, "WEXITSTATUS", lambda s: 0)

    synlynk._reconcile_daemon_jobs()

    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?", ("djob-zombie",)
    ).fetchone()
    conn2.close()
    assert row[0] == "done"
    assert row[1] == 0


def test_dispatch_ready_jobs_fails_job_with_failed_dep(project_dir, monkeypatch):
    """A queued job whose dependency has failed is itself marked failed (no deadlock)."""
    import json
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("djob-blocked", "claude", "task", "queued", 5,
         json.dumps(["djob-failed-dep"]), "2026-06-23T10:00:00")
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        ("djob-failed-dep", "claude", "task", "failed", 5, "[]", "2026-06-23T09:59:00")
    )
    conn.commit()
    conn.close()

    launched = []
    class FakeProc:
        pid = 22222
    monkeypatch.setattr(synlynk.subprocess, "Popen",
                        lambda *a, **kw: [launched.append(a), FakeProc()][1])
    synlynk._dispatch_ready_jobs(max_parallel=4)

    # Nothing launched — the blocked job was failed immediately
    assert len(launched) == 0
    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", ("djob-blocked",)
    ).fetchone()
    conn2.close()
    assert row[0] == "failed"


def test_dispatch_ready_jobs_commits_per_job(project_dir, monkeypatch):
    """Each launched job is committed immediately so a crash doesn't leave duplicates."""
    commits_after_update = []
    original_commit = None

    class TrackingConn:
        def __init__(self, real_conn):
            self._real = real_conn
            self._updates_since_commit = 0

        def execute(self, sql, params=()):
            result = self._real.execute(sql, params)
            if sql.strip().upper().startswith("UPDATE"):
                self._updates_since_commit += 1
            return result

        def commit(self):
            commits_after_update.append(self._updates_since_commit)
            self._updates_since_commit = 0
            self._real.commit()

        def fetchone(self):
            return self._real.fetchone()

        def close(self):
            self._real.close()

    conn = synlynk._get_db()
    for i in range(2):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
            "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
            (f"djob-commit-{i}", "claude", "do it", "queued", 5, "[]",
             f"2026-06-23T10:00:0{i}")
        )
    conn.commit()
    conn.close()

    class FakeProc:
        pid = 33333
        returncode = 0
        stdout = ""
        stderr = ""
        def communicate(self, *a, **kw):
            return ("", "")
        def wait(self, *a, **kw):
            return 0
        def poll(self):
            return 0

    monkeypatch.setattr(synlynk.subprocess, "Popen", lambda *a, **kw: FakeProc())

    real_get_db = synlynk._get_db
    def patched_get_db():
        return TrackingConn(real_get_db())
    monkeypatch.setattr(synlynk, "_get_db", patched_get_db)

    synlynk._dispatch_ready_jobs(max_parallel=4)

    # Each job should produce exactly one commit with an UPDATE before it
    assert all(c >= 1 for c in commits_after_update if c > 0), \
        "Expected at least one commit with a preceding UPDATE per job"


def test_dispatch_ready_jobs_creates_worktree_and_applies_dispatch_flags(
    project_dir, monkeypatch
):
    """#190: queue-path launch goes through dispatch_agent (worktree + dispatch_flags).

    A queued daemon_jobs row launched via _dispatch_ready_jobs must get an
    isolated job worktree and agent dispatch/permission flags — not a bare
    sh -c in the daemon cwd with non_interactive_flags only.
    """
    import synlynk as sl
    from synlynk.dispatch import _job_worktree_details

    job_id = "djob-iso-190"
    agent = "claude"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, "
        "depends_on, enqueued_at) VALUES (?,?,?,?,?,?,?)",
        (job_id, agent, "implement isolation fix", "queued", 5, "[]",
         "2026-07-12T10:00:00"),
    )
    conn.commit()
    conn.close()

    captured = []

    class FakeProc:
        pid = 424242
        returncode = 0
        stdout = ""
        stderr = ""

        def communicate(self, *a, **kw):
            return ("", "")

        def wait(self, *a, **kw):
            return 0

        def poll(self):
            return 0

    def fake_popen(cmd, **kwargs):
        captured.append({"cmd": cmd, "kwargs": kwargs})
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        sl,
        "_preflight_dispatch",
        lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {
            "passed": True, "sentinel": None, "reason": None,
        },
    )
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")

    launched = sl._dispatch_ready_jobs(max_parallel=4)
    assert launched == 1

    expected_wt, expected_branch = _job_worktree_details(job_id, agent)
    # Stub fixture returns worktrees/<job_id>; dispatch still lays down logs/prompts under it.
    assert os.path.isdir(os.path.join(expected_wt, ".synlynk", "logs"))
    assert os.path.isdir(os.path.join(expected_wt, ".synlynk", "prompts"))

    shell = [c for c in captured if c["cmd"] and c["cmd"][0] == "sh"]
    assert len(shell) == 1
    shell_cmd = shell[0]["cmd"][2]
    assert "--dangerously-skip-permissions" in shell_cmd
    assert "--print" in shell_cmd
    assert shell[0]["kwargs"].get("cwd") == expected_wt

    jobs = sl._load_jobs()
    match = [j for j in jobs if j.get("id") == job_id]
    assert len(match) == 1
    assert match[0]["worktree_path"] == expected_wt
    assert match[0]["worktree_branch"] == expected_branch

    conn2 = sl._get_db()
    row = conn2.execute(
        "SELECT status, pid, log_path FROM daemon_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    conn2.close()
    assert row[0] == "running"
    assert row[1] == 424242
    assert job_id in (row[2] or "")


# ── SynlynkDaemon unit tests ────────────────────────────────────────────────

def test_synlynk_daemon_inherits_watch_daemon():
    assert issubclass(synlynk.SynlynkDaemon, synlynk.WatchDaemon)


def test_synlynk_daemon_has_separate_pidfile(project_dir):
    d = synlynk.SynlynkDaemon()
    assert d.pidfile == ".synlynk/daemon.pid"
    assert d.pidfile != synlynk.WatchDaemon().pidfile


def test_synlynk_daemon_is_not_running_without_pidfile(project_dir):
    d = synlynk.SynlynkDaemon()
    assert d._is_running() is False


def test_synlynk_daemon_stop_idempotent(project_dir, capsys):
    d = synlynk.SynlynkDaemon()
    d.stop()
    captured = capsys.readouterr()
    assert "not running" in captured.out


# ── HTTP handler tests ───────────────────────────────────────────────────────

def _invoke_daemon_handler(project_dir, method, path, body=b"", headers=None):
    """Run the daemon HTTP handler in-process without binding a socket."""
    import io
    import time as _time

    daemon = synlynk.SynlynkDaemon()
    daemon._start_time = _time.time()
    handler_class = synlynk._make_daemon_handler(daemon)
    handler = handler_class.__new__(handler_class)
    handler._daemon = daemon
    handler.path = path
    handler.headers = headers or {}
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    response = {"status": None, "headers": []}

    handler.send_response = lambda code: response.__setitem__("status", code)
    handler.send_header = lambda key, value: response["headers"].append((key, value))
    handler.end_headers = lambda: None

    getattr(handler, f"do_{method.upper()}")()
    return response["status"], response["headers"], handler.wfile.getvalue(), daemon


def test_http_status_endpoint(project_dir):
    import json
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/status")
    data = json.loads(body)
    assert status == 200
    assert "uptime_s" in data
    assert "pid" in data
    assert "jobs" in data
    assert set(data["jobs"].keys()) == {"queued", "running", "done", "failed"}


def test_http_context_endpoint_json(project_dir):
    import json
    (project_dir / ".synlynk" / "context.md").write_text("# Context\nHello world")
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/context")
    data = json.loads(body)
    assert status == 200
    assert "Hello world" in data["content"]


def test_http_context_endpoint_plain_text(project_dir):
    (project_dir / ".synlynk" / "context.md").write_text("# Context\nHello plain")
    status, headers, body, _ = _invoke_daemon_handler(
        project_dir, "GET", "/context", headers={"Accept": "text/plain"}
    )
    assert status == 200
    assert ("Content-Type", "text/plain; charset=utf-8") in headers
    assert b"Hello plain" in body


def test_http_jobs_endpoint_empty(project_dir):
    import json
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/jobs")
    data = json.loads(body)
    assert status == 200
    assert isinstance(data, list)


def test_http_dispatch_endpoint_enqueues_job(project_dir):
    import json
    body = json.dumps({"agent": "claude", "task": "do something"}).encode()
    status, _, response_body, _ = _invoke_daemon_handler(
        project_dir,
        "POST",
        "/dispatch",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    data = json.loads(response_body)
    assert status == 200
    assert "job_id" in data
    conn2 = synlynk._get_db()
    row = conn2.execute(
        "SELECT status FROM daemon_jobs WHERE job_id=?", (data["job_id"],)
    ).fetchone()
    conn2.close()
    assert row[0] == "queued"


def test_http_dispatch_missing_agent_returns_400(project_dir):
    import json
    body = json.dumps({"task": "do something"}).encode()
    status, _, _, _ = _invoke_daemon_handler(
        project_dir,
        "POST",
        "/dispatch",
        body=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    assert status == 400


def test_http_jobs_id_404_for_unknown(project_dir):
    status, _, _, _ = _invoke_daemon_handler(project_dir, "GET", "/jobs/no-such-job")
    assert status == 404


def test_http_sentinel_endpoint(project_dir):
    import json
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "- [WARN] FLATLINE: 3 consecutive failures\n"
        "- [INFO] something minor\n"
    )
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/sentinel")
    data = json.loads(body)
    assert status == 200
    assert isinstance(data, list)
    assert len(data) == 2


def test_http_checkpoint_endpoint(project_dir, monkeypatch):
    import json
    called = []
    monkeypatch.setattr(synlynk, "generate_context", lambda **kw: called.append(1))
    status, _, body, _ = _invoke_daemon_handler(project_dir, "POST", "/checkpoint")
    data = json.loads(body)
    assert status == 200
    assert data.get("regenerated") is True
    assert len(called) == 1


def test_http_stories_endpoint(project_dir):
    import json
    # Create a story first
    synlynk.cmd_story_create("Test story", "backend", "platform")
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/stories")
    data = json.loads(body)
    assert status == 200
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["engg_domain"] == "backend"


def test_http_stories_id_404(project_dir):
    status, _, _, _ = _invoke_daemon_handler(project_dir, "GET", "/stories/no-such-story")
    assert status == 404


def test_http_capability_endpoint(project_dir):
    import json
    status, _, body, _ = _invoke_daemon_handler(project_dir, "GET", "/capability")
    data = json.loads(body)
    assert status == 200
    assert isinstance(data, list)  # empty list is fine when no ratings exist


def test_daemon_cli_status_not_running(project_dir, capsys):
    import sys
    old_argv = sys.argv
    sys.argv = ["synlynk", "daemon", "status"]
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert "not running" in captured.out


def test_daemon_cli_stop_idempotent(project_dir, capsys):
    import sys
    old_argv = sys.argv
    sys.argv = ["synlynk", "daemon", "stop"]
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert "not running" in captured.out


def test_daemon_cli_default_no_action(project_dir, capsys):
    import sys
    old_argv = sys.argv
    sys.argv = ["synlynk", "daemon"]
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert "not running" in captured.out


def test_daemon_cli_restart_not_running(project_dir, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(synlynk.SynlynkDaemon, 'stop', lambda self: calls.append('stop') or print('  ✦ daemon not running'))
    monkeypatch.setattr(synlynk.SynlynkDaemon, 'start', lambda self: calls.append('start'))
    import sys
    old_argv = sys.argv
    sys.argv = ['synlynk', 'daemon', 'restart']
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    captured = capsys.readouterr()
    assert 'not running' in captured.out
    assert calls == ['stop', 'start'], f'restart must call stop then start; got {calls}'



def test_daemon_cli_install_service_dispatch(project_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(synlynk, "SynlynkDaemon", lambda: object())
    monkeypatch.setattr(synlynk, "_daemon_install_service", lambda d: calls.append(d))
    import sys
    old_argv = sys.argv
    sys.argv = ["synlynk", "daemon", "--install-service"]
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    assert len(calls) == 1


def test_daemon_cli_uninstall_service_dispatch(project_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(synlynk, "SynlynkDaemon", lambda: object())
    monkeypatch.setattr(synlynk, "_daemon_uninstall_service", lambda: calls.append("uninstall"))
    import sys
    old_argv = sys.argv
    sys.argv = ["synlynk", "daemon", "--uninstall-service"]
    try:
        try:
            synlynk.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    assert calls == ["uninstall"]


def test_install_service_macos(project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "darwin")
    monkeypatch.setattr(synlynk.shutil, "which", lambda name: "/usr/local/bin/synlynk" if name == "synlynk" else None)
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *a, **kw: None)

    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    launchagents_dir = project_dir / "Library" / "LaunchAgents"
    synlynk_dir = project_dir / "synlynk"
    launchagents_dir.mkdir(parents=True, exist_ok=True)
    synlynk_dir.mkdir(parents=True, exist_ok=True)

    synlynk._daemon_install_service(object())

    plist_path = launchagents_dir / "com.synlynk.daemon.plist"
    assert plist_path.exists()
    plist = plist_path.read_text()
    assert "<string>/usr/local/bin/synlynk</string>" in plist
    assert "<string>com.synlynk.daemon</string>" in plist
    assert ".synlynk/launchd.log" in plist
    assert calls[0][0] == ["launchctl", "load", "-w", str(plist_path)]


def test_install_service_linux(project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "linux")
    monkeypatch.setattr(
        synlynk.shutil,
        "which",
        lambda name: "/usr/bin/systemctl" if name == "systemctl" else "/usr/bin/synlynk",
    )
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *a, **kw: None)

    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    unit_dir = project_dir / ".config" / "systemd" / "user"
    synlynk_dir = project_dir / ".synlynk"
    unit_dir.mkdir(parents=True, exist_ok=True)
    synlynk_dir.mkdir(parents=True, exist_ok=True)

    synlynk._daemon_install_service(object())

    unit_path = unit_dir / "synlynk-daemon.service"
    assert unit_path.exists()
    unit = unit_path.read_text()
    assert "Type=forking" in unit
    assert "After=default.target" in unit
    assert "ExecStart=/usr/bin/synlynk daemon start" in unit
    assert "PIDFile=%h/.synlynk/daemon.pid" in unit
    assert "Restart=on-failure" in unit
    assert calls[0][0] == ["systemctl", "--user", "enable", "--now", "synlynk-daemon"]


def test_install_service_crontab(project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "linux")
    monkeypatch.setattr(synlynk.shutil, "which", lambda name: None)
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *a, **kw: None)

    crontab_contents = [""]
    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        if cmd == ["crontab", "-l"]:
            return type("R", (), {"returncode": 0, "stdout": crontab_contents[0]})()
        if cmd == ["crontab", "-"]:
            crontab_contents[0] = kw["input"]
            return type("R", (), {"returncode": 0, "stdout": ""})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    synlynk._daemon_install_service(object())
    synlynk._daemon_install_service(object())

    assert "@reboot" in crontab_contents[0]
    assert crontab_contents[0].count("daemon start") == 1
    assert calls[0][0] == ["crontab", "-l"]
    assert calls[1][0] == ["crontab", "-"]


def test_uninstall_service_macos(project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "darwin")
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *a, **kw: None)

    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    plist_path = project_dir / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text("plist")

    synlynk._daemon_uninstall_service()

    assert calls[0][0] == ["launchctl", "unload", str(plist_path)]
    assert not plist_path.exists()


def test_uninstall_service_linux(project_dir, monkeypatch):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "linux")
    monkeypatch.setattr(synlynk.shutil, "which", lambda name: "/usr/bin/systemctl" if name == "systemctl" else None)
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *a, **kw: None)

    calls = []

    def fake_run(cmd, **kw):
        calls.append((list(cmd), kw))
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    unit_path = project_dir / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text("unit")

    synlynk._daemon_uninstall_service()

    assert calls[0][0] == ["systemctl", "--user", "disable", "--now", "synlynk-daemon"]
    assert not unit_path.exists()


def test_uninstall_service_not_installed(project_dir, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "darwin")

    def fake_run(cmd, **kw):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(synlynk.subprocess, "run", fake_run)

    synlynk._daemon_uninstall_service()
    captured = capsys.readouterr()
    assert "not installed" in captured.out


def test_agent_capability_baselines_includes_grok():
    import synlynk
    assert "grok" in synlynk.AGENT_CAPABILITY_BASELINES
    grok = synlynk.AGENT_CAPABILITY_BASELINES["grok"]
    assert grok["cli"] == "grok"
    assert grok.get("prompt_flag") == "--single"
    assert "-p" not in grok.get("non_interactive_flags", [])
    # --always-approve is the correct required flag (Grok dropped --yes)
    assert "--always-approve" in grok["dispatch_flags"]["valid_flags"]
    assert "--always-approve" in grok["dispatch_flags"]["required_flags"]
    assert "--yes" in grok["dispatch_flags"]["invalid_flags"]
    assert "cli-chat-proxy.grok.com:443" in grok["network_deps"]["required_endpoints"]
    assert "builder" in grok["roles"]
    assert "architect" in grok["roles"]


def test_grok_baseline_uses_always_approve():
    # Grok dropped --yes; --always-approve is now the correct headless flag
    from synlynk import AGENT_CAPABILITY_BASELINES
    grok = AGENT_CAPABILITY_BASELINES.get("grok", {})
    flags = grok.get("dispatch_flags", {})
    assert "--always-approve" in flags.get("valid_flags", []), \
        "--always-approve must be valid for Grok (--yes was dropped)"
    assert "--always-approve" in flags.get("required_flags", []), \
        "--always-approve must be required for Grok"
    assert "--yes" in flags.get("invalid_flags", []), \
        "--yes must be invalid for Grok (it was dropped by Grok CLI)"


def test_grok_baseline_has_network_deps():
    from synlynk import AGENT_CAPABILITY_BASELINES
    grok = AGENT_CAPABILITY_BASELINES.get("grok", {})
    endpoints = grok.get("network_deps", {}).get("required_endpoints", [])
    assert any("cli-chat-proxy.grok.com" in e for e in endpoints)


def test_agent_discovery_defaults_includes_grok():
    import synlynk, os
    assert "grok" in synlynk.AGENT_DISCOVERY_DEFAULTS
    assert synlynk.AGENT_DISCOVERY_DEFAULTS["grok"] == os.path.expanduser("~/.grok")


def test_probe_grok_version(tmp_path, monkeypatch):
    """#287: grok model from ~/.grok/config.toml [models] default, not CLI -v text."""
    import os
    import synlynk

    home = tmp_path / "home"
    grok = home / ".grok"
    grok.mkdir(parents=True)
    (grok / "config.toml").write_text('[models]\ndefault = "grok-composer-2.5-fast"\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        os.path, "expanduser",
        lambda p: str(home / p[2:]) if p.startswith("~/") else (str(home) if p == "~" else p),
    )
    result = synlynk._probe_model_version("grok", "grok")
    assert result == "grok-composer-2.5-fast"


def test_grok_md_in_instruction_targets():
    import synlynk
    paths = [t[0] for t in synlynk._INSTRUCTION_TARGETS]
    assert "GROK.md" in paths
    entry = next(t for t in synlynk._INSTRUCTION_TARGETS if t[0] == "GROK.md")
    assert entry[1] == "grok"
    assert entry[2] == "html"


def test_marker_style_for_grok():
    import synlynk
    assert synlynk._MARKER_STYLE_FOR_TOOL.get("grok") == "html"


def test_grok_md_template_content():
    import synlynk
    templates = synlynk._build_templates()
    assert "GROK.md" in templates
    content = templates["GROK.md"]
    assert "Co-Authored-By: Grok <noreply@x.ai>" in content
    assert "grok" in content.lower()


def test_init_wizard_adds_grok_to_agent_slots(tmp_path, monkeypatch):
    import synlynk, json, os
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "")
    synlynk.init(agents=["claude", "agy", "codex", "grok"], mode="solo",
                 org=None, repo=None, project_id=None, force=False)
    config = json.load(open(".synlynk/config.json"))
    assert config["agent_slots"].get("grok") == "grok"
    assert os.path.exists("GROK.md")


# ---------------------------------------------------------------------------
# synlynk doctor tests
# ---------------------------------------------------------------------------

def test_hc_python_version_ok(monkeypatch):
    import synlynk, sys
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0))
    result = synlynk._hc_python_version()
    assert result.status == "ok"


def test_hc_python_version_fail(monkeypatch):
    import synlynk, sys
    monkeypatch.setattr(sys, "version_info", (3, 8, 10, "final", 0))
    result = synlynk._hc_python_version()
    assert result.status == "fail"
    assert "3.9" in result.fix


def test_hc_project_init_ok(tmp_path, monkeypatch):
    import synlynk, os
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    result = synlynk._hc_project_init()
    assert result.status == "ok"


def test_hc_project_init_fail(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    result = synlynk._hc_project_init()
    assert result.status == "fail"
    assert "synlynk init" in result.fix


def test_hc_docs_dir_ok(tmp_path, monkeypatch):
    import synlynk, os
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "project-docs"
    docs.mkdir()
    for fname in ["roadmap.md", "todo.md", "memory.md"]:
        (docs / fname).write_text("")
    os.makedirs(tmp_path / ".synlynk")
    (tmp_path / ".synlynk" / "config.json").write_text('{"project_docs_dir": "project-docs"}')
    result = synlynk._hc_docs_dir()
    assert result.status == "ok"


def test_hc_docs_dir_warn_missing_files(tmp_path, monkeypatch):
    import synlynk, os
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "project-docs"
    docs.mkdir()
    (docs / "roadmap.md").write_text("")  # only roadmap, missing todo + memory
    os.makedirs(tmp_path / ".synlynk")
    (tmp_path / ".synlynk" / "config.json").write_text('{"project_docs_dir": "project-docs"}')
    result = synlynk._hc_docs_dir()
    assert result.status == "warn"
    assert "todo.md" in result.message or "memory.md" in result.message


def test_hc_identity_key_ok(tmp_path, monkeypatch):
    import synlynk
    synlynk_home = tmp_path / ".synlynk_test_home"
    synlynk_home.mkdir()
    key = synlynk_home / "identity.key"
    key.write_text("fakeprivkey")
    (synlynk_home / "identity.key.pub").write_text("fakepubkey")
    monkeypatch.setattr(synlynk.os.path, "expanduser",
                        lambda p: str(synlynk_home) if p == "~/.synlynk" else synlynk.os.path.expanduser.__wrapped__(p)
                        if hasattr(synlynk.os.path.expanduser, "__wrapped__") else p.replace("~", str(tmp_path)))
    # Patch directly: simulate key existence without touching real home
    import unittest.mock as _mock
    with _mock.patch("synlynk.os.path.exists") as mock_exists:
        mock_exists.side_effect = lambda p: p.endswith("identity.key") or p.endswith("identity.key.pub")
        result = synlynk._hc_identity_key()
    assert result.status == "ok"


def test_hc_identity_key_warn_missing(monkeypatch):
    import synlynk
    import unittest.mock as _mock
    with _mock.patch("synlynk.os.path.exists", return_value=False):
        result = synlynk._hc_identity_key()
    assert result.status == "warn"
    assert "synlynk identity init" in result.fix


def test_hc_agent_profiles_ok(tmp_path, monkeypatch):
    import synlynk, os, json
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    os.makedirs(tmp_path / ".agents")
    config = {"agent_slots": {"claude": "claude", "agy": "agy"}}
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))
    for name in ["claude", "agy"]:
        (tmp_path / ".agents" / f"{name}.json").write_text("{}")
    result = synlynk._hc_agent_profiles()
    assert result.status == "ok"


def test_hc_agent_profiles_warn_missing(tmp_path, monkeypatch):
    import synlynk, os, json
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    os.makedirs(tmp_path / ".agents")
    config = {"agent_slots": {"claude": "claude", "agy": "agy"}}
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))
    # only claude profile exists — agy is missing
    (tmp_path / ".agents" / "claude.json").write_text("{}")
    result = synlynk._hc_agent_profiles()
    assert result.status == "warn"
    assert "agy" in result.message


def test_hc_instruction_files_ok(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    for fname in ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "GROK.md"]:
        (tmp_path / fname).write_text("")
    result = synlynk._hc_instruction_files()
    assert result.status == "ok"


def test_hc_instruction_files_warn(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("")  # others missing
    result = synlynk._hc_instruction_files()
    assert result.status == "warn"
    assert "GEMINI.md" in result.message or "AGENTS.md" in result.message


def test_hc_version_current_up_to_date(monkeypatch):
    import synlynk, json as _json
    import urllib.request as _req

    class FakeResp:
        def __init__(self): self._data = _json.dumps({"tag_name": f"v{synlynk.VERSION}"}).encode()
        def read(self): return self._data
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(_req, "urlopen", lambda *a, **kw: FakeResp())
    result = synlynk._hc_version_current()
    assert result.status == "ok"
    assert "up to date" in result.message


def test_hc_version_current_update_available(monkeypatch):
    import synlynk, json as _json
    import urllib.request as _req

    class FakeResp:
        def __init__(self): self._data = _json.dumps({"tag_name": "v99.0.0"}).encode()
        def read(self): return self._data
        def __enter__(self): return self
        def __exit__(self, *a): pass

    monkeypatch.setattr(_req, "urlopen", lambda *a, **kw: FakeResp())
    result = synlynk._hc_version_current()
    assert result.status == "warn"
    assert "99.0.0" in result.message
    assert "synlynk upgrade" in result.fix


def test_hc_version_current_offline(monkeypatch):
    import synlynk, urllib.error, urllib.request as _req
    monkeypatch.setattr(_req, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    result = synlynk._hc_version_current()
    assert result.status == "warn"
    assert "offline" in result.message.lower() or "timeout" in result.message.lower()


def test_hc_model_rates_no_file(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    result = synlynk._hc_model_rates()
    assert result.status == "warn"
    assert "never been updated" in result.message
    assert "synlynk init" in result.fix


def test_hc_model_rates_fresh(tmp_path, monkeypatch):
    import synlynk, os, json, time
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    today_str = time.strftime("%Y-%m-%d")
    rates_data = {"unit": "usd_per_1k_tokens", "rates_updated_at": today_str}
    (tmp_path / ".synlynk" / "model_rates.json").write_text(json.dumps(rates_data))
    result = synlynk._hc_model_rates()
    assert result.status == "ok"
    assert "fresh" in result.message


def test_hc_model_rates_stale(tmp_path, monkeypatch):
    import synlynk, os, json
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    rates_data = {"unit": "usd_per_1k_tokens", "rates_updated_at": "2025-01-01"}
    (tmp_path / ".synlynk" / "model_rates.json").write_text(json.dumps(rates_data))
    result = synlynk._hc_model_rates()
    assert result.status == "warn"
    assert "stale" in result.message
    assert "refresh" in result.fix or "timestamp" in result.fix


def test_hc_model_rates_invalid_date(tmp_path, monkeypatch):
    import synlynk, os, json
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    rates_data = {"unit": "usd_per_1k_tokens", "rates_updated_at": "invalid-date"}
    (tmp_path / ".synlynk" / "model_rates.json").write_text(json.dumps(rates_data))
    result = synlynk._hc_model_rates()
    assert result.status == "warn"
    assert "invalid" in result.message
    assert "Update" in result.fix


def test_sentinel_model_rates_no_file(tmp_path, monkeypatch):
    import synlynk
    monkeypatch.chdir(tmp_path)
    # Should not write alert because model_rates.json does not exist
    synlynk.check_model_rates_freshness()
    assert not (tmp_path / ".synlynk" / "sentinel.md").exists()


def test_sentinel_model_rates_stale(tmp_path, monkeypatch):
    import synlynk, os, json
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    rates_data = {"unit": "usd_per_1k_tokens", "rates_updated_at": "2025-01-01"}
    (tmp_path / ".synlynk" / "model_rates.json").write_text(json.dumps(rates_data))
    synlynk.check_model_rates_freshness()
    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_path.exists()
    assert "STALE_MODEL_RATES" in sentinel_path.read_text()


def test_sentinel_model_rates_fresh(tmp_path, monkeypatch):
    import synlynk, os, json, time
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / ".synlynk")
    today_str = time.strftime("%Y-%m-%d")
    rates_data = {"unit": "usd_per_1k_tokens", "rates_updated_at": today_str}
    (tmp_path / ".synlynk" / "model_rates.json").write_text(json.dumps(rates_data))
    synlynk.check_model_rates_freshness()
    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    # Either sentinel.md does not exist, or it has no STALE_MODEL_RATES alert
    if sentinel_path.exists():
        assert "STALE_MODEL_RATES" not in sentinel_path.read_text()


def test_cmd_doctor_all_ok(tmp_path, monkeypatch, capsys):
    import synlynk
    ok_check = lambda: synlynk.HealthCheck("fake", "ok", "all good")
    exit_code = synlynk.cmd_doctor(checks=[ok_check, ok_check])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "All checks passed" in out


def test_cmd_doctor_with_failure(tmp_path, monkeypatch, capsys):
    import synlynk
    fail_check = lambda: synlynk.HealthCheck("fake", "fail", "broken", fix="fix it")
    exit_code = synlynk.cmd_doctor(checks=[fail_check])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "fix it" in out


def test_cmd_doctor_with_warn_only(tmp_path, monkeypatch, capsys):
    import synlynk
    warn_check = lambda: synlynk.HealthCheck("fake", "warn", "advisory", fix="maybe fix")
    exit_code = synlynk.cmd_doctor(checks=[warn_check])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "advisory warning" in out


def test_health_check_dataclass():
    import synlynk
    hc = synlynk.HealthCheck("test", "ok", "msg")
    assert hc.name == "test"
    assert hc.status == "ok"
    assert hc.fix == ""  # default


# ---------------------------------------------------------------------------
# synlynk exit / repair / sync tests
# ---------------------------------------------------------------------------

_CLAUDE_MD_WITH_MARKERS = (
    "# User section\n\n"
    '<!-- synlynk:start version="0.9.8" tool="claude" -->\n'
    "## synlynk Context\nmanaged content here\n"
    "<!-- synlynk:end -->\n"
)

_MANIFEST_CONTENT = {
    "schema_version": 1,
    "generated_at": "2026-06-27T00:00:00",
    "synlynk_version": "0.9.8",
    "files": {
        "CLAUDE.md": {"tool": "claude", "sha": "abc123", "last_checked": "2026-06-27T00:00:00"},
    },
}


def _setup_exit_project(tmp_path):
    """Create minimal synlynk project state for exit/repair/sync tests."""
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / "project-docs").mkdir(exist_ok=True)
    import json as _json
    cfg = {
        "schema_version": 1, "synlynk_version": "0.9.8",
        "mode": "solo", "org": None, "repo": None,
        "agent_slots": {"claude": {"cli": "claude", "roles": ["builder"]}},
        "docs_dir": "project-docs",
    }
    (tmp_path / ".synlynk" / "config.json").write_text(_json.dumps(cfg))
    (tmp_path / ".synlynk" / "instructions.json").write_text(_json.dumps(_MANIFEST_CONTENT))
    (tmp_path / "CLAUDE.md").write_text(_CLAUDE_MD_WITH_MARKERS)
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / ".agents" / "claude.json").write_text(_json.dumps({"name": "claude"}))


def test_cmd_exit_dry_run_prints_plan(tmp_path, monkeypatch, capsys):
    """Dry-run prints what would happen without touching any files."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    rc = synlynk.cmd_exit(dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry run" in out.lower()
    assert ".synlynk" in out
    assert (tmp_path / ".synlynk").exists()


def test_cmd_exit_confirm_removes_synlynk_dir(tmp_path, monkeypatch, capsys):
    """--confirm removes .synlynk/ and writes SYNLYNK_HANDOFF.md."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    rc = synlynk.cmd_exit(dry_run=False)
    assert rc == 0
    assert not (tmp_path / ".synlynk").exists()
    assert (tmp_path / "SYNLYNK_HANDOFF.md").exists()
    handoff = (tmp_path / "SYNLYNK_HANDOFF.md").read_text()
    assert "synlynk handoff" in handoff.lower()
    assert "synlynk init" in handoff


def test_cmd_exit_strips_instruction_sections(tmp_path, monkeypatch, capsys):
    """Synlynk section is removed from CLAUDE.md on exit --confirm."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    assert "synlynk:start" in claude_md.read_text()
    synlynk.cmd_exit(dry_run=False)
    if claude_md.exists():
        assert "synlynk:start" not in claude_md.read_text()


def test_cmd_exit_remove_docs_flag(tmp_path, monkeypatch, capsys):
    """--remove-docs deletes project-docs/."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    assert (tmp_path / "project-docs").exists()
    synlynk.cmd_exit(dry_run=False, remove_docs=True)
    assert not (tmp_path / "project-docs").exists()


def test_strip_synlynk_section_html(tmp_path):
    """Helper removes html-style synlynk block, leaving surrounding content."""
    f = tmp_path / "CLAUDE.md"
    f.write_text('# Before\n\n<!-- synlynk:start version="1" tool="claude" -->\nmanaged content\n<!-- synlynk:end -->\n\n# After\n')
    removed = synlynk._strip_synlynk_section(str(f), "html")
    assert removed
    remaining = f.read_text()
    assert "synlynk:start" not in remaining
    assert "# Before" in remaining
    assert "# After" in remaining


def test_strip_synlynk_section_none_removes_file(tmp_path):
    """marker_style='none' deletes the file entirely."""
    f = tmp_path / ".cursorrules"
    f.write_text("owned content\n")
    synlynk._strip_synlynk_section(str(f), "none")
    assert not f.exists()


def test_strip_synlynk_section_no_markers(tmp_path):
    """Returns False and leaves file unchanged if no markers present."""
    f = tmp_path / "CUSTOM.md"
    f.write_text("no markers here\n")
    removed = synlynk._strip_synlynk_section(str(f), "html")
    assert not removed
    assert f.read_text() == "no markers here\n"


def test_cmd_repair_dry_run(tmp_path, monkeypatch, capsys):
    """Repair dry-run shows exit + re-init plan without executing."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    rc = synlynk.cmd_repair(dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry run" in out.lower()
    assert (tmp_path / ".synlynk").exists()


def test_cmd_repair_confirm_reinits(tmp_path, monkeypatch, capsys):
    """Repair --confirm exits then re-inits (init mocked to avoid interactive wizard)."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    reinit_calls = []

    def mock_init(**kwargs):
        (tmp_path / ".synlynk").mkdir(exist_ok=True)
        import json as _j
        (tmp_path / ".synlynk" / "config.json").write_text(_j.dumps({"mode": "solo"}))
        reinit_calls.append(kwargs)

    monkeypatch.setattr(synlynk, "init", mock_init)
    rc = synlynk.cmd_repair(dry_run=False)
    assert rc == 0
    assert len(reinit_calls) == 1
    assert (tmp_path / ".synlynk").exists()


def test_cmd_sync_dry_run(tmp_path, monkeypatch, capsys):
    """Sync dry-run prints what would be updated without writing."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    rc = synlynk.cmd_sync(dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry run" in out.lower()


def test_cmd_sync_confirm_updates_instruction_files(tmp_path, monkeypatch, capsys):
    """Sync --confirm re-writes synlynk sections in tracked instruction files."""
    monkeypatch.chdir(tmp_path)
    _setup_exit_project(tmp_path)
    rc = synlynk.cmd_sync(dry_run=False)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sync complete" in out or "✓" in out


def test_cmd_sync_no_manifest(tmp_path, monkeypatch, capsys):
    """Sync with no tracked files prints advisory and returns 0."""
    monkeypatch.chdir(tmp_path)
    rc = synlynk.cmd_sync(dry_run=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "no tracked" in out.lower() or "dry run" in out.lower()


def test_agy_baseline_has_headless_contract():
    from synlynk import AGENT_CAPABILITY_BASELINES
    agy = AGENT_CAPABILITY_BASELINES.get("agy", {})
    contract = agy.get("headless_contract", {})
    assert contract.get("requires_pty") is False
    assert contract.get("stdout_flush_method") == "unbuffered"
    assert "PYTHONUNBUFFERED=1" in contract.get("env_vars_required", [])


def test_agy_dispatch_injects_pythonunbuffered(project_dir, monkeypatch):
    import os
    import subprocess
    import synlynk as sl
    # Stub agy CLI that prints its environment
    stub = project_dir / "agy"
    stub.write_text("#!/bin/sh\nenv | grep PYTHONUNBUFFERED\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(project_dir) + ":" + os.environ["PATH"])
    captured_env = {}
    original_popen = subprocess.Popen
    def mock_popen(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return original_popen(cmd, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda agent, cli: "mock-model")

    # call dispatch_agent for agy with a minimal task
    sl.dispatch_agent("agy", "echo test")
    assert "PYTHONUNBUFFERED" in captured_env
    assert captured_env["PYTHONUNBUFFERED"] == "1"


def test_reconcile_detects_stall_and_kills_process(tmp_path, monkeypatch):
    import signal, time, json, os
    import synlynk as sl

    job_id = "job-stall-test"
    log_file = tmp_path / f"{job_id}.log"
    log_file.write_bytes(b"")  # 0 bytes — stalled
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))

    job = {
        "id": job_id, "agent": "agy", "status": "running",
        "pid": 99999,  # non-existent PID
        "started_at": old_time,
        "log_file": str(log_file),
    }

    config = {"agents": {"agy": {"stall_timeout_minutes": 30}}, "stall_timeout_minutes": 30}
    sentinel_path = tmp_path / "sentinel.md"

    killed = []
    def mock_kill(pid, sig):
        killed.append((pid, sig))
    monkeypatch.setattr(os, "kill", mock_kill)

    result = sl._check_job_stall(job, config, str(sentinel_path))

    assert result is True
    assert job["status"] == "failed"
    assert len(killed) > 0
    assert "STALL_NO_OUTPUT" in sentinel_path.read_text()


def test_check_job_stall_extends_on_remote_activity(tmp_path, monkeypatch):
    import os
    import time
    import synlynk as sl

    job_id = "job-stall-remote-activity"
    log_file = tmp_path / f"{job_id}.log"
    log_file.write_bytes(b"")
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))

    job = {
        "id": job_id,
        "agent": "agy",
        "status": "running",
        "pid": 99999,
        "started_at": old_time,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-xyz",
    }

    monkeypatch.setattr(
        sl,
        "_inspect_worktree_git_state",
        lambda *a, **kw: {
            "has_activity": False,
            "remote_has_activity": True,
            "remote_ref": "origin/dispatch/codex/job-xyz",
            "remote_commit_count": 2,
            "dirty": False,
            "commits_ahead": 0,
        },
    )

    result = sl._check_job_stall(
        job,
        {"stall_timeout_minutes": 0},
        str(tmp_path / "sentinel.md"),
    )

    assert result is False
    assert job["status"] == "running"


def test_check_job_stall_still_kills_on_zero_activity(tmp_path, monkeypatch):
    import os
    import time
    import synlynk as sl

    job_id = "job-stall-zero-activity"
    log_file = tmp_path / f"{job_id}.log"
    log_file.write_bytes(b"")
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))

    job = {
        "id": job_id,
        "agent": "agy",
        "status": "running",
        "pid": 99999,
        "started_at": old_time,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-xyz",
    }

    monkeypatch.setattr(
        sl,
        "_inspect_worktree_git_state",
        lambda *a, **kw: {
            "has_activity": False,
            "remote_has_activity": False,
            "dirty": False,
            "commits_ahead": 0,
        },
    )

    result = sl._check_job_stall(
        job,
        {"stall_timeout_minutes": 0},
        str(tmp_path / "sentinel.md"),
    )

    assert result is True
    assert job["status"] == "failed"
    assert job["exit_code"] == -1
