"""Regression tests for gh:#2333 — false 'Failed to start' from racy pidfile
wait + stale logfile tail, and false 'watch is also running' on a dead pidfile.
"""

from __future__ import annotations

import inspect
import os
import time

import pytest

from synlynk import daemon as daemon_mod
from synlynk.daemon import SynlynkDaemon, WatchDaemon


STALE_ERROR = "SystemExit: 143"


def test_start_does_not_report_stale_logfile_error_when_child_silent(
    tmp_path, monkeypatch, capsys
):
    """Pre-seeded old log lines must not become today's Failed-to-start message.

    Even when the pidfile-wait race is lost (child never publishes readiness in
    time), a quiet start attempt that appends nothing to the log must report an
    honest readiness-timeout message instead of the stale tail.
    """
    logfile = tmp_path / "daemon.log"
    logfile.write_text(
        "2026-10-01 diagnostic leftover\n"
        f"{STALE_ERROR}\n"
        "Traceback (most recent call last):\n"
    )

    daemon = SynlynkDaemon()
    daemon.pidfile = str(tmp_path / "daemon.pid")
    daemon.logfile = str(logfile)
    daemon.workspace_root = str(tmp_path)

    # Spawn succeeds as a process, but never writes a pidfile — race lost.
    monkeypatch.setattr(daemon_mod, "_daemonize_via_reexec", lambda *a, **k: None)
    # Keep the await short so the test stays fast; the watermark fix is what
    # this assertion cares about, not the absolute timeout ceiling.
    monkeypatch.setattr(
        SynlynkDaemon,
        "_await_child_pidfile",
        lambda self, timeout=2.0: None,
    )

    daemon.start()

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert STALE_ERROR not in combined
    assert "Failed to start" in combined
    assert "no error output produced" in combined.lower() or (
        "did not report readiness" in combined.lower()
    )


def test_await_child_pidfile_uses_backoff_beyond_flat_two_seconds(tmp_path, monkeypatch):
    """Pidfile wait must keep polling with backoff past a flat 2.0s cutoff."""
    daemon = WatchDaemon()
    daemon.pidfile = str(tmp_path / "watch.pid")
    daemon.logfile = str(tmp_path / "watch.log")

    clock = {"now": 0.0}
    sleeps: list[float] = []
    become_ready_at = 2.5  # would lose a flat 2.0s race

    def fake_time():
        return clock["now"]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    def fake_is_running():
        return clock["now"] >= become_ready_at

    monkeypatch.setattr(time, "time", fake_time)
    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(daemon, "_is_running", fake_is_running)

    daemon._await_child_pidfile()

    assert clock["now"] >= become_ready_at
    assert sleeps, "expected backoff sleeps while waiting for pidfile"
    # Delay should grow beyond the initial 50ms poll at least once.
    assert max(sleeps) > 0.05

    default_timeout = inspect.signature(
        daemon_mod.WatchDaemon._await_child_pidfile
    ).parameters["timeout"].default
    assert default_timeout > 2.0


def test_prepare_start_ignores_stale_watch_pidfile(tmp_path, monkeypatch, capsys):
    """Dead watch.pid must not trigger 'synlynk watch is also running'."""
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "watch.pid").write_text("99999999\n")  # guaranteed-dead PID

    daemon = SynlynkDaemon()
    daemon.workspace_root = str(tmp_path)
    daemon.pidfile = str(synlynk_dir / "daemon.pid")
    daemon.logfile = str(synlynk_dir / "daemon.log")

    daemon._prepare_start()

    out = capsys.readouterr().out
    assert "watch is also running" not in out


def test_prepare_start_warns_when_watch_process_is_alive(tmp_path, monkeypatch, capsys):
    """A live watch pidfile should still warn about dual pollers."""
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "watch.pid").write_text(f"{os.getpid()}\n")

    daemon = SynlynkDaemon()
    daemon.workspace_root = str(tmp_path)
    daemon.pidfile = str(synlynk_dir / "daemon.pid")
    daemon.logfile = str(synlynk_dir / "daemon.log")

    daemon._prepare_start()

    out = capsys.readouterr().out
    assert "watch is also running" in out


def test_start_reports_only_new_logfile_bytes_on_failure(tmp_path, monkeypatch, capsys):
    """If the child does append during this attempt, report that new line only."""
    logfile = tmp_path / "daemon.log"
    logfile.write_text(f"old leftover\n{STALE_ERROR}\n")

    daemon = SynlynkDaemon()
    daemon.pidfile = str(tmp_path / "daemon.pid")
    daemon.logfile = str(logfile)
    daemon.workspace_root = str(tmp_path)

    fresh_error = "ImportError: boom during this start"

    def fake_daemonize(entry_point, log_path, cwd=None):
        with open(log_path, "a") as fh:
            fh.write(fresh_error + "\n")

    monkeypatch.setattr(daemon_mod, "_daemonize_via_reexec", fake_daemonize)
    monkeypatch.setattr(
        SynlynkDaemon,
        "_await_child_pidfile",
        lambda self, timeout=2.0: None,
    )

    daemon.start()

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert fresh_error in combined
    assert STALE_ERROR not in combined
    assert "Failed to start daemon:" in combined
