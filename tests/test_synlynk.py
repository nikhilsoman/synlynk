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
    assert "agy" in synlynk.AGENT_CAPABILITY_BASELINES
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


def test_version_is_070(project_dir):
    assert synlynk.VERSION == "0.7.0"


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
    assert result[0]["status"] == "failed"  # dead PID → failed regardless


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
    assert "project-docs/roadmap.md" in written
    assert "project-docs/memory.md" in written
    assert "project-docs/todo.md" in written


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
    job = sl.dispatch_agent("claude", "implement auth fix", story_id="14")
    assert job["agent"] == "claude"
    assert job["pid"] == 12345
    assert job["status"] == "running"
    assert job["task"] == "implement auth fix"
    assert job["story_id"] == "14"
    jobs = sl._load_jobs()
    assert any(j["id"] == job["id"] for j in jobs)


def test_dispatch_agent_writes_prompt_file(project_dir, monkeypatch):
    import synlynk as sl
    class FakeProc:
        pid = 99
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
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
    sl.dispatch_agent("claude", "task one")
    sl.dispatch_agent("claude", "task two")
    assert len(sl._load_jobs()) == 2


def test_dispatch_agent_injects_relevant_files(project_dir, monkeypatch):
    """dispatch_agent includes ## Relevant Files when story has scan data."""
    import synlynk as sl, json
    class FakeProc:
        pid = 1
    monkeypatch.setattr("subprocess.Popen", lambda *a, **kw: FakeProc())
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
    story_id = sl.cmd_story_create("Fix thing", engg_domain="backend")
    # Mock _git_head_sha to avoid subprocess.run call
    monkeypatch.setattr(sl, "_git_head_sha", lambda: None)
    job = sl.dispatch_agent("claude", "fix it", story_id=story_id)
    prompt = open(job["prompt_file"]).read()
    assert "## Relevant Files" not in prompt


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
    # Use timestamps that will fall into the correct windows relative to datetime('now')
    recent_ts = "2026-06-21T12:00:00"  # Recent window (last 7 days)
    prior_ts = "2026-06-10T12:00:00"   # Prior window (7-14 days ago)
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
