import os
import subprocess
import pytest

from synlynk.dispatch import get_worktree_epoch, _build_subprocess_env


def _setup_repo_with_commit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True, capture_output=True)

    (repo / "file.txt").write_text("commit content")
    # Commit with a known fixed author/committer date
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = "1700000000 +0000"
    env["GIT_COMMITTER_DATE"] = "1700000000 +0000"
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixed date commit"], cwd=str(repo), check=True, capture_output=True, env=env)
    return str(repo)


def test_get_worktree_epoch_reads_commit_timestamp(tmp_path):
    repo_dir = _setup_repo_with_commit(tmp_path)
    epoch = get_worktree_epoch(repo_dir)
    assert epoch == "1700000000"


def test_source_date_epoch_injected_into_subprocess_env(tmp_path):
    repo_dir = _setup_repo_with_commit(tmp_path)
    env = _build_subprocess_env(
        agent="codex",
        overrides={},
        requires_gh_write=False,
        story_id=None,
        worktree_path=repo_dir,
    )
    assert "SOURCE_DATE_EPOCH" in env
    assert env["SOURCE_DATE_EPOCH"] == "1700000000"


def test_get_worktree_epoch_fallback_on_non_git_dir(tmp_path):
    non_git = str(tmp_path / "non_git")
    os.makedirs(non_git, exist_ok=True)
    epoch = get_worktree_epoch(non_git)
    assert epoch.isdigit()
    assert int(epoch) > 0
