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
