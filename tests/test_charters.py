import pytest

from synlynk import agent_store
from synlynk.charters import (
    AgentCharter,
    adapt_charters_for_installed_tools,
    load_charter,
    validate_charter,
)


def _register_charter(tmp_path, monkeypatch, role, skills=None):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    skills_block = "" if skills is None else "skills:\n" + "".join(f"  - {skill}\n" for skill in skills)
    content = (
        "---\n"
        "schema_version: 1\n"
        f"role: {role}\n"
        f'description: "{role} test charter"\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        f"{skills_block}"
        "---\n\n"
        "## Instructions\n\nDo the work.\n\n"
        "## Authority & Escalation\n\nEscalate as needed.\n\n"
        "## Workflow Ownership\n\nOwn the work.\n"
    )
    agent_id = f"{role}-test"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(agent_id, content, actor="test", parent_revision=0)


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


def test_adapt_charters_merges_superpowers_skills_for_dev_role(tmp_path, monkeypatch):
    _register_charter(tmp_path, monkeypatch, "dev")
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)

    updated = adapt_charters_for_installed_tools()

    assert "test-driven-development" in updated["dev"]["skills"]
    assert "systematic-debugging" in updated["dev"]["skills"]


def test_adapt_charters_seed_fallback_merges_superpowers_skills(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)

    updated = adapt_charters_for_installed_tools()

    assert "test-driven-development" in updated["dev"]["skills"]
    assert "systematic-debugging" in updated["dev"]["skills"]


def test_adapt_charters_unlisted_role_unaffected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)

    updated = adapt_charters_for_installed_tools()

    assert updated["designer"]["skills"] == []


def test_adapt_charters_no_duplicate_skills(tmp_path, monkeypatch):
    _register_charter(tmp_path, monkeypatch, "dev", ["test-driven-development"])
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)

    updated = adapt_charters_for_installed_tools()

    assert updated["dev"]["skills"].count("test-driven-development") == 1
