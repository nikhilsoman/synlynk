import json

import pytest

from synlynk.product_store import (
    github_apps_dir, identity_slug_from_config, migrate_repo_apps_if_needed,
    product_root, resolve_github_apps_dir, types_yaml_path, write_apps_dir_for_init,
)
from synlynk.team import cmd_identity_init_role


def _repo(tmp_path, slug="vdowrx"):
    (tmp_path / ".synlynk").mkdir()
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


def test_second_init_is_noop_before_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    apps = github_apps_dir("vdowrx")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"installation_id": 2, "private_key_path": str(apps / "qa.pem")}))
    (apps / "qa.pem").write_text("dummy")
    monkeypatch.setattr("synlynk.team._build_app_manifest_url", lambda *a, **k: pytest.fail("manifest opened"))
    cmd_identity_init_role("qa")
