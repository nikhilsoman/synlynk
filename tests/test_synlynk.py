import sys
import os
import time
import json
import pytest
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))
import synlynk


def test_agent_capability_baselines_exist():
    assert "claude" in synlynk.AGENT_CAPABILITY_BASELINES
    assert "gemini" in synlynk.AGENT_CAPABILITY_BASELINES
    assert "codex" in synlynk.AGENT_CAPABILITY_BASELINES
    for name, caps in synlynk.AGENT_CAPABILITY_BASELINES.items():
        assert "roles" in caps
        assert "cli" in caps
        assert "non_interactive_flags" in caps


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


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert config["schema_version"] == 1
    assert config["budget"]["limit_usd"] == 10.0


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

def test_generate_context_omits_sentinel_section_when_empty(project_dir):
    synlynk.generate_context()
    ctx = (project_dir / ".synlynk" / "context.md").read_text()
    assert "Sentinel Alerts" not in ctx

def test_generate_context_scope_stub_falls_back(project_dir, capsys):
    synlynk.generate_context(scope="task:99")
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out
    # Still generates full context
    assert (project_dir / ".synlynk" / "context.md").exists()


def test_init_creates_project_structure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.init(force=False)
    assert (tmp_path / "project-docs" / "todo.md").exists()
    assert (tmp_path / "project-docs" / "memory.md").exists()
    assert (tmp_path / ".synlynk" / "config.json").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()


def test_init_claude_md_contains_session_protocol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.init(force=False)
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "synlynk watch status" in content
    assert "synlynk checkpoint" in content
    assert "context.md" in content


def test_init_skips_existing_without_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("MY CUSTOM CONTENT")
    synlynk.init(force=False)
    assert (tmp_path / "CLAUDE.md").read_text() == "MY CUSTOM CONTENT"


def test_init_force_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("MY CUSTOM CONTENT")
    synlynk.init(force=True)
    assert (tmp_path / "CLAUDE.md").read_text() != "MY CUSTOM CONTENT"
    assert "synlynk checkpoint" in (tmp_path / "CLAUDE.md").read_text()


def test_init_config_schema_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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

def test_upgrade_reports_up_to_date(monkeypatch, capsys):
    fake_gh = type('R', (), {
        'stdout': f"v{synlynk.VERSION}\n",
        'returncode': 0,
    })()
    monkeypatch.setattr(synlynk.subprocess, 'run', lambda *a, **kw: fake_gh)
    synlynk.upgrade()
    captured = capsys.readouterr()
    assert "latest version" in captured.out

def test_upgrade_reports_new_version(monkeypatch, capsys):
    import json as _json
    fake_response = type('R', (), {
        'read': lambda self: _json.dumps({"tag_name": "v99.0.0"}).encode(),
        '__enter__': lambda self: self,
        '__exit__': lambda self, *a: None,
    })()
    monkeypatch.setattr(synlynk.subprocess, 'run', lambda *a, **kw: (_ for _ in ()).throw(Exception("no gh")))
    monkeypatch.setattr(synlynk.urllib.request, 'urlopen', lambda *a, **kw: fake_response)
    synlynk.upgrade()
    captured = capsys.readouterr()
    assert "99.0.0" in captured.out
    assert "available" in captured.out

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
                 ".cursorrules", "config.json"]:
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
    assert "Co-Authored-By: Gemini" in content
    assert "feat/agy/" in content
    assert "Git Worktree-First Policy" in content
    assert "Live Issues SOP" in content
    assert "AGY CLI" in content
    assert "2026-06-18" in content


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
    synlynk.init()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_skips_agents_md_when_codex_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.init(agents=["claude", "agy"])
    assert not (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()


def test_init_skips_claude_md_when_claude_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.init(agents=["agy", "codex"])
    assert not (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "GEMINI.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_skips_gemini_md_when_agy_excluded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
    synlynk.init()
    config_path = tmp_path / "project-docs" / ".synlynk_config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["mode"] == "solo"
    assert data["version"] == synlynk.VERSION


def test_init_writes_synlynk_config_team_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.init(mode="team")
    config_path = tmp_path / "project-docs" / ".synlynk_config.json"
    data = json.loads(config_path.read_text())
    assert data["mode"] == "team"


def test_init_skips_synlynk_config_if_exists_without_force(project_dir):
    # conftest already wrote mode=single; init(mode="team") without force must not overwrite
    synlynk.init(mode="team")
    config_path = project_dir / "project-docs" / ".synlynk_config.json"
    data = json.loads(config_path.read_text())
    assert data["mode"] == "single"


def test_init_overwrites_synlynk_config_with_force(project_dir):
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
    synlynk.init(project_id="PJ_xyz789")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert "PJ_xyz789" in content
    assert "TODO: PROJECT_ID" not in content


def test_init_with_org_stored_in_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
    assert config["agent_slots"]["agy"] == "gemini"
    assert config["agent_slots"]["codex"] == "codex"


def test_build_templates_config_includes_owner_and_project_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = synlynk._build_templates(owner="Dialify", project_id="PVT_abc")
    config = json.loads(t["config.json"])
    assert config["owner"] == "Dialify"
    assert config["project_id"] == "PVT_abc"
    assert "agent_slots" in config


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
    synlynk.update_costs("claude --print hello", 1000, 200, 30.0)
    content = (project_dir / "project-docs" / "costs.md").read_text()
    assert "1000/200" in content
    # cost: (1000/1000*0.003) + (200/1000*0.015) = 0.003 + 0.003 = $0.0060
    assert "$0.0060" in content


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


def test_version_is_040(project_dir):
    assert synlynk.VERSION == "0.4.0"


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


def test_reconcile_marks_dead_pid_as_failed(project_dir):
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
    assert dead["status"] == "failed"
    assert dead["ended_at"] is not None


def test_reconcile_skips_finished_jobs(project_dir):
    jobs = [{"id": "job-done", "pid": 9999999, "status": "completed",
              "ended_at": "2026-06-14T09:00:00", "exit_code": 0}]
    synlynk._save_jobs(jobs)
    synlynk._reconcile_jobs()
    result = synlynk._load_jobs()
    assert result[0]["status"] == "completed"  # unchanged


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


def test_dispatch_agent_creates_job_entry(project_dir, monkeypatch):
    launched = []
    class FakeProc:
        pid = 12345
    def fake_popen(cmd, **kw):
        launched.append(cmd)
        return FakeProc()
    monkeypatch.setattr("subprocess.Popen", fake_popen)
    job = synlynk.dispatch_agent("claude", "implement auth fix", story_id="14")
    assert job["agent"] == "claude"
    assert job["pid"] == 12345
    assert job["status"] == "running"
    assert job["task"] == "implement auth fix"
    assert job["story_id"] == "14"
    jobs = synlynk._load_jobs()
    assert any(j["id"] == job["id"] for j in jobs)


def test_dispatch_agent_writes_prompt_file(project_dir, monkeypatch):
    class FakeProc:
        pid = 99
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    job = synlynk.dispatch_agent("gemini", "write tests")
    assert os.path.exists(job["prompt_file"])
    content = open(job["prompt_file"]).read()
    assert "write tests" in content


def test_dispatch_agent_unknown_agent_raises(project_dir):
    with pytest.raises(ValueError, match="Unknown agent"):
        synlynk.dispatch_agent("unknownbot", "do thing")


def test_dispatch_agent_appends_to_existing_jobs(project_dir, monkeypatch):
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
    synlynk.dispatch_agent("claude", "task one")
    synlynk.dispatch_agent("claude", "task two")
    assert len(synlynk._load_jobs()) == 2
