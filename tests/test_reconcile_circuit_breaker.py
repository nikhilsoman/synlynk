"""Unit tests for active in-flight circuit breaker in reconciliation (Invariant 2)."""

import hashlib
import os
import signal
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import synlynk
from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED
from synlynk.sentinel import _read_active_sentinel_alerts


def test_reconcile_trips_circuit_breaker_on_runaway_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    job_id = "job-reconcile-cb-test"
    log_file = log_dir / f"{job_id}.log"
    # Write tokens exceeding limit
    log_file.write_text("Input tokens: 350000\nOutput tokens: 20000\nStreaming runaway text...\n")

    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr("synlynk.circuit_breaker.process_identity_check", lambda pid, expected: "safe to kill")

    job = {
        "id": job_id,
        "agent": "codex",
        "task": "Refactor codebase",
        "status": "running",
        "pid": 88888,
        "pid_identity": {"start_time": "reconcile-test"},
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])

    # Configure circuit breaker limit lower than 370k
    config = {
        "circuit_breaker": {
            "max_job_tokens": 200000,
            "max_job_cost_usd": 10.00,
        }
    }
    monkeypatch.setattr(synlynk, "load_config", lambda: config)

    synlynk._reconcile_jobs()

    jobs = synlynk._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job_id)

    assert reconciled["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert reconciled["circuit_breaker_reason"] is not None
    assert len(killed) >= 1
    assert killed[0][0] == 88888

    # Verify sentinel alert
    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    assert sentinel_file.exists()
    alerts = _read_active_sentinel_alerts(str(sentinel_file))
    cb_alerts = [a for a in alerts if "TOKEN_CIRCUIT_BREAKER_TRIPPED" in a.get("code", "")]
    assert len(cb_alerts) >= 1


def test_reconcile_does_not_trip_on_normal_running_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    log_dir = tmp_path / ".synlynk" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    job_id = "job-reconcile-normal-test"
    log_file = log_dir / f"{job_id}.log"
    # Write normal tokens within limits
    log_file.write_text("Input tokens: 5000\nOutput tokens: 1000\nNormal progress...\n")

    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(os, "waitpid", lambda pid, options: (0, 0))

    job = {
        "id": job_id,
        "agent": "codex",
        "task": "Normal feature work",
        "status": "running",
        "pid": 77777,
        "pid_identity": {"start_time": "normal-test"},
        "log_file": str(log_file),
        "started_at": "2026-09-27T12:00:00",
        "ended_at": None,
        "exit_code": None,
    }
    synlynk._save_jobs([job])

    config = {
        "circuit_breaker": {
            "max_job_tokens": 200000,
            "max_job_cost_usd": 10.00,
        }
    }
    monkeypatch.setattr(synlynk, "load_config", lambda: config)

    synlynk._reconcile_jobs()

    jobs = synlynk._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job_id)

    assert reconciled["status"] == "running"
    termination_signals = [sig for pid, sig in killed if sig in (signal.SIGTERM, signal.SIGKILL)]
    assert len(termination_signals) == 0

