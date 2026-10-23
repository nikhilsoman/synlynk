"""Regression tests for synlynk issue #2553:
SynlynkDaemon.status() crashes with FileNotFoundError when the daemon is
alive via lock-owner or HTTP-port evidence but its pidfile is absent --
the same fingerprint #2544 fixed for WatchDaemon, now closed for
SynlynkDaemon's own _health() override.
"""

import os
import socket

import synlynk.daemon as daemon_module
from synlynk.daemon import (
    SynlynkDaemon,
    _daemon_lock_path,
    _try_acquire_daemon_lock,
    _release_daemon_lock,
)


def _isolated_http_port(daemon, monkeypatch):
    """Point daemon.HTTP_PORT at a port this test controls (LIVE-25, gh:#2329):
    the real default must never be probed by a test's port-listener fallback.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        test_port = probe.getsockname()[1]
    monkeypatch.setattr(daemon, "HTTP_PORT", test_port)
    return test_port


def test_resolve_live_pid_prefers_valid_pidfile(tmp_path):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as f:
        f.write(f"{os.getpid()}\n")

    assert daemon._resolve_live_pid() == os.getpid()


def test_resolve_live_pid_falls_back_to_lock_owner_when_pidfile_absent(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    assert not os.path.exists(pidfile)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)

    assert daemon._resolve_live_pid() == 4242


def test_resolve_live_pid_falls_back_to_port_listener_when_no_pidfile_or_lock(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 5150)
    monkeypatch.setattr(daemon_module, "_find_pid_listening_on_port", lambda port: 5150)

    assert daemon._resolve_live_pid() == 5150


def test_resolve_live_pid_returns_none_when_no_evidence(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    _isolated_http_port(daemon, monkeypatch)

    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(daemon_module, "_find_pid_listening_on_port", lambda port: None)

    assert daemon._resolve_live_pid() is None


def test_print_not_running_cleans_stale_pidfile(tmp_path, capsys):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as f:
        f.write("99999999\n")  # certainly-dead PID

    daemon._print_not_running()

    output = capsys.readouterr().out
    assert "daemon not running" in output
    assert "stale pidfile cleaned" in output
    assert not os.path.exists(pidfile)
