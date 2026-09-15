import pytest
from synlynk.charters import adapt_charters_for_installed_tools, cmd_charters_adapt
from synlynk import agent_store


def test_adapt_charters_injects_graphify_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    updated = adapt_charters_for_installed_tools()
    assert "graphify-architecture-audit" in updated["architect"]["skills"]
    assert "graphify-pr-impact" in updated["qa"]["skills"]
    assert "graphify-symbol-navigator" in updated["dev"]["skills"]


def test_adapt_charters_injects_pm_and_verifier_skills(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    updated = adapt_charters_for_installed_tools()
    assert "graphify-domain-sweep" in updated["pm"]["skills"]
    assert "graphify-pr-impact" in updated["verifier"]["skills"]


def test_adapt_charters_when_tool_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: False)
    updated = adapt_charters_for_installed_tools()
    assert "graphify-architecture-audit" not in updated["architect"]["skills"]
    assert "graphify-pr-impact" not in updated["qa"]["skills"]
    assert "graphify-symbol-navigator" not in updated["dev"]["skills"]
    assert "graphify-domain-sweep" not in updated["pm"]["skills"]


def test_adapt_charters_updates_living_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)

    agent_id = "architect-agent-1"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": "architect"}])
    initial_charter = (
        "---\n"
        "schema_version: 1\n"
        "role: architect\n"
        'description: "System design — architecture and technical direction."\n'
        "durability: session-only\n"
        "tools: []\n"
        "credentials: []\n"
        "skills: []\n"
        "---\n\n"
        "## Instructions\n\nDesign things.\n\n"
        "## Authority & Escalation\n\nEscalate tradeoffs.\n\n"
        "## Workflow Ownership\n\nSpec and Plan stages.\n"
    )
    agent_store.propose_charter_revision(agent_id, initial_charter, actor="test", parent_revision=0)

    updated = adapt_charters_for_installed_tools(dry_run=False)
    assert "graphify-architecture-audit" in updated["architect"]["skills"]

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert "graphify-architecture-audit" in content


def test_cmd_charters_adapt_triggers_tool_adaptation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)
    monkeypatch.setattr("synlynk.charters.detect_charter_divergence", lambda *a, **kw: [])

    agent_id = "qa-agent-1"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": "qa"}])
    initial_charter = (
        "---\n"
        "schema_version: 1\n"
        "role: qa\n"
        'description: "Quality assurance — tests and verifies work."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "skills: []\n"
        "---\n\n"
        "## Instructions\n\nVerify things.\n\n"
        "## Authority & Escalation\n\nDecides pass/fail.\n\n"
        "## Workflow Ownership\n\nCI/CD gate.\n"
    )
    agent_store.propose_charter_revision(agent_id, initial_charter, actor="test", parent_revision=0)

    cmd_charters_adapt(dry_run=False)
    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert "graphify-pr-impact" in content


def test_cmd_agent_sync_skills(tmp_path, monkeypatch):
    from synlynk.agent_cli import cmd_agent_sync_skills

    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda path: path.replace("~", str(fake_home)))
    monkeypatch.setattr("synlynk.tool_installer.is_tool_available", lambda tool: True)

    agent_id = "dev-agent-1"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": "dev"}])
    initial_charter = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "Implementation — writes the code."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "skills: []\n"
        "---\n\n"
        "## Instructions\n\nCode things.\n\n"
        "## Authority & Escalation\n\nEscalate scope.\n\n"
        "## Workflow Ownership\n\nImplement stage.\n"
    )
    agent_store.propose_charter_revision(agent_id, initial_charter, actor="test", parent_revision=0)

    res = cmd_agent_sync_skills(agent_id)
    assert "graphify-symbol-navigator" in res["dev"]["skills"]
    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert "graphify-symbol-navigator" in content

