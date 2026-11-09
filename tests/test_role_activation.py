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
