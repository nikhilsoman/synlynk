"""Adaptive Scope-Bounded Sparse Worktree Engine (#1389, #1390, #1391).

Provides high-performance cone-mode sparse worktrees for multi-agent dispatches,
preventing storage amplification and reducing checkout latency by only materializing
mandatory configuration and task-scoped paths.
"""

from __future__ import annotations

import os
import subprocess
from typing import List, Optional, Sequence

MANDATORY_SPARSE_CONE_DIRS = (".synlynk", "project-docs", "tests", "synlynk")


def is_sparse_worktree(worktree_path: str) -> bool:
    """Returns True if the given worktree has sparse checkout active."""
    if not os.path.isdir(worktree_path):
        return False
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip().lower() in ("true", "1")
    except OSError:
        return False


def create_sparse_cone_worktree(
    repo_root: str,
    worktree_path: str,
    branch: str,
    base_ref: str,
    scoped_paths: Optional[Sequence[str]] = None,
) -> bool:
    """Creates an isolated git worktree configured with cone-mode sparse checkout.

    Lifecycle:
    1. git worktree add --no-checkout <path> -b <branch> <base_ref>
    2. git -C <path> config extensions.worktreeConfig true
    3. git -C <path> sparse-checkout init --cone
    4. git -C <path> sparse-checkout set <cone_dirs...>
    5. git -C <path> checkout <branch>
    """
    repo_root = os.path.abspath(repo_root)
    worktree_path = os.path.abspath(worktree_path)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # 1. Add worktree without materializing files
    add_cmd = ["git", "-C", repo_root, "worktree", "add", "--no-checkout", worktree_path, "-b", branch, base_ref]
    res_add = subprocess.run(add_cmd, capture_output=True, text=True, check=False)
    if res_add.returncode != 0:
        # If branch already exists (e.g. existing tracking branch), try without -b
        add_retry = ["git", "-C", repo_root, "worktree", "add", "--no-checkout", worktree_path, branch]
        res_retry = subprocess.run(add_retry, capture_output=True, text=True, check=False)
        if res_retry.returncode != 0:
            return False

    # 2. Enable worktree-scoped configuration
    res_cfg = subprocess.run(
        ["git", "-C", worktree_path, "config", "extensions.worktreeConfig", "true"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res_cfg.returncode != 0:
        return False

    # 3. Initialize sparse-checkout in cone mode
    res_init = subprocess.run(
        ["git", "-C", worktree_path, "sparse-checkout", "init", "--cone"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res_init.returncode != 0:
        return False

    # 4. Resolve cone directories
    cone_set = set(MANDATORY_SPARSE_CONE_DIRS)
    for p in scoped_paths or []:
        cleaned = p.strip().lstrip("./")
        if not cleaned:
            continue
        first_segment = cleaned.split("/", 1)[0]
        cone_set.add(first_segment)

    set_cmd = ["git", "-C", worktree_path, "sparse-checkout", "set"] + sorted(cone_set)
    res_set = subprocess.run(set_cmd, capture_output=True, text=True, check=False)
    if res_set.returncode != 0:
        return False

    # 5. Checkout the branch to populate the cone
    res_co = subprocess.run(
        ["git", "-C", worktree_path, "checkout", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return res_co.returncode == 0


def ensure_path_in_sparse_cone(worktree_path: str, target_path: str) -> bool:
    """Dynamically adds a target path or directory to an active sparse worktree cone."""
    if not is_sparse_worktree(worktree_path):
        return True

    cleaned = target_path.strip().lstrip("./")
    if not cleaned:
        return True

    res = subprocess.run(
        ["git", "-C", worktree_path, "sparse-checkout", "add", cleaned],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode == 0
