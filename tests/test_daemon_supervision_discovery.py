"""Tests for daemon service discoverability and auto-install prompt (#1883)."""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

from synlynk.doctor import HEALTH_CHECKS, _hc_daemon_liveness, _hc_daemon_service, HealthCheck
from synlynk.daemon import SynlynkDaemon, check_daemon_health


def test_hc_daemon_service_warns_when_missing(tmp_path, monkeypatch):
    """When service file does not exist, doctor emits a warn with fix."""
    monkeypatch.setenv("HOME", str(tmp_path))
    hc = _hc_daemon_service()
    assert hc.status == "warn"
    assert "not registered" in hc.message
    assert "--install-service" in hc.fix


def test_hc_daemon_service_ok_when_installed(tmp_path, monkeypatch):
    """When service file exists, doctor reports ok."""
    monkeypatch.setenv("HOME", str(tmp_path))
    if sys.platform == "darwin":
        service_file = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service_file = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text("dummy")

    hc = _hc_daemon_service()
    assert hc.status == "ok"
    assert "installed" in hc.message


def test_daemon_status_hints_install_service_when_stopped(capsys):
    """synlynk daemon status prints install-service hint when not running."""
    daemon = SynlynkDaemon()
    with patch.object(daemon, "_is_running", return_value=False), \
         patch("os.path.exists", return_value=False):
        daemon.status()
    captured = capsys.readouterr()
    assert "daemon not running" in captured.out
    assert "synlynk daemon --install-service" in captured.out


def test_hc_daemon_liveness_in_health_checks_list():
    assert _hc_daemon_liveness in HEALTH_CHECKS


def test_hc_daemon_liveness_ok_when_running(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "daemon.pid").write_text(f"{os.getpid()}\n")
    hc = _hc_daemon_liveness()
    assert hc.status == "ok"
    assert "running" in hc.message


def test_hc_daemon_liveness_fails_on_zombie(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "daemon.pid").write_text("99999999\n")
    hc = _hc_daemon_liveness()
    assert hc.status == "fail"
    assert "pidfile exists but process is dead" in hc.message
    assert "daemon stop" in hc.fix


def test_hc_daemon_liveness_fails_when_service_installed_but_stopped(tmp_path, monkeypatch):
    """gh:#2261: installed unit + dead detached child must fail doctor."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    if sys.platform == "darwin":
        service_file = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service_file = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text("dummy")

    hc = _hc_daemon_liveness()
    assert hc.status == "fail"
    assert "service is installed" in hc.message
    assert "daemon start" in hc.fix


def test_check_daemon_health_alerts_on_dead_synlynk_daemon(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "daemon.pid").write_text("99999999\n")
    sentinel = str(tmp_path / ".synlynk" / "sentinel.md")

    check_daemon_health(sentinel_path=sentinel)

    out = capsys.readouterr().out
    assert "ZOMBIE_SYNLYNK_DAEMON" in out
    assert "ZOMBIE_SYNLYNK_DAEMON" in open(sentinel).read()


def test_check_daemon_health_alerts_when_service_installed_but_stopped(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    if sys.platform == "darwin":
        service_file = tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"
    else:
        service_file = tmp_path / ".config" / "systemd" / "user" / "synlynk-daemon.service"
    service_file.parent.mkdir(parents=True, exist_ok=True)
    service_file.write_text("dummy")
    sentinel = str(tmp_path / ".synlynk" / "sentinel.md")
    monkeypatch.setattr(
        "synlynk.daemon._daemon_service_registration", lambda: False
    )

    check_daemon_health(sentinel_path=sentinel)

    out = capsys.readouterr().out
    assert "DAEMON_DETACHED_DEAD" in out
    assert "DAEMON_DETACHED_DEAD" in open(sentinel).read()
