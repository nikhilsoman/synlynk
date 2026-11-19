import os
from unittest.mock import patch

from synlynk.harness_manifest import discover_and_validate


def test_discover_and_validate_runs_mcp_smoke_check_when_harness_declares_mcp_tools(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/harnesses", exist_ok=True)
    monkeypatch.setitem(
        __import__("synlynk.harness_manifest", fromlist=["HARNESS_CAPABILITY_BASELINES"]).__dict__["HARNESS_CAPABILITY_BASELINES"],
        "test-mcp-harness",
        {"mcp_tools": ["some-tool"], "models": [], "dispatch_flags": {}, "panel_auth_check": {}, "cli": "echo"},
    )
    monkeypatch.setattr(
        "synlynk.costs._payment_model_config_for_agent",
        lambda harness: {"mode": "subscription"},
    )
    with patch("synlynk.doctor._run_tc8", return_value={"passed": True, "servers_checked": 1}) as mock_tc8:
        manifest = discover_and_validate("test-mcp-harness")
    mock_tc8.assert_called_once()
    assert manifest["last_validated_smoke_run"] == {"passed": True, "servers_checked": 1}
