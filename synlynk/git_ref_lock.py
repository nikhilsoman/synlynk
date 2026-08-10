"""Advisory locking for git operations that mutate refs shared by worktrees."""

import fcntl
import os
from contextlib import contextmanager


def _common_git_dir(repo_path: str) -> str:
    git_path = os.path.join(repo_path, ".git")
    if os.path.isdir(git_path):
        return git_path

    with open(git_path, encoding="utf-8") as git_file:
        gitdir_line = git_file.read().strip()
    if not gitdir_line.startswith("gitdir:"):
        raise RuntimeError(f"Unable to resolve git directory for {repo_path}")
    gitdir = gitdir_line[len("gitdir:"):].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(repo_path, gitdir)
    gitdir = os.path.realpath(gitdir)

    commondir_file = os.path.join(gitdir, "commondir")
    if os.path.exists(commondir_file):
        with open(commondir_file, encoding="utf-8") as common_file:
            commondir = common_file.read().strip()
        return os.path.realpath(os.path.join(gitdir, commondir))
    return gitdir


@contextmanager
def git_ref_operation_lock(repo_path: str):
    """Serialize local git ref mutations across linked worktrees."""
    lock_path = os.path.join(_common_git_dir(os.path.realpath(repo_path)), "synlynk-ref-operations.lock")
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
