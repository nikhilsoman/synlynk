"""Unit tests for Control Plane & Daemon Health (Sprint 2: #1523, #1537, #1535, #1538, #1520)."""

import json
import os
import sqlite3
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from synlynk.daemon import SynlynkDaemon, WatchDaemon, _daemon_lock_path
from synlynk.dispatch import _resolve_github_apps_dir
from synlynk.doctor import _check_dual_ledger_sync, _hc_dual_ledger_sync
from synlynk.github_app_auth import _resolve_private_key_path
from synlynk.probe import _write_through_fallback_db


def _git_run(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_resolve_github_apps_dir_in_git_worktree(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_run(["init"], repo)
    _git_run(["config", "user.email", "test@example.com"], repo)
    _git_run(["config", "user.name", "Test"], repo)
    (repo / "tracked.txt").write_text("tracked\n")
    _git_run(["add", "tracked.txt"], repo)
    _git_run(["commit", "-m", "initial"], repo)
    worktree = tmp_path / "worktree"
    _git_run(["worktree", "add", str(worktree)], repo)

    apps_dir = repo / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)

    monkeypatch.chdir(worktree)
    resolved = _resolve_github_apps_dir()
    assert os.path.isabs(resolved)
    assert resolved == str(apps_dir)


def test_resolve_private_key_path_daemon_root_and_project_root(tmp_path, monkeypatch):
    daemon_root = tmp_path / "main_repo"
    daemon_root.mkdir()
    keys_dir = daemon_root / ".synlynk" / "github_apps"
    keys_dir.mkdir(parents=True)
    key_file = keys_dir / "app.2026-01-01.private-key.pem"
    key_file.write_text("dummy-key")

    isolated_worktree = tmp_path / "worktree"
    isolated_worktree.mkdir()
    monkeypatch.chdir(isolated_worktree)

    # 1. Daemon workspace root env override
    monkeypatch.setenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", str(daemon_root))
    resolved = _resolve_private_key_path(".synlynk/github_apps/app.2026-01-01.private-key.pem")
    assert resolved == str(key_file)
    assert os.path.isabs(resolved)

    # 2. _project_root fallback when env unset
    monkeypatch.delenv("SYNLYNK_DAEMON_WORKSPACE_ROOT", raising=False)
    with patch("synlynk._project_root", return_value=str(daemon_root)):
        resolved2 = _resolve_private_key_path("app.2026-01-01.private-key.pem")
        assert resolved2 == str(key_file)


def test_synlynk_daemon_stop_cleans_stale_lock_when_no_pidfile(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile

    lock_path = _daemon_lock_path(pidfile)
    # Write a stale lockfile (with a dead PID)
    with open(lock_path, "w") as f:
        f.write("9999999\n")

    assert os.path.exists(lock_path)
    assert not os.path.exists(pidfile)

    daemon.stop()
    # Lockfile should be cleaned up
    assert not os.path.exists(lock_path)


def test_synlynk_daemon_stop_terminates_lock_owner_pid(tmp_path, monkeypatch):
    pidfile = str(tmp_path / "daemon.pid")
    daemon = SynlynkDaemon()
    daemon.pidfile = pidfile
    lock_path = _daemon_lock_path(pidfile)

    # Spawn a dummy sleep process
    proc = subprocess.Popen(["sleep", "60"])
    try:
        # Simulate pidfile missing but lockfile owning proc.pid
        with open(lock_path, "w") as f:
            f.write(f"{proc.pid}\n")

        assert daemon._health() == "running"

        daemon.stop()
        assert not os.path.exists(lock_path)
        # Process should have been killed
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_dual_ledger_sync_detection_and_write_through(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".synlynk").mkdir(parents=True)
    fallback_db = str(repo / ".synlynk" / "state.db")

    primary_dir = tmp_path / "user_state"
    primary_dir.mkdir(parents=True)
    primary_db = str(primary_dir / "state.db")

    for db_path in (primary_db, fallback_db):
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE harness_records (
                harness_name TEXT PRIMARY KEY,
                installed_version TEXT,
                compliance_status TEXT,
                active_contract TEXT,
                active_flags TEXT,
                capability_hash TEXT,
                last_probe_at TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    # Seed primary with v1, fallback with v1
    conn_p = sqlite3.connect(primary_db)
    conn_p.execute("INSERT INTO harness_records (harness_name, installed_version) VALUES ('codex', '0.1.0')")
    conn_p.commit()
    conn_p.close()

    conn_f = sqlite3.connect(fallback_db)
    conn_f.execute("INSERT INTO harness_records (harness_name, installed_version) VALUES ('codex', '0.1.0')")
    conn_f.commit()
    conn_f.close()

    with patch("synlynk.get_state_db_path", return_value=primary_db), \
         patch("synlynk._project_root", return_value=str(repo)):
        res = _check_dual_ledger_sync()
        assert res["passed"] is True
        assert res["detail"] == "synchronized"

        hc = _hc_dual_ledger_sync()
        assert hc.status == "ok"

        # Now induce drift on primary
        conn_p = sqlite3.connect(primary_db)
        conn_p.execute("UPDATE harness_records SET installed_version='0.2.0' WHERE harness_name='codex'")
        conn_p.commit()
        conn_p.close()

        res_drift = _check_dual_ledger_sync()
        assert res_drift["passed"] is False
        assert "codex" in res_drift["detail"]

        hc_drift = _hc_dual_ledger_sync()
        assert hc_drift.status == "warn"

        # Write-through to fallback DB
        _write_through_fallback_db("codex", "0.2.0", "ok", "{}", "{}", "hash", "2026-09-10T00:00:00Z")

        # Now both should be synchronized again
        res_synced = _check_dual_ledger_sync()
        assert res_synced["passed"] is True


def test_cli_probe_no_fence_flag(tmp_path, monkeypatch):
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["probe", "--no-fence"])
    assert args.command == "probe"
    assert args.no_fence is True

    args_default = parser.parse_args(["probe"])
    assert args_default.no_fence is False


def test_cli_watch_action_argument(tmp_path, monkeypatch):
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["watch", "status"])
    assert args.command == "watch"
    assert args.action == "status"

    args_start = parser.parse_args(["watch", "start"])
    assert args_start.action == "start"

    args_default = parser.parse_args(["watch"])
    assert args_default.action is None
