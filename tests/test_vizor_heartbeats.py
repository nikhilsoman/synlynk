"""Daemon-home heartbeat store. Never touches ~/.synlynk/vizor-daemon."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from synlynk.viz.heartbeats import (
    daemon_id,
    open_heartbeats,
    read_beat,
    upsert_beat,
)


def _now():
    return datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def test_open_heartbeats_is_idempotent(tmp_path):
    first = open_heartbeats(tmp_path)
    first.close()
    second = open_heartbeats(tmp_path)
    try:
        tables = [
            row[0]
            for row in second.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
    finally:
        second.close()
    assert tables.count("daemon_heartbeats") == 1
    assert (tmp_path / "heartbeats.db").is_file()


def test_daemon_id_is_stable(tmp_path):
    first = daemon_id(tmp_path)
    second = daemon_id(tmp_path)
    assert first == second
    assert (tmp_path / "daemon_id").read_text().strip() == first


def test_upsert_replaces_the_single_row(tmp_path):
    upsert_beat(
        tmp_path,
        pid=os.getpid(),
        status="running",
        last_beat_at=_now(),
        cycle_count=1,
        active_task="idle",
    )
    upsert_beat(
        tmp_path,
        pid=os.getpid(),
        status="running",
        last_beat_at=_now(),
        cycle_count=2,
        active_task="acme",
    )
    conn = open_heartbeats(tmp_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM daemon_heartbeats").fetchone()[0]
        harness = conn.execute("SELECT harness FROM daemon_heartbeats").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert harness == "vizor"


def test_non_vizor_harness_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        upsert_beat(
            tmp_path,
            pid=os.getpid(),
            status="running",
            last_beat_at=_now(),
            cycle_count=1,
            active_task="idle",
            harness="codex",
        )


def test_dead_pid_is_reported_stale(tmp_path):
    dead = _dead_pid()
    upsert_beat(
        tmp_path,
        pid=dead,
        status="running",
        last_beat_at=_now(),
        cycle_count=3,
        active_task="idle",
    )
    row = read_beat(tmp_path, now=_now(), poll_interval_s=15)
    assert row["status"] == "stale"
    assert row["harness"] == "vizor"
    assert row["pid"] == dead


def test_fresh_live_pid_is_running(tmp_path):
    upsert_beat(
        tmp_path,
        pid=os.getpid(),
        status="running",
        last_beat_at=_now(),
        cycle_count=1,
        active_task="idle",
    )
    row = read_beat(tmp_path, now=_now(), poll_interval_s=15)
    assert row["status"] == "running"


def test_old_beat_is_stale(tmp_path):
    upsert_beat(
        tmp_path,
        pid=os.getpid(),
        status="running",
        last_beat_at=_now() - timedelta(seconds=31),
        cycle_count=1,
        active_task="idle",
    )
    row = read_beat(tmp_path, now=_now(), poll_interval_s=15)
    assert row["status"] == "stale"


def test_stopped_stays_stopped(tmp_path):
    upsert_beat(
        tmp_path,
        pid=_dead_pid(),
        status="stopped",
        last_beat_at=_now(),
        cycle_count=4,
        active_task="idle",
    )
    row = read_beat(tmp_path, now=_now(), poll_interval_s=15)
    assert row["status"] == "stopped"


def _dead_pid() -> int:
    for candidate in range(1_000_000, 1_000_200):
        try:
            os.kill(candidate, 0)
        except ProcessLookupError:
            return candidate
        except PermissionError:
            continue
    raise RuntimeError("no unused pid found")
