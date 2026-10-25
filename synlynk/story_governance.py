"""Universal 4-point attribution governance and verification."""

from __future__ import annotations

import re
import sqlite3


def verify_story_four_point_attribution(conn: sqlite3.Connection, story_id: str) -> dict:
    """Verify that a story is attributed across 4 coordinates: Goal, Epic, Milestone, Arc."""
    row = conn.execute(
        """SELECT s.story_id, s.title, s.goal_id, s.phase, s.engg_domain, s.gh_issue
             FROM stories s
            WHERE s.story_id=?""",
        (story_id,),
    ).fetchone()
    if not row:
        return {"valid": False, "story_id": story_id, "deficiencies": ["story_not_found"]}

    sid, title, goal_id, phase, domain, gh_issue = row
    deficiencies = []

    # 1. Goal coordinate
    if not goal_id:
        contrib = conn.execute(
            "SELECT goal_id FROM goal_contributions WHERE story_id=? AND link_status='linked' LIMIT 1",
            (story_id,),
        ).fetchone()
        if contrib:
            goal_id = contrib[0]
        else:
            deficiencies.append("missing_goal")

    # 2. Epic coordinate (checks gh_issue, title, or roadmap_phases linkage)
    combined_text = f"{title or ''} {gh_issue or ''}"
    has_epic = bool(re.search(r"#\d+|epic-[\w-]+", combined_text))
    if not has_epic:
        phase_row = conn.execute(
            "SELECT arc_version, phase_title FROM roadmap_phases WHERE story_id=? LIMIT 1",
            (story_id,),
        ).fetchone()
        if phase_row:
            has_epic = True
        else:
            deficiencies.append("missing_epic")

    # 3. Milestone coordinate
    has_milestone = bool(re.search(r"v\d+\.\d+\.\d+|milestone:", combined_text))
    if not has_milestone:
        phase_row = conn.execute(
            "SELECT arc_version FROM roadmap_phases WHERE story_id=? LIMIT 1",
            (story_id,),
        ).fetchone()
        if phase_row and phase_row[0]:
            has_milestone = True
        else:
            deficiencies.append("missing_milestone")

    # 4. Arc coordinate
    if not domain and not phase:
        deficiencies.append("missing_arc")

    return {
        "valid": len(deficiencies) == 0,
        "story_id": story_id,
        "goal_id": goal_id,
        "deficiencies": deficiencies,
    }
