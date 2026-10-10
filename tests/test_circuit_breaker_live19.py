import pytest
from unittest.mock import patch

from synlynk.circuit_breaker import (
    evaluate_job_circuit_breaker,
    CircuitBreakerResult,
    DEFAULT_MAX_JOB_TOKENS,
    DEFAULT_MAX_JOB_COST_USD,
    DEFAULT_ZERO_FILE_TOKEN_THRESHOLD,
    DEFAULT_TIER_OVERRIDES,
)
from synlynk.jobs import STATUS_CIRCUIT_BREAKER_TRIPPED


def test_circuit_breaker_defaults_live19():
    assert DEFAULT_MAX_JOB_TOKENS == 5_000_000
    assert DEFAULT_MAX_JOB_COST_USD == 15.00
    assert DEFAULT_ZERO_FILE_TOKEN_THRESHOLD == 500_000
    
    assert DEFAULT_TIER_OVERRIDES["fast"]["max_job_tokens"] == 500_000
    assert DEFAULT_TIER_OVERRIDES["fast"]["max_job_cost_usd"] == 2.00
    
    assert DEFAULT_TIER_OVERRIDES["pro"]["max_job_tokens"] == 3_000_000
    assert DEFAULT_TIER_OVERRIDES["pro"]["max_job_cost_usd"] == 10.00
    
    assert DEFAULT_TIER_OVERRIDES["reasoning"]["max_job_tokens"] == 5_000_000
    assert DEFAULT_TIER_OVERRIDES["reasoning"]["max_job_cost_usd"] == 15.00


@patch("synlynk.circuit_breaker.log_telemetry_event")
@patch("synlynk.circuit_breaker._write_sentinel_alert")
@patch("synlynk.circuit_breaker._kill_process_tree")
@patch("synlynk.jobs._job_cost_usd")
@patch("synlynk.costs.extract_tokens")
def test_evaluate_job_circuit_breaker_not_killed_live19(
    mock_extract_tokens,
    mock_job_cost_usd,
    mock_kill_process_tree,
    mock_write_sentinel,
    mock_log_telemetry,
):
    # Simulate a breach
    mock_extract_tokens.return_value = (500_000, 4_600_000) # total > 5_000_000
    mock_job_cost_usd.return_value = 16.00 # cost > 15.00
    
    # Process already exited
    mock_kill_process_tree.return_value = (False, "no_pid")
    
    job = {
        "id": "job-123",
        "agent": "test-agent",
        "status": "RUNNING",
        "pid": 99999,
    }
    
    result = evaluate_job_circuit_breaker(job, config={})
    
    # Assertions
    assert result.tripped is False
    assert result.process_killed is False
    assert result.kill_method == "no_pid"
    
    # State not mutated
    assert job["status"] == "RUNNING"
    assert "exit_code" not in job
    
    # No sentinel alert
    mock_write_sentinel.assert_not_called()
    
    # Telemetry should log warning
    mock_log_telemetry.assert_called_with({
        "type": "circuit_breaker_post_exit_warning",
        "job_id": "job-123",
        "agent": "test-agent",
        "tokens": 5_100_000,
        "cost_usd": 16.0,
        "reason": "Cost limit breached: $16.00 >= $15.00",
    })


@patch("synlynk.circuit_breaker.log_telemetry_event")
@patch("synlynk.circuit_breaker._write_sentinel_alert")
@patch("synlynk.circuit_breaker._kill_process_tree")
@patch("synlynk.jobs._job_cost_usd")
@patch("synlynk.costs.extract_tokens")
def test_evaluate_job_circuit_breaker_killed_live19(
    mock_extract_tokens,
    mock_job_cost_usd,
    mock_kill_process_tree,
    mock_write_sentinel,
    mock_log_telemetry,
):
    # Simulate a breach
    mock_extract_tokens.return_value = (500_000, 4_600_000) # total > 5_000_000
    mock_job_cost_usd.return_value = 16.00 # cost > 15.00
    
    # Process successfully killed
    mock_kill_process_tree.return_value = (True, "SIGKILL")
    
    job = {
        "id": "job-123",
        "agent": "test-agent",
        "status": "RUNNING",
        "pid": 99999,
    }
    
    result = evaluate_job_circuit_breaker(job, config={})
    
    # Assertions
    assert result.tripped is True
    assert result.process_killed is True
    assert result.kill_method == "SIGKILL"
    
    # State mutated
    assert job["status"] == STATUS_CIRCUIT_BREAKER_TRIPPED
    assert job["exit_code"] == -9
    assert "circuit_breaker_reason" in job
    
    # Sentinel alert written
    mock_write_sentinel.assert_called_once()
    
    # Telemetry should log normal kill
    mock_log_telemetry.assert_called_with({
        "type": "circuit_breaker",
        "job_id": "job-123",
        "agent": "test-agent",
        "tokens": 5_100_000,
        "cost_usd": 16.0,
        "reason": "Cost limit breached: $16.00 >= $15.00",
        "kill_method": "SIGKILL",
    })
