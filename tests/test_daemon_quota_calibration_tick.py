"""Unit test for the daemon's periodic quota calibration tick (v0.26.9)."""

from unittest.mock import MagicMock, patch

from synlynk.daemon import Daemon


def test_run_quota_calibration_tick_calls_maybe_calibrate_quota(tmp_path):
    d = Daemon.__new__(Daemon)  # bypass __init__, only the method under test is needed
    d.sentinel_path = str(tmp_path / "sentinel.md")

    with patch("synlynk.quota.maybe_calibrate_quota") as mock_calibrate:
        mock_calibrate.return_value = [{"harness": "claude", "window": "5h", "valid": True}]
        d._run_quota_calibration_tick({})
        mock_calibrate.assert_called_once()


def test_run_quota_calibration_tick_writes_sentinel_on_error(tmp_path):
    d = Daemon.__new__(Daemon)
    d.sentinel_path = str(tmp_path / "sentinel.md")

    with patch("synlynk.quota.maybe_calibrate_quota", side_effect=RuntimeError("boom")):
        d._run_quota_calibration_tick({})

    assert (tmp_path / "sentinel.md").exists()
    assert "QUOTA_CALIBRATION_TICK_FAILED" in (tmp_path / "sentinel.md").read_text()
