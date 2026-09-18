import json

import pytest

from synlynk.product_store import github_apps_dir, repos_path, types_yaml_path
from synlynk.workspace import add_repo


def _repo(tmp_path, slug="product"):
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({"identity_slug": slug}))


def test_add_repo_updates_canonical_apps_and_product_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _repo(tmp_path)
    product = tmp_path / "home" / ".synlynk" / "workspaces" / "product"
    product.mkdir(parents=True)
    types_yaml_path("product").write_text(json.dumps({"types": {
        "qa": {"kind": "qa", "canonical": True},
        "frontend-qa": {"kind": "qa", "canonical": False},
    }}))
    apps = github_apps_dir("product")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"app_slug": "qa"}))
    (apps / "frontend-qa.json").write_text(json.dumps({"app_slug": "frontend-qa", "repos": ["old/api"]}))

    result = add_repo("org/api", str(tmp_path))

    assert result["repo_id"] == "org/api"
    assert json.loads((tmp_path / ".synlynk" / "config.json").read_text())["repo_id"] == "org/api"
    assert json.loads((apps / "qa.json").read_text())["repos"] == ["org/api"]
    assert json.loads((apps / "frontend-qa.json").read_text())["repos"] == ["old/api"]
    assert json.loads(repos_path("product").read_text())["repos"] == [{"repo_id": "org/api", "nwo": "org/api"}]


def test_add_repo_requires_explicit_identity_slug(tmp_path):
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text("{}")
    with pytest.raises(RuntimeError, match="identity_slug"):
        add_repo("org/api", str(tmp_path))
