import os
import subprocess
import pytest

from synlynk.worktree_prune import (
    find_patch_equivalent_sibling_branches,
    prune_sibling_branches,
)


def _setup_prune_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True, capture_output=True)

    # Initial commit on main
    (repo / "README.md").write_text("# Main Repo")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init main"], cwd=str(repo), check=True, capture_output=True)
    return str(repo)


def test_detects_patch_equivalent_squashed_branches(tmp_path):
    repo_dir = _setup_prune_repo(tmp_path)

    # 1. Create feature branch with a change
    subprocess.run(["git", "checkout", "-b", "feat/squashed-feature"], cwd=repo_dir, check=True, capture_output=True)
    (tmp_path / "repo" / "feature.txt").write_text("feature content")
    subprocess.run(["git", "add", "feature.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add feature"], cwd=repo_dir, check=True, capture_output=True)

    # 2. Return to main and squash-merge the feature branch
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "merge", "--squash", "feat/squashed-feature"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "squash merge feature (#101)"], cwd=repo_dir, check=True, capture_output=True)

    # 3. Detect patch-equivalent branch
    candidates = find_patch_equivalent_sibling_branches(repo_dir, target_branch="main")
    assert "feat/squashed-feature" in candidates

    # 4. Prune it
    pruned = prune_sibling_branches(repo_dir, target_branch="main", dry_run=False)
    assert "feat/squashed-feature" in pruned

    # 5. Verify branch is gone
    branches = subprocess.run(["git", "branch"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout
    assert "feat/squashed-feature" not in branches


def test_preserves_unmerged_or_dirty_branches(tmp_path):
    repo_dir = _setup_prune_repo(tmp_path)

    # Create unmerged branch
    subprocess.run(["git", "checkout", "-b", "feat/unmerged-work"], cwd=repo_dir, check=True, capture_output=True)
    (tmp_path / "repo" / "work.txt").write_text("work in progress")
    subprocess.run(["git", "add", "work.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "work in progress"], cwd=repo_dir, check=True, capture_output=True)

    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)

    # Should NOT be identified as patch-equivalent
    candidates = find_patch_equivalent_sibling_branches(repo_dir, target_branch="main")
    assert "feat/unmerged-work" not in candidates

    pruned = prune_sibling_branches(repo_dir, target_branch="main", dry_run=False)
    assert "feat/unmerged-work" not in pruned

    branches = subprocess.run(["git", "branch"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout
    assert "feat/unmerged-work" in branches


def test_prune_removes_worktree_and_branch(tmp_path):
    repo_dir = _setup_prune_repo(tmp_path)
    wt_dir = str(tmp_path / "wt-squash")

    # Create worktree on branch feat/wt-branch
    subprocess.run(
        ["git", "worktree", "add", wt_dir, "-b", "feat/wt-branch", "main"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    (tmp_path / "wt-squash" / "wt_file.txt").write_text("wt file content")
    subprocess.run(["git", "add", "wt_file.txt"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "commit in wt"], cwd=wt_dir, check=True, capture_output=True)

    # Squash merge into main
    subprocess.run(["git", "merge", "--squash", "feat/wt-branch"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "squash merge wt branch"], cwd=repo_dir, check=True, capture_output=True)

    # Prune should remove worktree and delete branch
    pruned = prune_sibling_branches(repo_dir, target_branch="main", dry_run=False)
    assert "feat/wt-branch" in pruned
    assert not os.path.exists(wt_dir)

    branches = subprocess.run(["git", "branch"], cwd=repo_dir, capture_output=True, text=True, check=True).stdout
    assert "feat/wt-branch" not in branches
