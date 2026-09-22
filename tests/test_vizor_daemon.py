import os
import json
from pathlib import Path

import pytest

from synlynk import vizor_daemon


def test_poll_interval_default(monkeypatch):
    monkeypatch.delenv("SYNLYNK_VIZOR_POLL_INTERVAL", raising=False)
    assert vizor_daemon.poll_interval() == 15


def test_poll_interval_override(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "5")
    assert vizor_daemon.poll_interval() == 5


def test_poll_interval_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SYNLYNK_VIZOR_POLL_INTERVAL", "not-a-number")
    assert vizor_daemon.poll_interval() == 15


def test_workspace_render_context_chdirs_and_restores(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_cwd = os.getcwd()

    seen_cwd = {}
    with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
        seen_cwd["inside"] = Path(os.getcwd())

    assert seen_cwd["inside"] == repo.resolve()
    assert Path(os.getcwd()) == Path(original_cwd)


def test_workspace_render_context_restores_get_db_on_exception(tmp_path):
    import synlynk.viz as viz_module

    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    original_get_db = viz_module._get_db

    with pytest.raises(RuntimeError):
        with vizor_daemon.workspace_render_context(repo, db_path, tmp_path / "cache"):
            raise RuntimeError("boom")

    assert viz_module._get_db is original_get_db


def _seed_registry(reg_path, slug, repo_path, db_path):
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps({
        "version": 1,
        "products": {
            slug: {
                "product_id": f"pid-{slug}",
                "slug": slug,
                "canonical_path": str(db_path),
                "repo_path": str(repo_path),
                "mode": "canonical",
                "lineage_generation": 1,
                "state": "active",
            }
        },
    }))


def test_poll_once_writes_cache_per_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))

    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / ".synlynk").mkdir()
    (repo_a / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": "a"}))
    db_a = tmp_path / "a-state.db"
    db_a.write_bytes(b"")

    reg_path = tmp_path / "registry.json"
    _seed_registry(reg_path, "a", repo_a, db_a)

    cache_root = tmp_path / "cache-root"
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_root)

    def fake_generate_viz_data():
        return {
            "workspace": {"name": "a", "updated_at": "now", "repos": []},
            "notes": {},
            "workspace_map": {"edges": [], "edge_types": {}},
            "observatory": {},
        }

    import synlynk.viz as viz_module
    monkeypatch.setattr(viz_module, "generate_viz_data", fake_generate_viz_data)

    from synlynk import vizor_daemon
    results = vizor_daemon.poll_once(port=8721)

    assert results == {"a": "ok"}
    assert (cache_root / "a" / "manifest.json").exists()


def test_poll_once_isolates_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))

    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    db_a = tmp_path / "a-state.db"
    db_a.write_bytes(b"")
    db_b = tmp_path / "b-state.db"
    db_b.write_bytes(b"")

    reg_path = tmp_path / "registry.json"
    reg_path.write_text(json.dumps({
        "version": 1,
        "products": {
            "a": {
                "product_id": "pid-a", "slug": "a", "canonical_path": str(db_a),
                "repo_path": str(repo_a), "mode": "canonical",
                "lineage_generation": 1, "state": "active",
            },
            "b": {
                "product_id": "pid-b", "slug": "b", "canonical_path": str(db_b),
                "repo_path": str(repo_b), "mode": "canonical",
                "lineage_generation": 1, "state": "active",
            },
        },
    }))

    cache_root = tmp_path / "cache-root"
    monkeypatch.setattr("synlynk.vizor_daemon.CACHE_ROOT", cache_root)

    import synlynk.viz as viz_module

    def flaky_generate_viz_data():
        if Path(os.getcwd()) == repo_a.resolve():
            raise RuntimeError("boom")
        return {
            "workspace": {"name": "b", "updated_at": "now", "repos": []},
            "notes": {},
            "workspace_map": {"edges": [], "edge_types": {}},
            "observatory": {},
        }

    monkeypatch.setattr(viz_module, "generate_viz_data", flaky_generate_viz_data)

    from synlynk import vizor_daemon
    results = vizor_daemon.poll_once(port=8721)

    assert results["a"].startswith("error:")
    assert results["b"] == "ok"
    assert (cache_root / "b" / "manifest.json").exists()
