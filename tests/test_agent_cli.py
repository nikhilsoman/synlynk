import os

import pytest


SEED_ROLES = ["dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot"]


def test_cmd_agent_init_creates_registry_entry_and_charter(project_dir):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")

    agents = agent_store.list_agents()
    assert len(agents) == 1
    assert agents[0]["agent_id"] == agent_id
    assert {"kind": "role_slug", "value": "dev"} in agents[0]["aliases"]

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 1
    assert content == agent_cli.SEED_CHARTERS["dev"]


def test_cmd_agent_init_writes_projection_with_empty_capability_grants(project_dir):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("qa")

    projection_path = os.path.join(".synlynk", "agents", f"{agent_id}.yaml")
    with open(projection_path) as f:
        rendered = f.read()
    assert "capability_grants: {}" in rendered


def test_cmd_agent_init_rejects_duplicate_role(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_init("dev")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "already has an agent" in captured.err or "already has an agent" in captured.out


def test_cmd_agent_list_empty(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "No agents registered" in captured.out


def test_cmd_agent_list_shows_all_agents(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    agent_cli.cmd_agent_init("qa")
    capsys.readouterr()

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "dev" in captured.out
    assert "qa" in captured.out
    assert "active" in captured.out


def test_cmd_agent_show_resolves_by_full_id(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show(agent_id)
    captured = capsys.readouterr()
    assert agent_id in captured.out
    assert "dev" in captured.out


def test_cmd_agent_show_resolves_by_alias(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show("dev")
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cmd_agent_show_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_show("nonexistent")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No agent found matching" in captured.err or "No agent found matching" in captured.out
