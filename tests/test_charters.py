import pytest

from synlynk.charters import AgentCharter, load_charter, validate_charter


def test_load_architect_charter():
    charter = load_charter("architect")
    assert charter.role == "architect"
    assert "draft_spec" in charter.autonomous_authorities
    assert "invariant_violation_detected" in charter.escalation_triggers
    assert validate_charter(charter)


def test_charter_requires_mandate():
    invalid_charter = AgentCharter(
        role="rogue",
        harness_bindings=["codex"],
        mandate="",
        autonomous_authorities=["destroy_all"],
        escalation_triggers=[],
        behavioral_weights={},
    )
    assert not validate_charter(invalid_charter)
