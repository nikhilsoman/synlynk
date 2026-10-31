from synlynk.vizor_daemon import workspace_kind, is_durable_hub_entry, _workspace_index_html


def test_kind_ephemeral_hidden():
    assert is_durable_hub_entry(
        "synlynk",
        {"kind": "ephemeral", "repo_path": "/tmp/x", "path_root": "/tmp/x"},
    ) is False


def test_kind_local_shown(tmp_path):
    repo = tmp_path / "synlynk"
    repo.mkdir()
    assert workspace_kind({"kind": "local", "repo_path": str(repo)}, "synlynk") == "local"
    assert is_durable_hub_entry(
        "synlynk",
        {"kind": "local", "repo_path": str(repo), "path_root": str(repo)},
    ) is True


def test_missing_kind_worktree_is_ephemeral(tmp_path):
    repo = tmp_path / ".worktrees" / "djob-abc"
    repo.mkdir(parents=True)
    assert workspace_kind({"repo_path": str(repo)}, "djob-abc") == "ephemeral"
    assert is_durable_hub_entry("djob-abc", {"repo_path": str(repo)}) is False


def test_dev_clone_without_kind_is_local(tmp_path):
    repo = tmp_path / "dev" / "coldtest"
    repo.mkdir(parents=True)
    assert workspace_kind({"repo_path": str(repo)}, "coldtest") == "local"
    assert is_durable_hub_entry("coldtest", {"repo_path": str(repo)}) is True


def test_hub_html_omits_ephemeral(monkeypatch, tmp_path):
    durable = tmp_path / "synlynk"
    durable.mkdir()
    (durable / "state.db").write_bytes(b"")
    djob = tmp_path / ".worktrees" / "djob-abc"
    djob.mkdir(parents=True)
    (djob / "state.db").write_bytes(b"")
    registry = {
        "synlynk": {
            "kind": "local",
            "repo_path": str(durable),
            "canonical_path": str(durable / "state.db"),
            "path_root": str(durable),
        },
        "djob-abc": {
            "repo_path": str(djob),
            "canonical_path": str(djob / "state.db"),
        },
    }
    monkeypatch.setattr("synlynk.vizor_daemon._registered_workspaces", lambda: {
        slug: entry for slug, entry in registry.items() if is_durable_hub_entry(slug, entry)
    })
    html = _workspace_index_html()
    assert "synlynk" in html
    assert "djob-abc" not in html
