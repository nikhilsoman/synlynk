import json

import pytest

from synlynk.product_store import (
    github_apps_dir, identity_slug_from_config, migrate_repo_apps_if_needed,
    migrate_state_db_if_needed, product_registry_path, product_root,
    register_product, resolve_github_apps_dir, state_db_path,
    types_yaml_path, write_apps_dir_for_init,
)
from synlynk.team import cmd_identity_init_role


def _repo(tmp_path, slug="vdowrx"):
    (tmp_path / ".synlynk").mkdir(parents=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": slug}))


def test_identity_slug_and_product_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _repo(tmp_path)
    assert identity_slug_from_config(tmp_path) == "vdowrx"
    root = product_root("vdowrx")
    assert root == tmp_path / "home" / ".synlynk" / "workspaces" / "vdowrx"
    assert github_apps_dir("vdowrx") == root / "github_apps"
    assert types_yaml_path("vdowrx") == root / "types.yaml"


def test_resolve_prefers_product_then_repo_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _repo(tmp_path)
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text("{}")
    assert resolve_github_apps_dir(tmp_path) == repo_apps
    product = github_apps_dir("vdowrx")
    product.mkdir(parents=True)
    (product / "qa.json").write_text("{}")
    assert resolve_github_apps_dir(tmp_path) == product


def test_write_and_migrate_are_product_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _repo(tmp_path)
    repo_apps = tmp_path / ".synlynk" / "github_apps"
    repo_apps.mkdir()
    (repo_apps / "qa.json").write_text("{}")
    (repo_apps / "qa.pem").write_text("k")
    assert migrate_repo_apps_if_needed(tmp_path) == github_apps_dir("vdowrx")
    assert (github_apps_dir("vdowrx") / "qa.pem").read_text() == "k"
    assert write_apps_dir_for_init(tmp_path).is_dir()


def test_second_init_is_a_noop_before_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    apps = github_apps_dir("vdowrx")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"installation_id": 2, "private_key_path": str(apps / "qa.pem")}))
    (apps / "qa.pem").write_text("dummy")
    monkeypatch.setattr("synlynk.team._build_app_manifest_url", lambda *a, **k: pytest.fail("manifest opened"))
    cmd_identity_init_role("qa")
    assert "already provisioned" in capsys.readouterr().out


def test_state_db_migration_copies_legacy_repo_db_without_overwrite(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    _repo(repo, "hitchcock")
    legacy = repo / ".synlynk" / "state.db"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(legacy)
    source_conn.execute("CREATE TABLE ledger (value TEXT)")
    source_conn.execute("INSERT INTO ledger VALUES ('legacy')")
    source_conn.commit()
    source_conn.close()
    destination = migrate_state_db_if_needed(repo)
    assert destination == state_db_path("hitchcock")
    destination_conn = sqlite3.connect(destination)
    assert destination_conn.execute("SELECT value FROM ledger").fetchone() == ("legacy",)
    assert destination_conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    destination_conn.close()
    legacy.write_bytes(b"newer")
    assert migrate_state_db_if_needed(repo) == destination
    destination_conn = sqlite3.connect(destination)
    assert destination_conn.execute("SELECT value FROM ledger").fetchone() == ("legacy",)
    destination_conn.close()


def test_product_registry_registration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    first = register_product("synlynk")
    second = register_product("synlynk")
    assert first == second == state_db_path("synlynk")
    assert register_product("synlynk") == first
    payload = json.loads(product_registry_path().read_text())
    assert payload["products"]["synlynk"]["mode"] == "canonical"


def test_product_registry_rejects_path_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    register_product("synlynk")
    with pytest.raises(RuntimeError, match="path mismatch"):
        register_product("synlynk", tmp_path / "other.db")


def test_product_registry_rejects_corrupt_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    path = product_registry_path()
    path.parent.mkdir(parents=True)
    path.write_text("not json")
    with pytest.raises(RuntimeError, match="unreadable"):
        register_product("synlynk")


def test_existing_ledger_without_registry_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    legacy_path = state_db_path("synlynk")
    legacy_path.parent.mkdir(parents=True)
    legacy_path.touch()
    with pytest.raises(RuntimeError, match="missing for existing ledger"):
        from synlynk.product_store import ensure_product_registered

        ensure_product_registered("synlynk")
