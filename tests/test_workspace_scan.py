import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import synlynk


def test_write_workspace_config_creates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    scan = {
        "workspace_name": "my-ws",
        "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "myrepo",
                   "stack_labels": ["Python"], "readme_excerpt": "",
                   "context_sections": {}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/usr/bin/claude"}],
        "agents": [], "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    config_path = synlynk.write_workspace_config(scan, "my-ws")
    assert os.path.exists(config_path)
    import json
    data = json.loads(open(config_path).read())
    assert data["workspace_name"] == "my-ws"
    assert data["home_harness"] == "claude"
    assert len(data["repos"]) == 1


def test_generate_structured_context_has_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    scan = {
        "workspace_name": "test-ws",
        "topology": "single",
        "repos": [{"path": str(tmp_path), "name": "testrepo",
                   "stack_labels": ["Python"], "readme_excerpt": "A test repo.",
                   "context_sections": {"Your Role": "You are PM."}}],
        "harnesses": [{"name": "claude", "cli": "claude",
                       "version": "1.x", "path": "/usr/bin/claude"}],
        "agents": [{"name": "claude", "version": "1.x",
                    "functional": True, "roles": ["PM"]}],
        "skills": [], "home_harness": "claude",
        "scanned_at": "2026-07-01T10:00:00",
    }
    out_path = str(tmp_path / ".synlynk" / "context.md")
    result = synlynk.generate_structured_context(scan, out_path=out_path)
    assert "# synlynk context" in result
    assert "test-ws" in result
    assert "testrepo" in result
    assert "Python" in result
    assert os.path.exists(out_path)


def test_cmd_scan_no_flags_runs_workspace_scan(tmp_path, monkeypatch, capsys):
    """synlynk scan (no flags) runs workspace scan and prints summary."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan()
    captured = capsys.readouterr()
    assert "workspace" in captured.out.lower() or "scan" in captured.out.lower()


def test_cmd_scan_dry_run_no_writes(tmp_path, monkeypatch):
    """--dry-run does not write config.json."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(dry_run=True)
    ws_dir = tmp_path / ".synlynk" / "workspaces"
    assert not ws_dir.exists()


def test_cmd_scan_add_appends_repo(tmp_path, monkeypatch, capsys):
    """--add <path> appends a repo to existing workspace config."""
    ws_dir = tmp_path / ".synlynk" / "workspaces" / "test-ws"
    ws_dir.mkdir(parents=True)
    import json
    config = {"workspace_name": "test-ws", "topology": "single",
              "home_harness": "claude", "repos": [], "agent_roles": {},
              "created_at": "", "last_scanned_at": ""}
    (ws_dir / "config.json").write_text(json.dumps(config))
    (tmp_path / "newrepo").mkdir()
    (tmp_path / "newrepo" / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(synlynk, "discover_agents", lambda config=None: [])
    synlynk.cmd_scan(add_path=str(tmp_path / "newrepo"),
                     workspace_name="test-ws")
    data = json.loads((ws_dir / "config.json").read_text())
    assert any(r["name"] == "newrepo" for r in data["repos"])


def test_synlynk_scan_dry_run_cli(tmp_path, monkeypatch):
    import subprocess as sp
    (tmp_path / '.git').mkdir()
    (tmp_path / 'pyproject.toml').write_text("[project]\nname='test'")
    (tmp_path / '.synlynk').mkdir()
    env = os.environ.copy()
    env['HOME'] = str(tmp_path)
    env['PYTHONPATH'] = os.pathsep.join([
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
        env.get('PYTHONPATH', ''),
    ]).rstrip(os.pathsep)
    result = sp.run(
        ['python', '-m', 'synlynk', 'scan', '--dry-run'],
        cwd=str(tmp_path),
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert 'dry-run' in result.stdout or 'scan' in result.stdout
