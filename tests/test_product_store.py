import json

import pytest

from synlynk.product_store import (
    github_apps_dir, identity_slug_from_config, migrate_repo_apps_if_needed,
    migrate_state_db_if_needed, product_root, resolve_github_apps_dir, state_db_path,
    types_yaml_path, write_apps_dir_for_init,
)
from synlynk.team import IdentityAlreadyProvisioned, cmd_identity_init_role


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


def test_second_init_fails_closed_before_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    apps = github_apps_dir("vdowrx")
    apps.mkdir(parents=True)
    (apps / "qa.json").write_text(json.dumps({"installation_id": 2, "private_key_path": str(apps / "qa.pem")}))
    (apps / "qa.pem").write_text("dummy")
    monkeypatch.setattr("synlynk.team._build_app_manifest_url", lambda *a, **k: pytest.fail("manifest opened"))
    with pytest.raises(IdentityAlreadyProvisioned, match="second App"):
        cmd_identity_init_role("qa")


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


def test_identity_slug_from_config_resolves_in_git_worktree(tmp_path, monkeypatch):
    main_repo = tmp_path / "main_repo"
    _repo(main_repo, "canonical-product")
    (main_repo / ".git").mkdir()
    worktree_dir = tmp_path / "worktrees" / "chore-some-task"
    worktree_dir.mkdir(parents=True)
    # in a git worktree, .git is a file
    (worktree_dir / ".git").write_text(f"gitdir: {main_repo / '.git' / 'worktrees' / 'chore-some-task'}")

    monkeypatch.chdir(tmp_path)
    # mock subprocess.run for git rev-parse inside worktree
    def fake_run(cmd, cwd=None, **kwargs):
        if cmd[:3] == ["git", "rev-parse", "--path-format=absolute"] and cmd[3] == "--git-common-dir":
            return type("R", (), {"returncode": 0, "stdout": str(main_repo / ".git")})()
        return type("R", (), {"returncode": 1, "stdout": ""})()

    monkeypatch.setattr("synlynk.product_store.subprocess.run", fake_run)
    assert identity_slug_from_config(worktree_dir) == "canonical-product"
