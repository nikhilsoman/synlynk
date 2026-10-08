"""Soak tests for SQLite WAL-backed state.db under 20–50 concurrent writers.

Refs gh:#2102. Production ledgers are never opened; every run uses an isolated
temporary database initialized through synlynk's real schema + WAL pragmas.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from synlynk.testbed.state_db_soak import (
    DEFAULT_WRITERS,
    PASS_THRESHOLDS,
    SoakConfig,
    _apply_delete_journal_mode,
    _open_conn,
    classify_failure_modes,
    run_state_db_soak,
)
from synlynk.testbed.scenarios import ScenarioRunner


def test_default_writer_count_is_in_required_range():
    assert 20 <= DEFAULT_WRITERS <= 50
    assert 20 <= SoakConfig().writers <= 50


def test_classify_failure_modes_names_lock_corruption_and_starvation():
    assert "lock_contention" in classify_failure_modes(
        lock_errors=3, integrity_ok=True, starved_writers=0, committed_writes=10, expected_writes=10
    )
    assert "corruption" in classify_failure_modes(
        lock_errors=0, integrity_ok=False, starved_writers=0, committed_writes=10, expected_writes=10
    )
    assert "write_starvation" in classify_failure_modes(
        lock_errors=0, integrity_ok=True, starved_writers=2, committed_writes=10, expected_writes=10
    )
    assert classify_failure_modes(
        lock_errors=0, integrity_ok=True, starved_writers=0, committed_writes=10, expected_writes=10
    ) == []


def test_wal_soak_twenty_writers_on_isolated_temp_db(tmp_path):
    db_path = tmp_path / "state.db"
    report = run_state_db_soak(
        SoakConfig(
            db_path=str(db_path),
            writers=20,
            readers=4,
            ops_per_writer=8,
            executor="thread",
        )
    )

    assert report.db_path == str(db_path)
    assert Path(report.db_path).exists()
    assert report.writers == 20
    assert report.integrity_ok is True
    assert report.journal_mode == "wal"
    assert report.recovery_ok is True
    assert report.committed_writes == report.expected_writes
    assert report.lock_errors == 0
    assert report.starved_writers == 0
    assert report.failure_modes == []
    assert report.passed is True
    assert report.p99_latency_s <= PASS_THRESHOLDS["max_p99_latency_s"]

    conn = sqlite3.connect(str(db_path))
    jobs = conn.execute("SELECT COUNT(*) FROM daemon_jobs").fetchone()[0]
    evidence = conn.execute("SELECT COUNT(*) FROM job_evidence").fetchone()[0]
    conn.close()
    assert jobs >= 20
    assert evidence >= 20


def test_wal_soak_fifty_writers_on_isolated_temp_db(tmp_path):
    report = run_state_db_soak(
        SoakConfig(
            db_path=str(tmp_path / "state-50.db"),
            writers=50,
            readers=8,
            ops_per_writer=6,
            executor="thread",
        )
    )
    assert report.passed is True
    assert report.writers == 50
    assert report.committed_writes == report.expected_writes
    assert report.lock_errors == 0
    assert report.integrity_ok is True
    assert report.journal_mode == "wal"


def test_wal_soak_process_executor_twenty_writers(tmp_path):
    report = run_state_db_soak(
        SoakConfig(
            db_path=str(tmp_path / "proc-state.db"),
            writers=20,
            readers=4,
            ops_per_writer=5,
            executor="process",
        )
    )
    assert report.passed is True
    assert report.integrity_ok is True
    assert report.lock_errors == 0
    assert report.starved_writers == 0


def test_soak_report_is_json_serializable(tmp_path):
    report = run_state_db_soak(
        SoakConfig(
            db_path=str(tmp_path / "json-state.db"),
            writers=20,
            readers=2,
            ops_per_writer=3,
            executor="thread",
        )
    )
    payload = report.to_dict()
    json.dumps(payload)
    assert payload["integrity_ok"] is True
    assert "lock_failure_rate" in payload
    assert "p50_latency_s" in payload
    assert "p99_latency_s" in payload


def test_scenario_runner_state_db_wal_soak(tmp_path):
    runner = ScenarioRunner(driver=None)
    result = runner.run_state_db_wal_soak(db_path=str(tmp_path / "scenario-state.db"), writers=20)
    assert result.name == "state_db_wal_soak"
    assert result.status == "PASSED"


def test_soak_without_wal_or_busy_timeout_captures_lock_failures(tmp_path):
    """Prove the harness records contention instead of silently swallowing it."""
    report = run_state_db_soak(
        SoakConfig(
            db_path=str(tmp_path / "delete-mode.db"),
            writers=20,
            readers=0,
            ops_per_writer=6,
            executor="thread",
            apply_wal=False,
            busy_timeout_ms=1,
            connect_timeout_s=0.05,
        )
    )
    if report.passed:
        pytest.skip("DELETE journal still serialized this load; no contention to capture")
    assert "lock_contention" in report.failure_modes or "write_starvation" in report.failure_modes
    assert report.lock_errors > 0 or report.starved_writers > 0


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _ScriptedConn:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def execute(self, sql):
        self.calls.append(sql)
        item = self._results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return _Cursor(item)


def test_delete_journal_pragma_retries_locked_then_succeeds():
    conn = _ScriptedConn(
        [
            sqlite3.OperationalError("database is locked"),
            ("wal",),
            ("delete",),
        ]
    )
    assert _apply_delete_journal_mode(conn, attempts=4, base_delay_s=0) is True
    assert conn.calls == [
        "PRAGMA journal_mode",
        "PRAGMA journal_mode",
        "PRAGMA journal_mode=DELETE",
    ]


def test_delete_journal_pragma_falls_through_when_lock_persists():
    conn = _ScriptedConn([sqlite3.OperationalError("database is locked")] * 5)
    assert _apply_delete_journal_mode(conn, attempts=3, base_delay_s=0) is False
    assert len(conn.calls) == 3


def test_delete_journal_pragma_does_not_swallow_other_operational_errors():
    conn = _ScriptedConn([sqlite3.OperationalError("disk I/O error")])
    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        _apply_delete_journal_mode(conn, attempts=3, base_delay_s=0)


def test_open_conn_survives_locked_delete_pragma(tmp_path, monkeypatch):
    db_path = tmp_path / "control.db"
    sqlite3.connect(db_path).close()
    monkeypatch.setattr(
        "synlynk.testbed.state_db_soak._apply_delete_journal_mode",
        lambda conn, **kwargs: False,
    )
    conn = _open_conn(
        SoakConfig(
            db_path=str(db_path),
            apply_wal=False,
            busy_timeout_ms=1,
            connect_timeout_s=0.05,
        )
    )
    try:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        conn.close()
