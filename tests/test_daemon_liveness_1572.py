"""Reproduction and regression tests for synlynk issue #1572:
Daemon start/status report false 'already running' with no live process.
"""

import os
import socket
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from synlynk.daemon import (
    SynlynkDaemon,
    WatchDaemon,
    _daemon_lock_path,
    _try_acquire_daemon_lock,
    _release_daemon_lock,
)


def test_daemon_health_ignores_own_pid_in_lockfile(tmp_path):
    """When lockfile holds caller's os.getpid() during start, _health must NOT report running."""
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    lock_path = _daemon_lock_path(pidfile)

    # 1. pidfile does not exist, lockfile holds current process PID
    lock_fh = _try_acquire_daemon_lock(lock_path, blocking=False)
    assert lock_fh is not None
    try:
        # Before fix, _health() saw os.getpid() in lock_path and returned "running"
        assert daemon._health() == "stopped"
    finally:
        _release_daemon_lock(lock_fh)

    # 2. pidfile exists with dead PID, lockfile holds current process PID
    with open(pidfile, "w") as f:
        f.write("99999999\n")
    lock_fh = _try_acquire_daemon_lock(lock_path, blocking=False)
    assert lock_fh is not None
    try:
        # Before fix, _health() saw os.getpid() in lock_path and returned "running" instead of "zombie"
        assert daemon._health() == "zombie"
    finally:
        _release_daemon_lock(lock_fh)


def test_watch_status_cleans_dead_pid_and_start_succeeds(tmp_path, monkeypatch, capsys):
    """A dead pidfile is reported as stopped and does not block the next start."""
    pidfile = str(tmp_path / "watch.pid")
    logfile = str(tmp_path / "watch.log")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = logfile

    with open(pidfile, "w") as f:
        f.write("99999999\n")

    daemon.status()
    status_output = capsys.readouterr().out
    assert "watch stopped" in status_output
    assert "watch running" not in status_output
    assert not os.path.exists(pidfile)

    spawned = []

    def fake_daemonize(entry_point, log_path, cwd=None):
        spawned.append(entry_point)
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")

    monkeypatch.setattr("synlynk.daemon._daemonize_via_reexec", fake_daemonize)
    daemon.start()

    start_output = capsys.readouterr().out
    assert "already running" not in start_output
    assert "started" in start_output
    assert len(spawned) == 1


def test_daemon_start_does_not_self_deadlock(tmp_path, monkeypatch, capsys):
    """daemon.start() without mock on _is_running must not self-abort as 'already running'."""
    pidfile = str(tmp_path / "daemon.pid")
    logfile = str(tmp_path / "daemon.log")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = logfile

    spawned = []

    def fake_daemonize(entry_point, log_path, cwd=None):
        spawned.append(entry_point)
        # Simulate child writing pidfile with a fake child PID
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")

    monkeypatch.setattr("synlynk.daemon._daemonize_via_reexec", fake_daemonize)
    daemon.start()

    out = capsys.readouterr().out
    assert "already running" not in out
    assert len(spawned) == 1
    assert "started" in out


def test_watch_start_does_not_self_deadlock(tmp_path, monkeypatch, capsys):
    """watch.start() without mock on _is_running must not self-abort as 'already running'."""
    pidfile = str(tmp_path / "watch.pid")
    logfile = str(tmp_path / "watch.log")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = logfile

    spawned = []

    def fake_daemonize(entry_point, log_path, cwd=None):
        spawned.append(entry_point)
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")

    monkeypatch.setattr("synlynk.daemon._daemonize_via_reexec", fake_daemonize)
    daemon.start()

    out = capsys.readouterr().out
    assert "already running" not in out
    assert len(spawned) == 1
    assert "started" in out


def test_daemon_restart_when_not_running(tmp_path, monkeypatch, capsys):
    """synlynk daemon restart when stopped must not output self-contradictory messages."""
    pidfile = str(tmp_path / "daemon.pid")
    logfile = str(tmp_path / "daemon.log")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = logfile

    spawned = []

    def fake_daemonize(entry_point, log_path, cwd=None):
        spawned.append(entry_point)
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")

    monkeypatch.setattr("synlynk.daemon._daemonize_via_reexec", fake_daemonize)

    # Simulate: daemon.stop() then daemon.start()
    daemon.stop()
    daemon.start()

    out = capsys.readouterr().out
    # Must NOT say "already running"
    assert "already running" not in out
    assert len(spawned) == 1
    assert "started" in out


def test_daemon_run_loop_handles_port_conflict(tmp_path, monkeypatch):
    """When HTTP port is in use, _run_loop must not crash with unhandled exception."""
    pidfile = str(tmp_path / "daemon.pid")
    logfile = str(tmp_path / "daemon.log")
    sentinel = str(tmp_path / "sentinel.md")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = logfile
    daemon.sentinel_path = sentinel

    # Bind the daemon HTTP port to simulate another process holding it
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", daemon.HTTP_PORT))
    sock.listen(1)

    with open(pidfile, "w") as f:
        f.write(f"{os.getpid()}\n")

    try:
        # Before fix, this would raise OSError [Errno 48] Address already in use
        # and crash unhandled, leaving behind stale pidfile.
        # With fix, it catches the error, cleans up pidfile, and returns cleanly.
        daemon._run_loop()
        assert not os.path.exists(pidfile)
    finally:
        sock.close()


def test_daemon_stop_kills_orphaned_process_on_http_port(tmp_path, monkeypatch):
    """When pidfile is missing but an orphan listens on HTTP_PORT, stop() reclaims it."""
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile

    # Spawn an orphan process that binds HTTP_PORT
    orphan_code = (
        f"import socket, time; "
        f"s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); "
        f"s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); "
        f"s.bind(('127.0.0.1', {daemon.HTTP_PORT})); "
        f"s.listen(1); "
        f"time.sleep(30)"
    )
    proc = subprocess.Popen([sys.executable, "-c", orphan_code])
    time.sleep(0.3)
    try:
        assert proc.poll() is None
        # stop() should detect the orphan process listening on HTTP_PORT and kill it
        daemon.stop()
        # Verify orphan process was terminated
        for _ in range(20):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
