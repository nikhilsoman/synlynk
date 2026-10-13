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


def test_load_pm_charter():
    charter = load_charter("pm")
    assert charter.role == "pm"
    assert charter.harness_bindings == []
    assert "approve_priority" in charter.autonomous_authorities
    assert "charter_change_requested" in charter.escalation_triggers
    assert charter.durability == "durable"
    assert len(charter.wake_cycle_sop) == 4
    assert validate_charter(charter)


def test_load_tpm_charter():
    charter = load_charter("tpm")
    assert charter.role == "tpm"
    assert charter.harness_bindings == []
    assert "triage_issue" in charter.autonomous_authorities
    assert "dispatch_blocked_twice" in charter.escalation_triggers
    assert charter.durability == "durable"
    assert len(charter.wake_cycle_sop) == 7
    assert validate_charter(charter)


def test_maintainer_charter_is_durable():
    charter = load_charter("maintainer")
    assert charter.role == "maintainer"
    assert charter.durability == "durable"
    assert any(
        "drift" in step.lower() or "sweep" in step.lower()
        for step in charter.wake_cycle_sop
    )
    assert validate_charter(charter)


def test_empty_harness_bindings_is_valid():
    charter = AgentCharter(
        role="pm",
        harness_bindings=[],
        mandate="Approve things",
        autonomous_authorities=["approve_priority"],
        escalation_triggers=["budget_exceeded"],
        behavioral_weights={},
    )
    assert validate_charter(charter)
