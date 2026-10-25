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

import synlynk.daemon as daemon_module
from synlynk.daemon import (
    SynlynkDaemon,
    WatchDaemon,
    _daemon_lock_path,
    _try_acquire_daemon_lock,
    _release_daemon_lock,
)


def test_health_snapshot_classifies_absent_pid_with_verified_lock(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    lock_fh = _try_acquire_daemon_lock(_daemon_lock_path(pidfile), blocking=False)
    assert lock_fh is not None
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)
    try:
        health = daemon._health_snapshot()
        assert (health.state, health.pid, health.pidfile_state) == (
            "degraded",
            4242,
            "absent",
        )
    finally:
        _release_daemon_lock(lock_fh)


def test_health_snapshot_ignores_unheld_lock_with_live_pid(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    with open(_daemon_lock_path(pidfile), "w") as fh:
        fh.write("4242\n")
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)

    health = daemon._health_snapshot()

    assert (health.state, health.pid, health.pidfile_state) == (
        "stopped",
        None,
        "absent",
    )


def test_health_snapshot_classifies_malformed_pid_without_owner(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as fh:
        fh.write("not-a-pid\n")
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: None)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda _pid: False)

    health = daemon._health_snapshot()

    assert (health.state, health.pid, health.pidfile_state) == (
        "zombie",
        None,
        "malformed",
    )


def test_health_snapshot_preserves_valid_live_pid(tmp_path):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    with open(pidfile, "w") as fh:
        fh.write(f"{os.getpid()}\n")

    health = daemon._health_snapshot()

    assert (health.state, health.pid, health.pidfile_state) == (
        "running",
        os.getpid(),
        "valid",
    )


def test_daemon_lock_probe_detects_held_lock_without_mutating_pid(tmp_path):
    lock_path = str(tmp_path / "watch.pid.lock")
    lock_fh = _try_acquire_daemon_lock(lock_path, blocking=False)
    assert lock_fh is not None
    try:
        with open(lock_path, "rb") as fh:
            before = fh.read()
        assert daemon_module._daemon_lock_is_held(lock_path) is True
        with open(lock_path, "rb") as fh:
            assert fh.read() == before
    finally:
        _release_daemon_lock(lock_fh)

    assert daemon_module._daemon_lock_is_held(lock_path) is False


def test_watch_status_reports_degraded_without_pidfile(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    lock_fh = _try_acquire_daemon_lock(_daemon_lock_path(pidfile), blocking=False)
    assert lock_fh is not None
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)
    try:
        daemon.status()
    finally:
        _release_daemon_lock(lock_fh)

    output = capsys.readouterr().out
    assert "watch degraded" in output
    assert "4242" in output


def test_watch_stop_signals_verified_lock_owner_without_pidfile(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    lock_fh = _try_acquire_daemon_lock(_daemon_lock_path(pidfile), blocking=False)
    assert lock_fh is not None
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)
    sent = []
    monkeypatch.setattr(
        daemon_module.os, "kill", lambda pid, sig: sent.append((pid, sig))
    )
    monkeypatch.setattr(daemon_module, "_pkg", lambda _name: lambda *_args: None)
    try:
        daemon.stop()
    finally:
        _release_daemon_lock(lock_fh)

    assert sent == [(4242, 15)]
    assert "watch stopped" in capsys.readouterr().out


def test_watch_stop_does_not_signal_unheld_lock_metadata(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    with open(_daemon_lock_path(pidfile), "w") as fh:
        fh.write("4242\n")
    monkeypatch.setattr(daemon_module, "_daemon_lock_owner_pid", lambda _path: 4242)
    monkeypatch.setattr(daemon_module, "_pid_is_alive", lambda pid: pid == 4242)
    sent = []
    monkeypatch.setattr(
        daemon_module.os, "kill", lambda pid, sig: sent.append((pid, sig))
    )
    monkeypatch.setattr(daemon_module, "_pkg", lambda _name: lambda *_args: None)

    daemon.stop()

    assert sent == []
    assert "watch is not running" in capsys.readouterr().out


def test_watch_status_preserves_pidfile_published_after_health_snapshot(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = str(tmp_path / "watch.log")
    original_snapshot = daemon._health_snapshot
    lifetime_lock = [None]

    def snapshot_then_start_daemon():
        health = original_snapshot()
        lifetime_lock[0] = _try_acquire_daemon_lock(
            _daemon_lock_path(pidfile), blocking=False
        )
        assert lifetime_lock[0] is not None
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")
        return health

    monkeypatch.setattr(daemon, "_health_snapshot", snapshot_then_start_daemon)
    try:
        daemon.status()
        assert os.path.exists(pidfile)
        assert "left pidfile untouched" in capsys.readouterr().out
    finally:
        _release_daemon_lock(lifetime_lock[0])


def test_watch_stop_preserves_pidfile_published_after_health_snapshot(
    tmp_path, monkeypatch, capsys
):
    pidfile = str(tmp_path / "watch.pid")
    daemon = WatchDaemon()
    daemon.pidfile = pidfile
    daemon.logfile = str(tmp_path / "watch.log")
    original_snapshot = daemon._health_snapshot
    lifetime_lock = [None]

    def snapshot_then_start_daemon():
        health = original_snapshot()
        lifetime_lock[0] = _try_acquire_daemon_lock(
            _daemon_lock_path(pidfile), blocking=False
        )
        assert lifetime_lock[0] is not None
        with open(pidfile, "w") as f:
            f.write(f"{os.getpid()}\n")
        return health

    monkeypatch.setattr(daemon, "_health_snapshot", snapshot_then_start_daemon)
    monkeypatch.setattr(daemon_module, "_pkg", lambda _name: lambda *_args: None)
    try:
        daemon.stop()
        assert os.path.exists(pidfile)
        assert "left pidfile untouched" in capsys.readouterr().out
    finally:
        _release_daemon_lock(lifetime_lock[0])


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

    # Isolate HTTP_PORT to an ephemeral port to avoid colliding with live daemons
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        test_port = probe.getsockname()[1]
    monkeypatch.setattr(daemon, "HTTP_PORT", test_port)

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

    # xdist workers run this test concurrently.  Give each worker an isolated
    # port so one worker cannot reclaim another worker's orphan process.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        test_port = probe.getsockname()[1]
    monkeypatch.setattr(daemon, "HTTP_PORT", test_port)

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
