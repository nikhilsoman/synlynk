"""Tests for synlynk roles and agent onboarding."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import synlynk


def _write_config(tmp_path, **overrides):
    config = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "watch_interval_seconds": 30,
        "auto_launch_after_wizard": True,
        "dispatch_mode": "daily-grind",
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "project_docs_dir": "project-docs",
        "agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex"},
        "workgroup_agents": [],
        "last_housekeeping_date": None,
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
        "stall_timeout_minutes": 30,
        "agents": {},
        "roles": {
            "claude": ["pm", "review", "deploy"],
            "agy": ["implement", "test", "css", "templates", "content"],
            "grok": ["implement", "test", "canvas", "js", "infra"],
            "codex": ["implement", "test", "refactor"],
        },
    }
    config.update(overrides)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))


def test_load_config_roles_default_has_four_agents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    roles = cfg.get("roles", {})
    assert set(roles.keys()) >= {"claude", "agy", "grok", "codex"}


def test_load_config_roles_claude_is_pm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    assert "pm" in cfg["roles"]["claude"]


def test_load_config_roles_codex_is_implement(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    assert "implement" in cfg["roles"]["codex"]


def test_fence_exists_false_when_no_fence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "CLAUDE.md"
    f.write_text("# Some file\nno fence here\n")
    assert not synlynk._fence_exists(str(f))


def test_fence_exists_true_when_fence_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "GEMINI.md"
    f.write_text(
        "# Header\n"
        "<!-- synlynk:harness v1 verified:2026-01-01 -->\n"
        "body\n"
        "<!-- /synlynk:harness -->\n"
    )
    assert synlynk._fence_exists(str(f))


def test_cmd_roles_prints_only_workgroup_agents(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, workgroup_agents=["claude", "codex"])
    (tmp_path / "CLAUDE.md").write_text(
        "# Claude\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\nbody\n<!-- /synlynk:harness -->\n"
    )
    (tmp_path / "AGENTS.md").write_text(
        "# Codex\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\nbody\n<!-- /synlynk:harness -->\n"
    )
    synlynk.cmd_roles(fix=False)
    out = capsys.readouterr().out
    assert "claude" in out
    assert "codex" in out
    assert "agy" not in out
    assert "grok" not in out


def test_cmd_roles_fix_writes_fence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, workgroup_agents=["claude"])
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Claude\nSome content\n")
    synlynk.cmd_roles(fix=True)
    content = claude_md.read_text()
    assert "<!-- synlynk:harness" in content


def test_cmd_roles_fix_skips_missing_file(tmp_path, monkeypatch, capsys):
    """--fix should not create files that don't exist, just skip them."""
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, workgroup_agents=["claude"])
    synlynk.cmd_roles(fix=True)
    _ = capsys.readouterr()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_cmd_agent_add_onboards_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    stub = tmp_path / "codex"
    stub.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  --version) echo 'codex 1.2.3'; exit 0 ;;\n"
        "  --help) echo '  exec  Run commands'; exit 0 ;;\n"
        "  *) echo 'codex stub'; exit 0 ;;\n"
        "esac\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    synlynk.cmd_agent_add("codex")

    out = capsys.readouterr().out
    assert "onboarded codex" in out
    assert (tmp_path / "AGENTS.md").exists()
    assert "<!-- synlynk:harness" in (tmp_path / "AGENTS.md").read_text()

    cfg = json.loads((tmp_path / ".synlynk" / "config.json").read_text())
    assert "codex" in cfg["workgroup_agents"]
    assert cfg["agent_slots"]["codex"] == "codex"
    assert cfg["roles"]["codex"] == ["implement", "test", "refactor"]

    import sqlite3

    db = sqlite3.connect(str(tmp_path / "state.db"))
    row = db.execute(
        "SELECT installed_version FROM harness_records WHERE agent_name='codex'"
    ).fetchone()
    db.close()
    assert row and row[0] == "1.2.3"


def test_cmd_agent_add_noop_when_fully_onboarded(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, workgroup_agents=["codex"], agent_slots={"codex": "codex"})
    ag_agents = tmp_path / "AGENTS.md"
    ag_agents.write_text(
        "# Codex\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\nbody\n<!-- /synlynk:harness -->\n"
    )
    stub = tmp_path / "codex"
    stub.write_text("#!/bin/sh\necho 'codex 1.2.3'\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    before = ag_agents.read_text()
    synlynk.cmd_agent_add("codex")
    after = ag_agents.read_text()
    out = capsys.readouterr().out

    assert "already fully onboarded" in out
    assert before == after


def test_cmd_agent_add_errors_when_binary_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    synlynk.cmd_agent_add("codex")
    out = capsys.readouterr().out
    assert "not on PATH" in out


def test_agent_add_cli_route(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(synlynk, "cmd_agent_add", lambda name: calls.append(name))

    old_argv = sys.argv
    sys.argv = ["synlynk", "agent", "add", "codex"]
    try:
        synlynk.main()
    finally:
        sys.argv = old_argv

    assert calls == ["codex"]
