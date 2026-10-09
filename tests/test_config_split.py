import json
import os
import synlynk


def test_load_workspace_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws = synlynk.load_workspace()
    assert ws["local_fallback"] == "agy"
    assert ws["dispatch"]["stacking"] == "auto"
    assert ws["mode"] == "solo"


def test_load_billing_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    billing = synlynk.load_billing()
    assert billing["budget"] == {"limit_usd": 10.0, "limit_requests": 100}
    assert "claude" in billing["harness_billing"] or billing["harness_billing"] == {}


def test_load_workspace_reads_existing_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"schema_version": 1, "local_fallback": "codex"}, f)
    assert synlynk.load_workspace()["local_fallback"] == "codex"


def test_migration_splits_legacy_config_into_three_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    legacy = {
        "schema_version": 1,
        "local_fallback": "codex",
        "budget": {"limit_usd": 25.0, "limit_requests": 50},
        "harness_billing": {},
        "qa_gate_mode": "merge-restricted-classes",
        "roles": {"claude": ["pm"]},
    }
    with open(".synlynk/config.json", "w") as f:
        json.dump(legacy, f)

    synlynk.migrate_legacy_config_if_needed()

    assert os.path.exists(".synlynk/workspace.json")
    assert os.path.exists(".synlynk/billing.json")
    assert os.path.exists(".synlynk/policy.json")
    assert os.path.exists(".synlynk/config.json.bak")
    assert not os.path.exists(".synlynk/config.json")

    with open(".synlynk/workspace.json") as f:
        workspace = json.load(f)
    assert workspace["local_fallback"] == "codex"
    assert "budget" not in workspace

    with open(".synlynk/billing.json") as f:
        billing = json.load(f)
    assert billing["budget"] == {"limit_usd": 25.0, "limit_requests": 50}

    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    assert policy["qa_gate_mode"] == "merge-restricted-classes"
    assert policy["roles"] == {"claude": ["pm"]}


def test_migration_preserves_existing_policy_json_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "qa_gate_mode": "block-only"}, f)
    with open(".synlynk/policy.json", "w") as f:
        json.dump({"schema_version": 1, "repo_id": "synlynk", "overrides": {"foo": "bar"}}, f)

    synlynk.migrate_legacy_config_if_needed()

    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    assert policy["repo_id"] == "synlynk"
    assert policy["overrides"] == {"foo": "bar"}
    assert policy["qa_gate_mode"] == "block-only"


def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1}, f)
    assert synlynk.migrate_legacy_config_if_needed() is True
    workspace_mtime = os.path.getmtime(".synlynk/workspace.json")

    assert synlynk.migrate_legacy_config_if_needed() is False

    assert os.path.getmtime(".synlynk/workspace.json") == workspace_mtime


def test_migration_noop_when_no_legacy_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert synlynk.migrate_legacy_config_if_needed() is False
    assert not os.path.exists(".synlynk")


def test_migration_aborts_on_corrupt_policy_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1}, f)
    with open(".synlynk/policy.json", "w") as f:
        f.write("{not valid json")

    assert synlynk.migrate_legacy_config_if_needed() is False

    assert os.path.exists(".synlynk/config.json")
    assert not os.path.exists(".synlynk/config.json.bak")
    assert not os.path.exists(".synlynk/workspace.json")


def test_load_config_facade_matches_old_flat_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert config["schema_version"] == 1
    assert config["budget"] == {"limit_usd": 10.0, "limit_requests": 100}
    assert config["local_fallback"] == "agy"
    assert config["qa_gate_mode"] == "block-only"
    assert config["dispatch"]["stacking"] == "auto"


def test_load_config_falls_back_to_legacy_config_without_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "local_fallback": "codex"}, f)

    config = synlynk.load_config()

    assert config["local_fallback"] == "codex"
    assert os.path.exists(".synlynk/config.json")
    assert not os.path.exists(".synlynk/workspace.json")
    assert not os.path.exists(".synlynk/config.json.bak")


def test_migration_preserves_arbitrary_legacy_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "agent_discovery_paths": ["foo"], "worktree": "bar"}, f)

    assert synlynk.migrate_legacy_config_if_needed() is True

    with open(".synlynk/workspace.json") as f:
        workspace = json.load(f)
    assert workspace["agent_discovery_paths"] == ["foo"]
    assert workspace["worktree"] == "bar"


def test_load_config_does_not_migrate_legacy_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    legacy_path = ".synlynk/config.json"
    legacy = {"schema_version": 1, "agent_discovery_paths": ["foo"], "worktree": "bar"}
    with open(legacy_path, "w") as f:
        json.dump(legacy, f)
    before = open(legacy_path, "rb").read()
    before_mtime = os.path.getmtime(legacy_path)

    for _ in range(3):
        config = synlynk.load_config()

    assert config["agent_discovery_paths"] == ["foo"]
    assert config["worktree"] == "bar"
    assert open(legacy_path, "rb").read() == before
    assert os.path.getmtime(legacy_path) == before_mtime
    assert not os.path.exists(".synlynk/workspace.json")
    assert not os.path.exists(".synlynk/billing.json")
    assert not os.path.exists(".synlynk/config.json.bak")


def test_migration_is_idempotent_and_preserves_split_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "worktree": "bar"}, f)

    assert synlynk.migrate_legacy_config_if_needed() is True
    split_files = {
        name: open(f".synlynk/{name}", "rb").read()
        for name in ("workspace.json", "billing.json", "policy.json")
    }

    assert synlynk.migrate_legacy_config_if_needed() is False
    assert {
        name: open(f".synlynk/{name}", "rb").read()
        for name in ("workspace.json", "billing.json", "policy.json")
    } == split_files
