"""qa delegated merge-gate authority (block-only mode).

Computes a fail-closed gate verdict from two signals: CI matrix status and
open Support-Engineer-filed sentinel-alert issues.
See docs/superpowers/specs/2026-08-20-qa-merge-gate-authority-design.md.
"""

import json
import subprocess
from typing import Optional

from synlynk.sentinel import _extract_verified_by_ci
from synlynk import detect_remote_owner_repo


def _qa_gate_ci_status(worktree_path=None, worktree_branch=None) -> Optional[bool]:
    """True/False/None (undeterminable) CI matrix status for the active branch."""
    return _extract_verified_by_ci(
        worktree_path=worktree_path, worktree_branch=worktree_branch
    )


_HIGH_SEVERITY_MARKERS = ("FLATLINE", "QUOTA_EXHAUSTED", "CRITICAL")


def _qa_gate_sentinel_health(owner: str, repo: str) -> Optional[bool]:
    """True (healthy) / False (unhealthy) / None (undeterminable).

    Queries open GitHub issues Support Engineer files for sentinel alerts
    rather than reading the gitignored sentinel.md file.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", f"{owner}/{repo}",
                "--label", "support-engineer",
                "--state", "open",
                "--json", "title,number",
                "--limit", "100",
            ],
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
        issues = json.loads((result.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        return None
    if not isinstance(issues, list):
        return None

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        title = str(issue.get("title") or "")
        if "sentinel_alerts" not in title:
            continue
        upper = title.upper()
        if any(marker in upper for marker in _HIGH_SEVERITY_MARKERS):
            return False
    return True
