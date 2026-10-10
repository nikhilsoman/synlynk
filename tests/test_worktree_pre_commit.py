import shutil
import subprocess
from pathlib import Path


HOOK = Path(__file__).parents[1] / "githooks" / "pre-commit"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def _run_git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )


def _setup_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "codex@example.com")
    _git(repo, "config", "user.name", "Codex")
    (repo / "README").write_text("seed\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "seed")
    githooks = repo / "githooks"
    githooks.mkdir()
    shutil.copy2(HOOK, githooks / "pre-commit")
    (githooks / "pre-commit").chmod(0o755)
    _git(repo, "config", "core.hooksPath", "githooks")
    return repo


def _make_change(repo, name="change"):
    (repo / "README").write_text(f"{name}\n")
    _git(repo, "add", "README")


def test_pre_commit_blocks_feature_branch_in_main_worktree(tmp_path):
    repo = _setup_repo(tmp_path)
    _git(repo, "checkout", "-b", "feat/example")
    _make_change(repo)

    result = _run_git(repo, "commit", "-m", "feature")

    assert result.returncode != 0
    assert "shared main checkout" in result.stderr
    assert "git worktree add worktrees/<name> -b <branch>" in result.stderr
    assert "CLAUDE.md" in result.stderr


def test_pre_commit_blocks_detached_head_in_main_worktree(tmp_path):
    repo = _setup_repo(tmp_path)
    _git(repo, "checkout", "--detach")
    _make_change(repo)

    result = _run_git(repo, "commit", "-m", "detached")

    assert result.returncode != 0
    assert "detached HEAD" in result.stderr


def test_pre_commit_allows_commit_in_linked_worktree(tmp_path):
    repo = _setup_repo(tmp_path)
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-b", "feat/linked", str(linked), "main")
    _make_change(linked, "linked")

    result = _run_git(linked, "commit", "-m", "linked")

    assert result.returncode == 0, result.stderr
