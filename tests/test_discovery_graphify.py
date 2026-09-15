# tests/test_discovery_graphify.py
import json
import pytest
from pathlib import Path
from synlynk.discovery import scan_workspace_static


def test_scan_workspace_static_fallback_when_graphify_absent(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: False)
    (tmp_path / "app.py").write_text("def hello(): pass")

    res = scan_workspace_static(str(tmp_path))
    assert "domain" in res
    assert "physical" in res
    assert "logical" in res
    assert res.get("knowledge_graph") is None or res["knowledge_graph"]["available"] is False


def test_scan_workspace_static_uses_graphify_cache_and_checks_staleness(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: True)
    monkeypatch.setattr("synlynk.discovery._get_head_commit", lambda root: "commit_abc123")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = {
        "built_at_commit": "commit_abc123",
        "nodes_count": 42,
        "edges_count": 84,
        "communities_count": 5,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest))

    res = scan_workspace_static(str(tmp_path))
    assert res["knowledge_graph"]["available"] is True
    assert res["knowledge_graph"]["stale"] is False
    assert res["knowledge_graph"]["nodes_count"] == 42
    assert res["knowledge_graph"]["edges_count"] == 84
    assert res["knowledge_graph"]["communities_count"] == 5
    assert res["knowledge_graph"]["built_at_commit"] == "commit_abc123"


def test_scan_workspace_static_flags_stale_when_head_advanced(tmp_path, monkeypatch):
    monkeypatch.setattr("synlynk.discovery._is_graphify_installed", lambda: True)
    monkeypatch.setattr("synlynk.discovery._get_head_commit", lambda root: "commit_xyz789")

    out_dir = tmp_path / ".synlynk" / "graphify-out"
    out_dir.mkdir(parents=True)
    manifest = {
        "built_at_commit": "commit_abc123",
        "nodes_count": 42,
        "edges_count": 84,
        "communities_count": 5,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest))

    res = scan_workspace_static(str(tmp_path))
    assert res["knowledge_graph"]["available"] is True
    assert res["knowledge_graph"]["stale"] is True
