"""GOVERNS backlog automation: dedup, goal resolution, and filing for
discovered/planned work. See docs/superpowers/specs/2026-08-29-governs-backlog-automation-design.md.
"""

import hashlib
import json
import re
import subprocess


def compute_signal_hash(title: str, source: str) -> str:
    """Stable hash of a normalized title + source, used as the dedup key."""
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.md5(f"{source}:{normalized}".encode()).hexdigest()[:16]


def has_ledger_duplicate(conn, signal_hash: str) -> bool:
    """True if signal_hash already has a backlog_proposals row (filed or declined)."""
    row = conn.execute(
        "SELECT 1 FROM backlog_proposals WHERE signal_hash=? LIMIT 1", (signal_hash,)
    ).fetchone()
    return row is not None


def record_proposal(conn, signal_hash: str, title: str, source: str, status: str,
                     gh_issue_url, story_id, goal_id, goal_match_basis, session_id) -> None:
    """Insert a backlog_proposals ledger row. Caller commits."""
    conn.execute(
        "INSERT INTO backlog_proposals "
        "(signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_hash, title, source, status, gh_issue_url, story_id, goal_id, goal_match_basis, session_id),
    )
    conn.commit()


def search_similar_issues(title: str) -> list:
    """Search open+closed GitHub issues for similar titles via `gh issue list --search`.

    Returns a list of {"title": ..., "url": ...} dicts, or [] on any gh failure.
    """
    result = subprocess.run(
        ["gh", "issue", "list", "--search", title, "--state", "all",
         "--json", "title,url", "--limit", "10"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return []
