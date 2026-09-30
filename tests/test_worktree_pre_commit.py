import os
import subprocess
from pathlib import Path


HOOK = Path(__file__).parents[1] / "githooks" / "pre-commit"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_pre_commit_blocks_feature_branch_in_main_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "codex@example.com")
    _git(repo, "config", "user.name", "Codex")
    (repo / "README").write_text("seed\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "checkout", "-b", "feat/example")

    result = subprocess.run(
        [str(HOOK)], cwd=repo, capture_output=True, text=True, env=os.environ.copy()
    )

    assert result.returncode != 0
    assert "shared main checkout" in result.stderr
    assert "git worktree add worktrees/<name> -b <branch>" in result.stderr
    assert "CLAUDE.md" in result.stderr
