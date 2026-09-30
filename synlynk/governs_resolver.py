"""Small, data-driven helpers retained for legacy GOVERNS callers."""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional, Tuple

_IN_BAND_GOAL_RE = re.compile(
    r"(?:linked|governing|parent|master)?\s*goals?[\s\*\*_:]+[`\*\[\(]*(goal-[a-z0-9-]+)", re.I
)
_ISSUE_NUM_RE = re.compile(r"#(\d+)")
_STORY_ID_RE = re.compile(r"\b(story-[a-z0-9-]+)\b", re.I)


def extract_in_band_goal(text: str) -> Optional[str]:
    """Extract an explicit goal ID from the first 50 lines of text."""
    if not text:
        return None
    for line in text.splitlines()[:50]:
        match = _IN_BAND_GOAL_RE.search(line)
        if match:
            return match.group(1).strip("`*[]() ")
    return None


def resolve_parent_goal(
    file_path: Optional[str] = None,
    story_id: Optional[str] = None,
    issue_number: Optional[int | str] = None,
    branch: Optional[str] = None,
    text_content: Optional[str] = None,
    explicit_goal: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    repo_root: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Resolve through workspace-authored candidates; never invent a goal ID."""
    if explicit_goal and str(explicit_goal).strip():
        return str(explicit_goal).strip(), "explicit_argument"

    file_text = ""
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as fh:
                file_text = "".join(fh.readline() for _ in range(50))
        except OSError:
            pass
    combined = "\n".join(filter(None, (text_content, file_text, branch)))
    in_band = extract_in_band_goal(combined)
    if in_band:
        return in_band, "in_band_header"

    owns_conn = conn is None
    if conn is None:
        try:
            from synlynk import _get_db
            conn = _get_db()
        except Exception:
            conn = None
    if conn is None:
        return None, "unresolved"
    try:
        from synlynk.governs_engine import resolve_goal_for_story
        resolved = resolve_goal_for_story(
            conn, title=combined, story_id=story_id, issue_number=issue_number,
            repo_root=repo_root,
        )
        return resolved.goal_id, resolved.reason
    finally:
        if owns_conn:
            conn.close()
