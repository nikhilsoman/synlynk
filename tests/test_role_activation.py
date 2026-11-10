import json

import pytest


def _fake_home(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(fake_home)))


def test_activate_role_registers_agent_and_writes_charter(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import agent_store, role_activation

    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert "secops" in agent_ids
    charter, revision = agent_store.read_charter("secops")
    assert "role: secops" in charter
    assert revision == 1


def test_activate_role_is_idempotent(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import role_activation

    role_activation.activate_role("secops", actor="nikhil", actor_type="human")
    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    from synlynk import agent_store
    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert agent_ids.count("secops") == 1


def test_activate_role_rejects_unknown_role(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import role_activation

    with pytest.raises(ValueError, match="no seed charter"):
        role_activation.activate_role("not-a-real-role", actor="nikhil", actor_type="human")


def test_activate_maintainer_role(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import agent_store, role_activation

    role_activation.activate_role("maintainer", actor="nikhil", actor_type="human")

    charter, _ = agent_store.read_charter("maintainer")
    assert "worktree_cleanup" in charter
    assert "release_cut" in charter
    assert "identity_binding" in charter


def test_cli_agent_activate_calls_role_activation(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    import sys
    from synlynk import cli

    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "activate", "secops"])
    cli.main()

    from synlynk import agent_store
    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert "secops" in agent_ids


def test_activate_role_seeds_capability_ratings(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    import sqlite3
    from synlynk import _get_db, role_activation

    conn = _get_db()
    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    rows = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE agent='secops' AND signal_source='seed'"
    ).fetchone()
    assert rows[0] > 0


def test_cli_agent_deprecate_disables_and_revokes(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    import sys
    from synlynk import agent_store, cli

    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "activate", "secops"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "deprecate", "secops"])
    cli.main()

    entries = [e for e in agent_store.list_agents() if e["agent_id"] == "secops"]
    assert entries[0]["disabled"] is True




