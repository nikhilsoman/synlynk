from unittest.mock import patch

from synlynk.support_engineer import cmd_agent_run


def test_cmd_agent_run_routes_pm_to_wake_cycle():
    with patch("synlynk.support_engineer._pkg") as mock_pkg, \
         patch("synlynk.pm_agent.cmd_pm_wake") as mock_wake:
        mock_pkg.return_value = lambda name: {"name": "pm", "wake_cycle": "pm_wake"}
        cmd_agent_run("pm")
        mock_wake.assert_called_once()


def test_cmd_agent_run_routes_tpm_to_wake_cycle():
    with patch("synlynk.support_engineer._pkg") as mock_pkg, \
         patch("synlynk.tpm_sweep.run_tpm_wake_cycle") as mock_wake:
        mock_pkg.return_value = lambda name: {"name": "tpm", "wake_cycle": "tpm_wake"}
        cmd_agent_run("tpm")
        mock_wake.assert_called_once()
