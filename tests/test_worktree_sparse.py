import os
import subprocess
import pytest

from synlynk.worktree_sparse import (
    create_sparse_cone_worktree,
    ensure_path_in_sparse_cone,
    is_sparse_worktree,
)


def _setup_fixture_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True, capture_output=True)

    # Create directories and files
    (repo / ".synlynk").mkdir()
    (repo / ".synlynk" / "config.json").write_text('{"worktree": {"mode": "sparse"}}')

    (repo / "project-docs").mkdir()
    (repo / "project-docs" / "roadmap.md").write_text("# Roadmap")

    (repo / "synlynk").mkdir()
    (repo / "synlynk" / "app.py").write_text("print('hello')")

    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text("def test_ok(): pass")

    # Large / extraneous directories that should NOT be in initial cone
    (repo / "website" / "assets").mkdir(parents=True)
    (repo / "website" / "assets" / "large.png").write_bytes(b"LARGE_IMAGE_DATA")

    (repo / "docs" / "archive").mkdir(parents=True)
    (repo / "docs" / "archive" / "old.md").write_text("Old doc")

    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo), check=True, capture_output=True)
    return str(repo)


def test_create_sparse_cone_worktree_includes_mandatory_dirs(tmp_path):
    repo_dir = _setup_fixture_repo(tmp_path)
    wt_dir = str(tmp_path / "wt1")

    ok = create_sparse_cone_worktree(
        repo_root=repo_dir,
        worktree_path=wt_dir,
        branch="dispatch/agent/job-1",
        base_ref="HEAD",
        scoped_paths=["synlynk"],
    )
    assert ok is True
    assert is_sparse_worktree(wt_dir) is True

    # Invariants: .synlynk, project-docs, synlynk must exist
    assert os.path.isfile(os.path.join(wt_dir, ".synlynk", "config.json"))
    assert os.path.isfile(os.path.join(wt_dir, "project-docs", "roadmap.md"))
    assert os.path.isfile(os.path.join(wt_dir, "synlynk", "app.py"))

    # Unscoped paths must NOT be materialized on disk
    assert not os.path.exists(os.path.join(wt_dir, "website", "assets", "large.png"))
    assert not os.path.exists(os.path.join(wt_dir, "docs", "archive", "old.md"))


def test_ensure_path_in_sparse_cone_expands_set(tmp_path):
    repo_dir = _setup_fixture_repo(tmp_path)
    wt_dir = str(tmp_path / "wt2")

    create_sparse_cone_worktree(
        repo_root=repo_dir,
        worktree_path=wt_dir,
        branch="dispatch/agent/job-2",
        base_ref="HEAD",
        scoped_paths=["synlynk"],
    )
    assert not os.path.exists(os.path.join(wt_dir, "website", "assets", "large.png"))

    # Dynamically expand cone to include website
    expanded = ensure_path_in_sparse_cone(wt_dir, "website/assets")
    assert expanded is True
    assert os.path.isfile(os.path.join(wt_dir, "website", "assets", "large.png"))


def test_is_sparse_worktree_returns_false_on_full_repo(tmp_path):
    repo_dir = _setup_fixture_repo(tmp_path)
    assert is_sparse_worktree(repo_dir) is False


def test_dispatch_create_job_worktree_honors_sparse_config(tmp_path, monkeypatch, git_worktree_repo):
    from synlynk.dispatch import _create_job_worktree
    repo_dir = _setup_fixture_repo(tmp_path)
    monkeypatch.chdir(repo_dir)
    # Mock load_config returning worktree.mode: sparse
    monkeypatch.setattr(
        "synlynk.dispatch._pkg",
        lambda name, default=None: (lambda: {"worktree": {"mode": "sparse"}}) if name == "load_config" else default,
    )
    info = _create_job_worktree("job-testsparse", "codex", base="HEAD")
    assert info["path"]
    assert is_sparse_worktree(info["path"]) is True
    assert os.path.isfile(os.path.join(info["path"], ".synlynk", "config.json"))
    assert not os.path.exists(os.path.join(info["path"], "website", "assets", "large.png"))
