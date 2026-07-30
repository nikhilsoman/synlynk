import os
import sqlite3

import pytest


class _DummySocket:
    def close(self):
        pass


def _make_stub_agent(tmp_path, name, version, version_output=None):
    script = tmp_path / name
    version_line = version_output or f"{name} {version}"
    script.write_text(
        f"""#!/bin/sh
case "$1" in
  --version) echo "{version_line}"; exit 0 ;;
  --help)    echo "  --flag  Example flag"; exit 0 ;;
  *)         echo "stub output"; exit 0 ;;
esac
"""
    )
    script.chmod(0o755)
    return script


def _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0", capability_hash="oldhash"):
    import synlynk

    conn = sqlite3.connect(str(db_path))
    synlynk._migrate_db(conn)
    conn.execute(
        """
        INSERT INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, 'ok', '{}', '{}', ?, datetime('now'))
        """,
        (agent_name, agent_name, installed_version, capability_hash),
    )
    conn.commit()
    conn.close()


def _read_installed_version(db_path, agent_name):
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT installed_version FROM harness_records WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_probe_clears_drift_alert_for_matching_agent(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [CRITICAL] [2026-07-15 10:01] OTHER_ALERT: leave this alone\n"
    )

    cmd_probe(agent="agy")

    content = sentinel_path.read_text()
    assert "HARNESS_VERSION_DRIFT" not in content
    assert "OTHER_ALERT" in content
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_leaves_other_agent_drift_alert_untouched(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'codex' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:01] OTHER_AGENT_ALERT: keep this too\n"
    )
    before = sentinel_path.read_text()

    cmd_probe(agent="agy")

    assert sentinel_path.read_text() == before
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_no_drift_alerts_is_noop_for_sentinel_state(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [INFO] [2026-07-15 10:00] VERIFY_SKIP: unrelated sentinel state\n"
    )
    before = sentinel_path.read_text()

    cmd_probe(agent="agy")

    assert sentinel_path.read_text() == before
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_clears_all_drift_alerts_for_same_agent(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="agy", installed_version="1.0.0")
    _make_stub_agent(tmp_path, "agy", "2.0.0")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    sentinel_path = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_path.write_text(
        "# Sentinel Alerts\n"
        "- [WARNING] [2026-07-15 10:00] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:01] HARNESS_VERSION_DRIFT: Agent 'agy' version changed: 2.0.0 -> 3.0.0. Run synlynk probe to update.\n"
        "- [WARNING] [2026-07-15 10:02] HARNESS_VERSION_DRIFT: Agent 'codex' version changed: 1.0.0 -> 2.0.0. Run synlynk probe to update.\n"
    )

    cmd_probe(agent="agy")

    content = sentinel_path.read_text()
    assert content.count("HARNESS_VERSION_DRIFT") == 1
    assert "Agent 'codex' version changed" in content
    assert "Agent 'agy' version changed" not in content
    assert _read_installed_version(db_path, "agy") == "2.0.0"


def test_probe_extracts_claude_version_from_descriptive_output(tmp_path, monkeypatch):
    import socket
    import synlynk
    from synlynk.probe import cmd_probe

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    db_path = tmp_path / ".synlynk" / "state.db"
    _seed_probe_db(db_path, agent_name="claude", installed_version="2.0.0")
    _make_stub_agent(tmp_path, "claude", "2.1.208", version_output="2.1.208 (Claude Code)")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: _DummySocket())
    monkeypatch.setattr(synlynk, "_get_db", lambda: sqlite3.connect(str(db_path)))

    cmd_probe(agent="claude")

    assert _read_installed_version(db_path, "claude") == "2.1.208"


# --- #287: Tier-2 model probe reads agent config files, not CLI version text ---


def _install_fake_home(tmp_path, monkeypatch):
    """Point ~ at tmp_path for isolated agent config probes."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # expanduser respects HOME on POSIX; also pin for safety on all platforms.
    real_expanduser = os.path.expanduser

    def _expand(path):
        if path.startswith("~/") or path == "~":
            return str(home / path[2:]) if path.startswith("~/") else str(home)
        return real_expanduser(path)

    monkeypatch.setattr(os.path, "expanduser", _expand)
    return home


def test_probe_model_version_codex_reads_config_toml(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        'model = "gpt-5.4-mini"\nmodel_reasoning_effort = "medium"\n'
    )

    assert _probe_model_version("codex", "codex") == "gpt-5.4-mini"


def test_probe_model_version_grok_reads_models_default(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    grok_dir = home / ".grok"
    grok_dir.mkdir()
    (grok_dir / "config.toml").write_text(
        '[cli]\ninstaller = "internal"\n\n[models]\ndefault = "grok-build"\n'
    )

    assert _probe_model_version("grok", "grok") == "grok-build"


def test_probe_model_version_agy_session_scoped(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    _install_fake_home(tmp_path, monkeypatch)
    # No config file required — agy has no persistent default model.
    result = _probe_model_version("agy", "agy")
    assert result == "session-scoped, no fixed default"


def test_probe_model_version_claude_reads_settings_model(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{\n  "model": "claude-sonnet-4-6",\n  "permissions": {}\n}\n'
    )

    assert _probe_model_version("claude", "claude") == "claude-sonnet-4-6"


def test_probe_model_version_claude_built_in_default_when_no_model_key(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"permissions": {}}\n')

    result = _probe_model_version("claude", "claude")
    assert result == "uses Claude Code's built-in default, no override"


def test_probe_model_version_claude_built_in_default_when_settings_missing(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    _install_fake_home(tmp_path, monkeypatch)
    result = _probe_model_version("claude", "claude")
    assert result == "uses Claude Code's built-in default, no override"


def test_probe_model_version_codex_unknown_when_config_missing(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    _install_fake_home(tmp_path, monkeypatch)
    assert _probe_model_version("codex", "codex") == "unknown"


def test_probe_model_version_grok_unknown_when_models_section_missing(tmp_path, monkeypatch):
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    grok_dir = home / ".grok"
    grok_dir.mkdir()
    (grok_dir / "config.toml").write_text('[cli]\ninstaller = "internal"\n')

    assert _probe_model_version("grok", "grok") == "unknown"


def test_probe_model_version_does_not_shell_out(tmp_path, monkeypatch):
    """Regression: old probe shelled out to CLI --version /status and scraped text."""
    import subprocess
    from synlynk.probe import _probe_model_version

    home = _install_fake_home(tmp_path, monkeypatch)
    codex_dir = home / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text('model = "gpt-5.4-mini"\n')

    def _boom(*a, **k):
        raise AssertionError("subprocess.run must not be called for model probe")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    assert _probe_model_version("codex", "codex") == "gpt-5.4-mini"
    assert _probe_model_version("agy", "agy") == "session-scoped, no fixed default"


def test_read_toml_string_value_top_level_and_section(tmp_path):
    from synlynk.probe import _read_toml_string_value

    path = tmp_path / "cfg.toml"
    path.write_text(
        'model = "gpt-test"\n\n[models]\ndefault = "grok-test"\nother = "x"\n'
    )
    assert _read_toml_string_value(str(path), "model") == "gpt-test"
    assert _read_toml_string_value(str(path), "default", section="models") == "grok-test"
    assert _read_toml_string_value(str(path), "missing") is None
    assert _read_toml_string_value(str(path / "nope"), "model") is None


def _make_repo_requirement_fixture(repo_path, requirements):
    if "docker" in requirements:
        (repo_path / "Dockerfile").write_text("FROM scratch\n")

    if "mcp" in requirements:
        (repo_path / ".mcp.json").write_text('{"name": "fixture"}\n')

    if "gh-actions" in requirements:
        workflows = repo_path / ".github" / "workflows"
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / "ci.yml").write_text("name: ci\n")


@pytest.mark.parametrize(
    ("requirements", "expected"),
    [
        (set(), set()),
        ({"docker"}, {"docker"}),
        ({"mcp"}, {"mcp"}),
        ({"gh-actions"}, {"gh-actions"}),
        ({"docker", "mcp"}, {"docker", "mcp"}),
        ({"docker", "gh-actions"}, {"docker", "gh-actions"}),
        ({"mcp", "gh-actions"}, {"mcp", "gh-actions"}),
        ({"docker", "mcp", "gh-actions"}, {"docker", "mcp", "gh-actions"}),
    ],
)
def test_scan_repo_requirements_detects_artifact_presence(tmp_path, requirements, expected):
    from synlynk.probe import _scan_repo_requirements

    repo = tmp_path / "repo"
    repo.mkdir()
    _make_repo_requirement_fixture(repo, requirements)

    assert _scan_repo_requirements(str(repo)) == expected
