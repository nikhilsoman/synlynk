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


def test_cmd_agent_edit_updates_charter(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    charter_file = tmp_path / "new_charter.md"
    charter_file.write_text("Implementation — writes the code, reviews own PRs.")

    agent_cli.cmd_agent_edit(agent_id, str(charter_file))

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert content == "Implementation — writes the code, reviews own PRs."


def test_cmd_agent_edit_stdin(project_dir, monkeypatch, capsys):
    import io
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO("New charter from stdin."))
    agent_cli.cmd_agent_edit(agent_id, "-")

    content, revision = agent_store.read_charter(agent_id)
    assert content == "New charter from stdin."
    assert revision == 2


def test_cmd_agent_edit_stale_revision_exits_1(project_dir, tmp_path, monkeypatch, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    # cmd_agent_edit reads parent_revision fresh from read_charter() immediately
    # before writing, so it never observes a stale cached revision itself. The
    # only way to exercise its RevisionConflictError handling path is to force
    # the underlying store call to raise it directly, simulating a concurrent
    # writer winning the race between our read and our write.
    def _raise_conflict(*args, **kwargs):
        raise agent_store.RevisionConflictError("concurrent edit detected")

    monkeypatch.setattr(agent_store, "propose_charter_revision", _raise_conflict)

    charter_file = tmp_path / "stale.md"
    charter_file.write_text("stale content")

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_edit(agent_id, str(charter_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "updated by someone else" in captured.err or "updated by someone else" in captured.out


def test_cmd_agent_disable_sets_flag(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)

    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    assert entry["disabled"] is True


def test_cmd_agent_disable_idempotent(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)
    capsys.readouterr()
    agent_cli.cmd_agent_disable(agent_id)
    captured = capsys.readouterr()
    assert "already disabled" in captured.out


def test_cmd_agent_disable_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_disable("nonexistent")
    assert exc_info.value.code == 1
