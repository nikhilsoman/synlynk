"""Unit tests for daemon resilience, supervisor heartbeat, and auto-rollups (Issues #5211 & #5215)."""

import os
import time
from unittest.mock import MagicMock, patch
import pytest

from synlynk.daemon import (
    SynlynkDaemon,
    check_daemon_health,
    _daemon_state_path,
)
from synlynk.tpm_sweep import post_proposal_interim_rollup


def test_daemon_heartbeat_updated_on_tick(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synlynk.daemon._repo_common_dir", lambda strict=True: str(tmp_path))
    os.makedirs(".synlynk", exist_ok=True)
    d = SynlynkDaemon()
    d.pidfile = str(tmp_path / ".synlynk" / "daemon.pid")

    # Record heartbeat
    d._record_heartbeat()
    hb_file = tmp_path / ".synlynk" / "daemon.heartbeat"
    assert hb_file.exists()
    ts = float(hb_file.read_text().strip())
    assert abs(ts - time.time()) < 2.0


def test_check_daemon_health_detects_flatline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synlynk.daemon._repo_common_dir", lambda strict=True: str(tmp_path))
    os.makedirs(".synlynk", exist_ok=True)
    sentinel_path = str(tmp_path / ".synlynk" / "sentinel.json")

    # Mock running daemon with an old heartbeat (>120s)
    pid_file = tmp_path / ".synlynk" / "daemon.pid"
    pid_file.write_text(str(os.getpid()))
    hb_file = tmp_path / ".synlynk" / "daemon.heartbeat"
    hb_file.write_text(str(time.time() - 300))  # 5 mins ago

    monkeypatch.setattr("synlynk.daemon._daemon_state_path", lambda name: str(tmp_path / ".synlynk" / name))
    monkeypatch.setattr("synlynk.daemon._probe_pidfile_health", lambda p: "running")

    alerts = []
    def fake_write_alert(level, code, msg, **kwargs):
        alerts.append((level, code, msg))

    monkeypatch.setattr("synlynk.daemon._write_sentinel_alert", fake_write_alert)

    check_daemon_health(sentinel_path=sentinel_path)
    flatline_alerts = [a for a in alerts if a[1] == "DAEMON_FLATLINE"]
    assert len(flatline_alerts) == 1
    assert "heartbeat flatlined" in flatline_alerts[0][2]


def test_daemon_loop_survives_autonomous_tick_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("synlynk.daemon._repo_common_dir", lambda strict=True: str(tmp_path))
    d = SynlynkDaemon(autonomous=True)
    d.pidfile = str(tmp_path / "daemon.pid")

    # Mock _autonomous_tick to raise an exception once then stop
    call_count = 0
    def exploding_tick():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Simulated autonomous tick database crash")

    monkeypatch.setattr(d, "_autonomous_tick", exploding_tick)

    # Run single iteration of protected tick
    success = d._safe_autonomous_tick()
    assert success is False
    assert call_count == 1
    # Daemon did not crash, caught gracefully


def test_post_proposal_interim_rollup_posts_to_active_proposal(tmp_path, monkeypatch):
    import synlynk as sl

    db_file = tmp_path / "state.db"
    conn = sl._get_db(str(db_file))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS approval_tickets (id INTEGER PRIMARY KEY, story_id TEXT, action TEXT, issue_url TEXT, status TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, readiness TEXT)")
        conn.execute("INSERT INTO approval_tickets (story_id, action, issue_url, status) VALUES ('v0.32.4', 'release_proposal', 'https://github.com/nikhilsoman/synlynk/issues/5219', 'open')")
        conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('story-1', 'Task 1', 'done', 'ready')")
        conn.execute("INSERT INTO stories (story_id, title, status, readiness) VALUES ('story-2', 'Task 2', 'open', 'ready')")
        conn.commit()

        captured = {}
        def fake_run_gh_as_role(role, args, **kwargs):
            captured["role"] = role
            captured["args"] = args
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "https://github.com/nikhilsoman/synlynk/issues/5219#issuecomment-999"
            return mock

        monkeypatch.setattr("synlynk.gh_role.run_gh_as_role", fake_run_gh_as_role)

        res = post_proposal_interim_rollup(
            story_id="story-1",
            pr_number=5221,
            pr_title="feat: implement task 1",
            status="merged",
            conn=conn,
        )
        assert res is not None
        assert captured["role"] == "tpm"
        assert "5219" in captured["args"]
        assert "PR #5221" in " ".join(captured["args"])
    finally:
        conn.close()
