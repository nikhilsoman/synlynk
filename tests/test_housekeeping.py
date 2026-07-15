"""Tests for the daily housekeeping drift check."""

import json
import os
from datetime import date, timedelta

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
        "agent_slots": {"claude": "claude"},
        "workgroup_agents": ["claude"],
        "last_housekeeping_date": None,
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
        "stall_timeout_minutes": 30,
        "agents": {},
        "roles": {"claude": ["pm", "review", "deploy"]},
    }
    config.update(overrides)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))


def _write_stub(tmp_path, name):
    stub = tmp_path / name
    stub.write_text(
        f"""#!/bin/sh
case "$1" in
  --version) echo '{name} 1.0.0'; exit 0 ;;
  --help) echo '  --flag  help'; exit 0 ;;
  *) echo 'stub'; exit 0 ;;
esac
"""
    )
    stub.chmod(0o755)
    return stub


def test_daily_housekeeping_triggers_on_new_day_and_updates_date(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _write_config(tmp_path, last_housekeeping_date=yesterday, workgroup_agents=["claude"])
    _write_stub(tmp_path, "claude")
    _write_stub(tmp_path, "grok")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    calls = []

    def fake_probe(agent_name, db_conn, write_fence=False):
        calls.append(agent_name)
        return {"skipped": False, "version": "1.0.0", "status": "ok"}

    monkeypatch.setattr(synlynk, "_probe_agent", fake_probe)
    monkeypatch.setattr(synlynk, "_repair_sops_only", lambda *args, **kwargs: None)

    synlynk._run_daily_housekeeping()

    out = capsys.readouterr().out
    cfg = json.loads((tmp_path / ".synlynk" / "config.json").read_text())

    assert "New agent detected on PATH: grok" in out
    assert calls == ["claude"]
    assert cfg["last_housekeeping_date"] == date.today().isoformat()


def test_daily_housekeeping_does_not_rerun_same_day(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    today = date.today().isoformat()
    _write_config(tmp_path, last_housekeeping_date=today, workgroup_agents=["claude"])
    _write_stub(tmp_path, "claude")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    calls = []

    def fake_probe(agent_name, db_conn, write_fence=False):
        calls.append(agent_name)
        return {"skipped": False, "version": "1.0.0", "status": "ok"}

    monkeypatch.setattr(synlynk, "_probe_agent", fake_probe)
    monkeypatch.setattr(synlynk, "_repair_sops_only", lambda *args, **kwargs: None)

    synlynk._run_daily_housekeeping()

    out = capsys.readouterr().out
    assert out == ""
    assert calls == []


def test_daily_housekeeping_is_silent_when_nothing_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _write_config(tmp_path, last_housekeeping_date=yesterday, workgroup_agents=["claude"])
    _write_stub(tmp_path, "claude")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    monkeypatch.setattr(
        synlynk,
        "_detect_harnesses_on_path",
        lambda: [{"name": "claude", "cli": "claude", "version": "1.0.0", "path": str(tmp_path / "claude")}],
    )

    monkeypatch.setattr(
        synlynk,
        "_probe_agent",
        lambda *args, **kwargs: {"skipped": True, "version": "1.0.0", "status": "ok"},
    )
    monkeypatch.setattr(synlynk, "_repair_sops_only", lambda *args, **kwargs: None)

    synlynk._run_daily_housekeeping()

    out = capsys.readouterr().out
    cfg = json.loads((tmp_path / ".synlynk" / "config.json").read_text())

    assert out == ""
    assert cfg["last_housekeeping_date"] == date.today().isoformat()
