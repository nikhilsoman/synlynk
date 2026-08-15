import json
import os


def test_get_workspace_id_mints_and_persists(project_dir):
    from synlynk.agent_store import get_workspace_id

    workspace_id = get_workspace_id()
    assert workspace_id
    with open(".synlynk/config.json") as f:
        config = json.load(f)
    assert config["workspace_id"] == workspace_id


def test_get_workspace_id_idempotent(project_dir):
    from synlynk.agent_store import get_workspace_id

    first = get_workspace_id()
    second = get_workspace_id()
    assert first == second


def test_get_workspace_id_never_overwrites_existing_value(project_dir):
    from synlynk.agent_store import get_workspace_id

    with open(".synlynk/config.json") as f:
        config = json.load(f)
    config["workspace_id"] = "pre-existing-id"
    with open(".synlynk/config.json", "w") as f:
        json.dump(config, f)

    assert get_workspace_id() == "pre-existing-id"


def test_agent_store_path_under_workspace_home(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    path = agent_store.agent_store_path("dev-primary")
    assert path == str(fake_home / ".synlynk" / "workspaces" / workspace_id / "agents" / "dev-primary")


def test_register_and_resolve_agent(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )

    assert agent_store.resolve_agent_id("dev") == "dev-primary"
    assert agent_store.resolve_agent_id("synlynk-dev[bot]") == "dev-primary"
    assert agent_store.resolve_agent_id("unregistered-alias") is None


def test_register_agent_rejects_duplicate_agent_id(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev2"}])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_register_agent_rejects_duplicate_alias_across_agents(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-secondary", aliases=[{"kind": "role_slug", "value": "dev"}])
        assert False, "expected ValueError"
    except ValueError:
        pass
