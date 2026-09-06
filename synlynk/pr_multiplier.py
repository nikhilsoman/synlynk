"""Post-hoc PR review-cycle multiplier for capability_ratings quality."""

import json
import subprocess
from typing import Optional

_MULTIPLIER_BASE = 1.10
_MULTIPLIER_DECAY = 0.825
_MULTIPLIER_FLOOR = 0.25


def _review_cycle_multiplier(n: int) -> float:
    """Returns the review-cycle multiplier for n review cycles.

    n=1 means a clean first-pass approval and yields a 10% bonus.
    The multiplier decays geometrically and floors at 0.25.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1 (got {n}); n=1 represents a clean first-pass approval")
    multiplier = _MULTIPLIER_BASE * (_MULTIPLIER_DECAY ** (n - 1))
    return max(multiplier, _MULTIPLIER_FLOOR)


def _apply_review_cycle_multiplier(conn, pr_number: int, changes_requested_count: int) -> None:
    """Applies the multiplier to all capability_ratings rows for pr_number, exactly once."""
    already_applied = conn.execute(
        "SELECT 1 FROM pr_multiplier_applied WHERE pr_number=?",
        (pr_number,),
    ).fetchone()
    if already_applied:
        return

    n = 1 + changes_requested_count
    multiplier = _review_cycle_multiplier(n)
    rows = conn.execute(
        "SELECT id, quality FROM capability_ratings WHERE pr_number=?",
        (pr_number,),
    ).fetchall()
    for row_id, quality in rows:
        new_quality = max(0.0, min(10.0, quality * multiplier))
        conn.execute(
            "UPDATE capability_ratings SET quality=? WHERE id=?",
            (new_quality, row_id),
        )
    conn.execute(
        "INSERT INTO pr_multiplier_applied (pr_number, applied_at) VALUES (?, datetime('now'))",
        (pr_number,),
    )
    conn.commit()


def _current_pr_number(pr_number: Optional[int] = None) -> Optional[int]:
    """Resolves the current PR number via gh, or None if unavailable.

    Dispatch review jobs check out `dispatch/<harness>/job-<id>`, which has no
    PR of its own. Fall back to the GitHub commit-pulls API for HEAD (#1432).
    """
    if pr_number is not None:
        try:
            return int(pr_number)
        except (TypeError, ValueError):
            return None
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "number"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    except Exception:
        result = None
    if result is not None and result.returncode == 0:
        try:
            payload = json.loads((result.stdout or "").strip() or "{}")
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            number = payload.get("number")
            if isinstance(number, int):
                return number
    return _current_pr_number_from_head_sha()


def _current_pr_number_from_head_sha() -> Optional[int]:
    """Look up an open (or any) PR that contains HEAD — job-branch fallback."""
    try:
        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if sha_proc.returncode != 0:
        return None
    sha = (sha_proc.stdout or "").strip()
    if not sha:
        return None
    try:
        from synlynk import detect_remote_owner_repo
        owner, repo = detect_remote_owner_repo()
    except Exception:
        owner, repo = None, None
    if not owner or not repo:
        return None
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/commits/{sha}/pulls"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        pulls = json.loads((result.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(pulls, list):
        return None
    open_nums = [
        p.get("number") for p in pulls
        if isinstance(p, dict) and isinstance(p.get("number"), int)
        and str(p.get("state") or "").lower() == "open"
    ]
    if open_nums:
        return open_nums[0]
    for p in pulls:
        if isinstance(p, dict) and isinstance(p.get("number"), int):
            return p["number"]
    return None


def _is_github_remote() -> bool:
    """Returns True only when the current checkout is on a GitHub remote."""
    from synlynk import detect_remote_owner_repo

    owner, repo = detect_remote_owner_repo()
    return bool(owner and repo)
