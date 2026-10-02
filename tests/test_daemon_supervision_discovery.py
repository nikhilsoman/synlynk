"""Tests for daemon service discoverability and auto-install prompt (#1883)."""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

from synlynk.doctor import _hc_daemon_service, HealthCheck
from synlynk.daemon import SynlynkDaemon


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
