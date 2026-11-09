import json

import pytest


def test_load_native_capabilities_reads_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "native"
    registry_dir.mkdir(parents=True)
    manifest = {
        "capability_id": "worktree-clean",
        "name": "worktree_cleanup",
        "source": "native",
        "description": "Removes merged/stale worktrees and their branches.",
        "purpose": "Keep the repo's worktree set from accumulating stale entries.",
        "scope": "filesystem:worktrees,git:branches",
        "auth": {"type": "none"},
        "enforced_hook": "synlynk.worktree:cmd_worktree_clean",
        "harness_compat": "any",
        "workspace_id": "local",
        "owner": "synlynk-core",
        "version": "1.0.0",
    }
    (registry_dir / "worktree-clean.json").write_text(json.dumps(manifest))

    from synlynk import capability_registry
    caps = capability_registry.load_native_capabilities()

    assert len(caps) == 1
    assert caps[0]["capability_id"] == "worktree-clean"
    assert caps[0]["enforced_hook"] == "synlynk.worktree:cmd_worktree_clean"


def test_load_native_capabilities_rejects_manifest_missing_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "native"
    registry_dir.mkdir(parents=True)
    (registry_dir / "broken.json").write_text(json.dumps({"capability_id": "broken"}))

    from synlynk import capability_registry
    with pytest.raises(ValueError, match="missing required"):
        capability_registry.load_native_capabilities()


def test_load_native_capabilities_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import capability_registry
    assert capability_registry.load_native_capabilities() == []


def test_load_local_capabilities_scoped_by_harness_bindings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "local"
    registry_dir.mkdir(parents=True)
    manifest = {
        "capability_id": "stitch-ui-driver",
        "name": "generate_screen_from_text",
        "source": "local_harness",
        "description": "Generates a UI screen mockup from a text prompt via the Stitch MCP server.",
        "purpose": "Design-stage mockup generation.",
        "scope": "mcp:stitch",
        "auth": {"type": "mcp_server", "server": "stitch"},
        "enforced_hook": None,
        "harness_compat": ["claude"],
        "workspace_id": "local",
        "owner": "designer",
        "version": "1.0.0",
    }
    (registry_dir / "stitch-ui-driver.json").write_text(json.dumps(manifest))

    from synlynk import capability_registry
    caps = capability_registry.load_local_capabilities(harness="claude")
    assert len(caps) == 1
    caps_other = capability_registry.load_local_capabilities(harness="grok")
    assert caps_other == []


def test_load_native_capabilities_includes_gh_sync_roadmap():
    from synlynk import capability_registry
    caps = capability_registry.load_native_capabilities()
    ids = {c["capability_id"] for c in caps}
    assert "gh-sync-roadmap" in ids
    entry = next(c for c in caps if c["capability_id"] == "gh-sync-roadmap")
    assert entry["enforced_hook"] == "synlynk.gh_sync_cli:cmd_sync_roadmap"


