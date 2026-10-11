"""Unit tests for Invariant 2: Hard in-flight token circuit breakers & runaway worker killer."""

import os
import signal
import sys
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED
from synlynk.circuit_breaker import (
    CircuitBreakerResult,
    evaluate_job_circuit_breaker,
)
from synlynk.sentinel import _read_active_sentinel_alerts


def _codex_turn_log(input_tokens, cached_input_tokens, output_tokens, reasoning=0):
    return (
        '{"type":"turn.completed","usage":{'
        f'"input_tokens":{input_tokens},'
        f'"cached_input_tokens":{cached_input_tokens},'
        f'"output_tokens":{output_tokens},'
        f'"reasoning_output_tokens":{reasoning}'
        "}}\n"
    )


def test_codex_tool_loop_cache_sum_does_not_trip_fast_tier_or_zero_file(tmp_path, monkeypatch):
    """job-fccc76c4 / job-fda2e4ef: one Codex turn summed ~1.2M input tokens,
    of which ~1.18M were cache reads of a ~50k prompt. The live prompt never
    approached the 500k zero-file or fast-tier limits. Those jobs were killed
    anyway because the sum was priced and compared as fresh input.
    """
    log_file = tmp_path / "job.log"
    log_file.write_text(_codex_turn_log(1_248_424, 1_181_440, 6_645, 2_141))
    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append((pid, sig)))

    job = {
        "id": "job-fccc76c4",
        "agent": "codex",
        "model_tier": "fast",
        "pid": 4242,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path),
        "status": "running",
    }
    config = {
        "circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 15.00,
            "zero_file_token_threshold": 500_000,
            "tier_overrides": {
                "fast": {"max_job_tokens": 500_000, "max_job_cost_usd": 2.00},
            },
        }
    }
    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )
    assert res.tripped is False
    assert killed == []
    assert job["status"] == "running"
    assert res.total_tokens < 500_000
    assert res.cost_usd < 2.00


def test_codex_uncached_cumulative_input_still_trips_zero_file(tmp_path, monkeypatch):
    log_file = tmp_path / "job.log"
    log_file.write_text(_codex_turn_log(600_000, 0, 100))
    monkeypatch.setattr(os, "kill", lambda pid, sig: None)
    job = {
        "id": "job-real-bloat",
        "agent": "codex",
        "pid": 4243,
        "log_file": str(log_file),
        "worktree_path": str(tmp_path),
        "status": "running",
    }
    res = evaluate_job_circuit_breaker(
        job,
        config={"circuit_breaker": {
            "max_job_tokens": 5_000_000,
            "max_job_cost_usd": 100.0,
            "zero_file_token_threshold": 500_000,
        }},
        sentinel_path=str(tmp_path / "sentinel.md"),
        skip_identity_check_for_test=True,
    )
    assert res.tripped is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED


def test_circuit_breaker_not_tripped_under_limits(tmp_path):
    log_file = tmp_path / "normal_job.log"
    log_file.write_text("Input tokens: 500\nOutput tokens: 100\nDone work.\n")

    job = {
        "id": "job-normal-1",
        "agent": "codex",
        "pid": 12345,
        "log_file": str(log_file),
        "status": "running",
    }

    res = evaluate_job_circuit_breaker(job, config={"circuit_breaker": {"max_job_tokens": 100000, "max_job_cost_usd": 3.00}})
    assert res.tripped is False
    assert res.process_killed is False
    assert job["status"] == "running"


def test_circuit_breaker_trips_on_token_limit_breach(tmp_path, monkeypatch):
    log_file = tmp_path / "runaway_tokens.log"
    # Write token count exceeding 100,000 limit
    log_file.write_text("Input tokens: 120000\nOutput tokens: 15000\n")
    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_file.parent.mkdir(parents=True, exist_ok=True)

    killed_pids = []
    def fake_kill(pid, sig):
        killed_pids.append((pid, sig))

    monkeypatch.setattr(os, "kill", fake_kill)

    job = {
        "id": "job-token-runaway",
        "agent": "codex",
        "pid": 54321,
        "pid_identity": {"start_time": "test-time"},
        "log_file": str(log_file),
        "status": "running",
    }

    config = {
        "circuit_breaker": {
            "max_job_tokens": 100000,
            "max_job_cost_usd": 5.00,
            "zero_file_token_threshold": 50000,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(sentinel_file),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is True
    assert res.process_killed is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert "token" in res.reason.lower() or "runaway" in res.reason.lower()
    assert len(killed_pids) >= 1
    assert killed_pids[0][0] == 54321

    # Verify Sentinel alert generated
    alerts = _read_active_sentinel_alerts(str(sentinel_file))
    cb_alerts = [a for a in alerts if "TOKEN_CIRCUIT_BREAKER_TRIPPED" in a.get("code", "")]
    assert len(cb_alerts) >= 1
    assert "job-token-runaway" in cb_alerts[0]["message"]


def test_circuit_breaker_trips_on_cost_limit_breach(tmp_path, monkeypatch):
    log_file = tmp_path / "expensive_runaway.log"
    # Write token counts that compute to > $2.00 cost
    log_file.write_text("Input tokens: 400000\nOutput tokens: 100000\n")
    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_file.parent.mkdir(parents=True, exist_ok=True)

    killed_pids = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed_pids.append((pid, sig)))

    job = {
        "id": "job-cost-runaway",
        "agent": "claude",
        "pid": 65432,
        "log_file": str(log_file),
        "status": "running",
    }

    config = {
        "circuit_breaker": {
            "max_job_tokens": 1000000,
            "max_job_cost_usd": 1.50,
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(sentinel_file),
        skip_identity_check_for_test=True,
    )

    assert res.tripped is True
    assert res.process_killed is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert "cost" in res.reason.lower()


def test_circuit_breaker_respects_tier_overrides(tmp_path, monkeypatch):
    log_file = tmp_path / "fast_tier.log"
    log_file.write_text("Input tokens: 60000\nOutput tokens: 5000\n")
    sentinel_file = tmp_path / ".synlynk" / "sentinel.md"
    sentinel_file.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(os, "kill", lambda pid, sig: None)

    job = {
        "id": "job-fast-tier",
        "agent": "codex",
        "model_tier": "fast",
        "pid": 77777,
        "log_file": str(log_file),
        "status": "running",
    }

    config = {
        "circuit_breaker": {
            "max_job_tokens": 300000,
            "max_job_cost_usd": 3.00,
            "tier_overrides": {
                "fast": {"max_job_tokens": 50000, "max_job_cost_usd": 0.20},
            }
        }
    }

    res = evaluate_job_circuit_breaker(
        job,
        config=config,
        sentinel_path=str(sentinel_file),
        skip_identity_check_for_test=True,
    )

    # Fast tier max is 50,000, job has 65,000 -> must trip
    assert res.tripped is True
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
