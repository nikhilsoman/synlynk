"""Small helpers for keeping a mergeable pull request based on main."""

import json
import os
import subprocess
from typing import Optional


def rebase_pr_if_behind(
    pr_number: int, repo_path: Optional[str] = None, env: Optional[dict] = None
) -> dict:
    """Rebase and push a mergeable, behind PR onto ``origin/main``.

    The helper is deliberately conservative: GitHub must report both
    ``BEHIND`` and ``MERGEABLE`` before any local git mutation is attempted.
    A failed rebase is aborted and never pushed.  The result is a small
    status dictionary so callers can continue to the merge only when this
    best-effort repair did not fail.
    """
    path = repo_path or os.getcwd()
    try:
        view = subprocess.run(
            [
                "gh", "pr", "view", str(pr_number),
                "--json", "mergeStateStatus,mergeable,headRefName",
            ],
            capture_output=True,
            text=True,
            cwd=path,
            env=env,
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return {"rebased": False, "attempted": False, "reason": str(exc)}
    if view.returncode != 0:
        return {"rebased": False, "attempted": False, "reason": "could not inspect pull request"}
    try:
        metadata = json.loads(view.stdout or "")
    except json.JSONDecodeError:
        return {"rebased": False, "attempted": False, "reason": "invalid pull request metadata"}

    if metadata.get("mergeStateStatus") != "BEHIND":
        return {"rebased": False, "attempted": False, "reason": "pull request is not behind main"}
    if metadata.get("mergeable") != "MERGEABLE":
        return {"rebased": False, "attempted": False, "reason": "pull request is not mergeable"}
    head_branch = metadata.get("headRefName")
    if not head_branch:
        return {"rebased": False, "attempted": False, "reason": "pull request head branch is unknown"}

    def git(*args):
        return subprocess.run(
            ["git", "-C", path, *args],
            capture_output=True,
            text=True,
            check=False,
        )

    fetch = git("fetch", "origin", "main")
    if fetch.returncode != 0:
        return {"rebased": False, "attempted": True, "reason": "could not fetch origin/main"}
    rebase = git("rebase", "origin/main")
    if rebase.returncode != 0:
        git("rebase", "--abort")
        return {"rebased": False, "attempted": True, "reason": "rebase conflicted"}
    push = git("push", "origin", f"HEAD:{head_branch}", "--force-with-lease")
    if push.returncode != 0:
        return {"rebased": False, "attempted": True, "reason": "force-with-lease push failed"}
    return {"rebased": True, "attempted": True, "reason": "rebased onto origin/main"}
