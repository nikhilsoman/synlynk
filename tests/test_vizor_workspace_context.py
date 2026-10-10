import json
from pathlib import Path
import pytest
from synlynk.vizor_daemon import WorkspaceContext, resolve_workspace_context

def test_resolve_workspace_context_valid(tmp_path, monkeypatch):
    reg_file = tmp_path / "product-registry.json"
    repo_dir = tmp_path / "repo_a"
    repo_dir.mkdir()
    db_file = tmp_path / "state.db"
    db_file.write_text("")
    
    registry_data = {
        "products": {
            "demo-app": {
                "slug": "demo-app",
                "repo_path": str(repo_dir),
                "canonical_path": str(db_file),
            }
        },
        "version": 1
    }
    reg_file.write_text(json.dumps(registry_data))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    ctx = resolve_workspace_context("demo-app")
    assert ctx is not None
    assert isinstance(ctx, WorkspaceContext)
    assert ctx.slug == "demo-app"
    assert ctx.repo_path == repo_dir
    assert ctx.db_path == db_file

def test_resolve_workspace_context_rejects_invalid_or_missing(tmp_path, monkeypatch):
    reg_file = tmp_path / "product-registry.json"
    reg_file.write_text(json.dumps({"products": {}, "version": 1}))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(reg_file))

    assert resolve_workspace_context("nonexistent") is None
    assert resolve_workspace_context("") is None
    assert resolve_workspace_context("../../etc/passwd") is None
    assert resolve_workspace_context("slug with spaces") is None
