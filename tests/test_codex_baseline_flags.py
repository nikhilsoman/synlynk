"""Codex baseline flag names must match the installed CLI (TC-2)."""

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.probe import _run_tc2


def test_codex_valid_flags_use_ask_for_approval_not_approval_policy():
    flags = AGENT_CAPABILITY_BASELINES["codex"]["dispatch_flags"]
    valid = flags.get("valid_flags", [])
    invalid = flags.get("invalid_flags", [])
    assert "--ask-for-approval" in valid
    assert "--approval-policy" not in valid
    assert "--approval-policy" in invalid


def test_codex_tc2_passes_against_live_cli_help():
    """Regression: doctor TC-2 failed on --approval-policy after Codex renamed the flag."""
    result = _run_tc2("codex", AGENT_CAPABILITY_BASELINES["codex"]["dispatch_flags"])
    assert result["passed"] is True, result
    assert result["failed_flags"] == []
