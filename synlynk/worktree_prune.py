"""Sibling Branch Auto-Pruning Engine (#1348).

Detects and auto-prunes patch-equivalent sibling branches (e.g. branches whose
commits have been squash-merged into main or rebased), safely tearing down
their worktrees and deleting local branches.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, List, Optional, Set


def _get_worktree_map(repo_root: str) -> Dict[str, str]:
    """Returns a dict mapping branch name (e.g. 'feat/foo') to worktree path."""
    res = subprocess.run(
        ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        return {}

    branch_to_path: Dict[str, str] = {}
    current_path = ""
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch refs/heads/"):
            branch_name = line[len("branch refs/heads/"):].strip()
            if current_path and branch_name:
                branch_to_path[branch_name] = current_path
        elif not line:
            current_path = ""
    return branch_to_path


def _get_current_branch(repo_root: str) -> str:
    res = subprocess.run(
        ["git", "-C", repo_root, "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.stdout.strip() if res.returncode == 0 else ""


def _is_worktree_dirty(worktree_path: str) -> bool:
    if not os.path.isdir(worktree_path):
        return False
    res = subprocess.run(
        ["git", "-C", worktree_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode != 0 or bool(res.stdout.strip())


def is_patch_equivalent(repo_root: str, branch: str, target_branch: str = "main") -> bool:
    """Checks whether all commits on branch are merged or patch-equivalent to target_branch.

    Uses `git merge-base --is-ancestor` for direct merges and `git cherry` for squash-merges.
    """
    # 1. Direct merge check
    ancestor_res = subprocess.run(
        ["git", "-C", repo_root, "merge-base", "--is-ancestor", branch, target_branch],
        capture_output=True,
        check=False,
    )
    if ancestor_res.returncode == 0:
        return True

    # 2. Patch-equivalence check via git cherry
    cherry_res = subprocess.run(
        ["git", "-C", repo_root, "cherry", target_branch, branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if cherry_res.returncode != 0:
        return False

    lines = [line.strip() for line in cherry_res.stdout.splitlines() if line.strip()]
    if not lines:
        # No commits difference beyond merge base
        return True

    # If all lines start with '-', every patch on the branch exists in target_branch
    return all(line.startswith("-") for line in lines)


def find_patch_equivalent_sibling_branches(
    repo_root: str,
    target_branch: str = "main",
) -> List[str]:
    """Finds all local branches whose work is fully represented in target_branch and safe to prune."""
    repo_root = os.path.abspath(repo_root)
    current_branch = _get_current_branch(repo_root)

    res_branches = subprocess.run(
        ["git", "-C", repo_root, "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res_branches.returncode != 0:
        return []

    all_branches = [b.strip() for b in res_branches.stdout.splitlines() if b.strip()]
    wt_map = _get_worktree_map(repo_root)

    candidates: List[str] = []
    protected = {target_branch, "main", "master", "HEAD", current_branch}

    for branch in all_branches:
        if branch in protected:
            continue

        wt_path = wt_map.get(branch)
        if wt_path and _is_worktree_dirty(wt_path):
            continue

        if is_patch_equivalent(repo_root, branch, target_branch):
            candidates.append(branch)

    return candidates


def prune_sibling_branches(
    repo_root: str,
    target_branch: str = "main",
    dry_run: bool = False,
) -> List[str]:
    """Prunes patch-equivalent sibling branches and their associated worktrees."""
    repo_root = os.path.abspath(repo_root)
    candidates = find_patch_equivalent_sibling_branches(repo_root, target_branch)
    wt_map = _get_worktree_map(repo_root)

    pruned: List[str] = []
    for branch in candidates:
        if dry_run:
            pruned.append(branch)
            continue

        wt_path = wt_map.get(branch)
        if wt_path and os.path.exists(wt_path):
            # Remove worktree registration
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "remove", "--force", wt_path],
                capture_output=True,
                check=False,
            )
            if os.path.exists(wt_path):
                shutil.rmtree(wt_path, ignore_errors=True)

        # Delete local branch
        res_del = subprocess.run(
            ["git", "-C", repo_root, "branch", "-D", branch],
            capture_output=True,
            check=False,
        )
        if res_del.returncode == 0:
            pruned.append(branch)

    if not dry_run:
        subprocess.run(["git", "-C", repo_root, "worktree", "prune"], capture_output=True, check=False)

    return pruned
