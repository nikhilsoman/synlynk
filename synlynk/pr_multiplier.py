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
    """Applies the multiplier to all capability_ratings rows for pr_number."""
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
    conn.commit()


def _current_pr_number() -> Optional[int]:
    """Resolves the current branch PR number via gh, or None if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "number"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads((result.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    number = payload.get("number")
    return number if isinstance(number, int) else None


def _is_github_remote() -> bool:
    """Returns True only when the current checkout is on a GitHub remote."""
    from synlynk import detect_remote_owner_repo

    owner, repo = detect_remote_owner_repo()
    return bool(owner and repo)
