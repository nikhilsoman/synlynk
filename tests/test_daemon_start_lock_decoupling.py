"""Regression coverage for the starter/lifetime flock deadlock (gh:#2262)."""

from __future__ import annotations

import time


def test_start_holds_a_separate_lock_while_child_acquires_lifetime_lock(
    tmp_path, monkeypatch, capsys
):
    """The re-exec child must never wait for its parent starter's flock."""
    import synlynk.daemon as daemon_mod

    daemon = daemon_mod.SynlynkDaemon()
    daemon.workspace_root = str(tmp_path)
    daemon.pidfile = str(tmp_path / "daemon.pid")
    daemon.logfile = str(tmp_path / "daemon.log")
    running = {"value": False}
    child_lock = {"fh": None}

    monkeypatch.setattr(daemon, "_prepare_start", lambda: None)
    monkeypatch.setattr(daemon, "_is_running", lambda: running["value"])

    def spawn_child(*_args, **_kwargs):
        child_lock["fh"] = daemon_mod._try_acquire_daemon_lock(
            daemon_mod._daemon_lock_path(daemon.pidfile), blocking=False
        )
        assert child_lock["fh"] is not None, "starter held the daemon lifetime lock"
        (tmp_path / "daemon.pid").write_text("12345\n")
        running["value"] = True

    monkeypatch.setattr(daemon_mod, "_daemonize_via_reexec", spawn_child)
    started_at = time.monotonic()
    try:
        daemon.start()
    finally:
        daemon_mod._release_daemon_lock(child_lock["fh"])

    assert time.monotonic() - started_at < 1.0
    assert "synlynk daemon started" in capsys.readouterr().out


def test_daemon_start_lock_path_is_distinct_from_lifetime_lock(tmp_path):
    import synlynk.daemon as daemon_mod

    pidfile = str(tmp_path / "daemon.pid")
    assert daemon_mod._daemon_start_lock_path(pidfile) != daemon_mod._daemon_lock_path(pidfile)
    assert daemon_mod._daemon_start_lock_path(pidfile).endswith(".start.lock")


def test_launchd_install_unloads_existing_registration_before_reload(tmp_path, monkeypatch):
    """A stale launchd registration must not make service installation fail."""
    import subprocess
    import synlynk.daemon as daemon_mod

    daemon = daemon_mod.SynlynkDaemon()
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(daemon_mod.sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(daemon_mod, "_daemon_package_path", lambda: str(tmp_path / "package"))
    monkeypatch.setattr(daemon_mod, "_daemon_caller_path", lambda: str(tmp_path / "workspace"))
    monkeypatch.setattr(daemon_mod, "_repo_common_dir", lambda *args, **kwargs: str(tmp_path / "workspace"))
    monkeypatch.setattr(daemon_mod.subprocess, "run", fake_run)

    daemon_mod._daemon_install_service(daemon)

    assert commands[0][0] == [
        "launchctl", "unload", str(tmp_path / "Library" / "LaunchAgents" / "com.synlynk.daemon.plist"),
    ]
    assert commands[0][1]["check"] is False
    assert commands[0][1]["capture_output"] is True
    assert commands[1][0][:3] == ["launchctl", "load", "-w"]
