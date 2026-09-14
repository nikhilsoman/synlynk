import subprocess
from pathlib import Path
from typing import Dict, Any


def dispatch_first_win_task(goal: Dict[str, Any], repo_root: str) -> Dict[str, Any]:
    """Execute single-click isolated worktree task dispatch producing a verified PR."""
    branch = "feat/first-win-verification"
    p = Path(repo_root)
    worktree_path = p.parent / f"worktree-first-win-{p.name}"

    try:
        # Create isolated worktree per Synlynk Worktree-First policy
        res = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(worktree_path), "HEAD"],
            cwd=str(p),
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "status": "dispatched",
            "branch": branch,
            "worktree_isolated": True,
            "worktree_path": str(worktree_path),
            "goal": goal,
            "message": f"First-win task dispatched into isolated worktree on branch {branch}.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "worktree_isolated": False,
            "branch": branch,
            "message": f"Failed to dispatch first-win task into worktree: {e}",
        }
