"""Regression tests for gh:#2261 — refuse disposable daemonize cwd + self-health-check."""

import sys
from unittest.mock import patch

import pytest

import synlynk.daemon as daemon_mod
from synlynk.daemon import (
    SynlynkDaemon,
    _daemonize_via_reexec,
    check_daemon_health,
)
from synlynk.doctor import _hc_daemon_service
from synlynk.sentinel import _read_sentinel_alerts


def test_daemonize_via_reexec_refuses_disposable_worktree_cwd(tmp_path):
    disposable = tmp_path / "worktrees" / "job-597c6896"
    disposable.mkdir(parents=True)
    logfile = str(tmp_path / "daemon.log")

    with pytest.raises(RuntimeError, match="disposable worktree"):
        _daemonize_via_reexec(
            "synlynk.daemon._synlynk_daemon_child_main",
            logfile,
            cwd=str(disposable),
        )


def test_daemonize_via_reexec_defaults_away_from_disposable_cwd(tmp_path, monkeypatch):
    """When cwd is omitted, resolve via _repo_common_dir — never inherit a disposable cwd."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    disposable = tmp_path / "worktrees" / "job-dead"
    disposable.mkdir(parents=True)
    monkeypatch.chdir(disposable)

    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(daemon_mod.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(repo_root)
    )

    logfile = str(repo_root / "daemon.log")
    _daemonize_via_reexec("synlynk.daemon._synlynk_daemon_child_main", logfile)

    assert captured["kwargs"]["cwd"] == str(repo_root)
    assert captured["kwargs"]["env"]["SYNLYNK_DAEMON_WORKSPACE_ROOT"] == str(repo_root)


def test_check_daemon_health_detects_zombie_synlynk_daemon(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "daemon.pid").write_text("99999999\n")
    sentinel = str(synlynk_dir / "sentinel.md")

    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(tmp_path)
    )

    check_daemon_health(sentinel_path=sentinel)

    alerts = _read_sentinel_alerts(severity="CRITICAL", sentinel_path=sentinel)
    assert any("ZOMBIE_DAEMON" in a for a in alerts)
    assert any("Synlynk daemon" in a or "daemon pidfile" in a.lower() for a in alerts)


def test_check_daemon_health_alerts_when_service_installed_but_stopped(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    sentinel = str(synlynk_dir / "sentinel.md")

    if sys.platform == "darwin":
        service = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text("dummy")

    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(tmp_path)
    )

    check_daemon_health(sentinel_path=sentinel)

    alerts = _read_sentinel_alerts(severity="CRITICAL", sentinel_path=sentinel)
    assert any("DAEMON_SERVICE_UNHEALTHY" in a for a in alerts)


def test_hc_daemon_service_warns_when_installed_but_process_unhealthy(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)

    if sys.platform == "darwin":
        service = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text("dummy")

    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(tmp_path)
    )

    with patch.object(SynlynkDaemon, "_health", return_value="stopped"):
        hc = _hc_daemon_service()

    assert hc.status == "warn"
    assert "not running" in hc.message.lower() or "not healthy" in hc.message.lower()
    assert "daemon start" in hc.fix or "--install-service" in hc.fix


def test_hc_daemon_service_ok_when_installed_and_running(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)

    if sys.platform == "darwin":
        service = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service.parent.mkdir(parents=True, exist_ok=True)
    service.write_text("dummy")

    monkeypatch.setattr(
        daemon_mod, "_repo_common_dir", lambda *, strict=False: str(tmp_path)
    )

    with patch.object(SynlynkDaemon, "_health", return_value="running"):
        hc = _hc_daemon_service()

    assert hc.status == "ok"
    assert "installed" in hc.message.lower()
