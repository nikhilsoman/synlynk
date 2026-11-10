"""Tests for TPM Orchestrator autonomy level behavior in wake cycles."""
import pytest
from unittest.mock import patch, MagicMock

from synlynk.autonomy import AutonomyLevel
from synlynk.tpm_sweep import run_tpm_wake_cycle


@pytest.fixture
def mock_backlog_and_db():
    with patch("synlynk.tpm_sweep.ingest_backlog") as mock_ingest, \
         patch("synlynk.tpm_sweep.triage_backlog") as mock_triage, \
         patch("synlynk.db._get_db") as mock_get_db:
        mock_triage.return_value = [
            {"id": "item-1", "goal_id": "goal-1", "complexity_tier": 1},
            {"id": "item-2", "goal_id": None, "complexity_tier": 2},
        ]
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        yield mock_conn


@patch("synlynk.tpm_sweep.get_agent_autonomy_level")
@patch("synlynk.tpm_sweep.run_sweep_pass")
def test_tpm_wake_cycle_in_l1_advisory_skips_sweep_dispatch(mock_sweep, mock_autonomy, mock_backlog_and_db):
    mock_autonomy.return_value = AutonomyLevel.L1_ADVISORY

    result = run_tpm_wake_cycle()

    assert result["autonomy_level"] == "L1_ADVISORY"
    assert result["sweep"]["status"] == "advisory_only"
    assert result["sweep"]["dispatched"] == 0
    # Crucial safety invariant: zero dispatch in L1 Advisory
    mock_sweep.assert_not_called()


@patch("synlynk.tpm_sweep.get_agent_autonomy_level")
@patch("synlynk.tpm_sweep.run_sweep_pass")
def test_tpm_wake_cycle_in_l2_gated_executes_gated_sweep(mock_sweep, mock_autonomy, mock_backlog_and_db):
    mock_autonomy.return_value = AutonomyLevel.L2_GATED
    mock_sweep.return_value = {"advanced": 1, "parked": 1, "failed": 0}

    result = run_tpm_wake_cycle()

    assert result["autonomy_level"] == "L2_GATED"
    assert result["sweep"]["advanced"] == 1
    assert result["sweep"]["parked"] == 1
    mock_sweep.assert_called_once()


@patch("synlynk.tpm_sweep.get_agent_autonomy_level")
@patch("synlynk.tpm_sweep.run_sweep_pass")
def test_tpm_wake_cycle_in_l3_autonomous_executes_autonomous_sweep(mock_sweep, mock_autonomy, mock_backlog_and_db):
    mock_autonomy.return_value = AutonomyLevel.L3_AUTONOMOUS
    mock_sweep.return_value = {"advanced": 3, "parked": 0, "failed": 0}

    result = run_tpm_wake_cycle()

    assert result["autonomy_level"] == "L3_AUTONOMOUS"
    assert result["sweep"]["advanced"] == 3
    mock_sweep.assert_called_once()
