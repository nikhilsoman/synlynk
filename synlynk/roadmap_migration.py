"""Roadmap migration and foreign-key backfill mechanics.

Retargets cost_entries.phase_id/epic_id to goals.id per
docs/superpowers/specs/2026-11-13-fully-derived-roadmap-approach-c-design.md.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List


def backfill_cost_entries_goals(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Backfill cost_entries.phase_id from legacy phase IDs to corresponding goals.id.
    
    Returns:
        Dict with keys:
          - migrated_count: int
          - ambiguous_phases: List[Dict[str, Any]]
    """
    # Find legacy phases table if renamed or existing
    phase_table = None
    for candidate in ("roadmap_phases_legacy", "roadmap_phases"):
        cur = conn.execute(
            "SELECT type FROM sqlite_master WHERE name = ?", (candidate,)
        )
        row = cur.fetchone()
        if row and row[0] == "table":
            phase_table = candidate
            break

    if not phase_table:
        return {"migrated_count": 0, "ambiguous_phases": []}

    legacy_phases = conn.execute(
        f"SELECT id, arc_version, phase_title FROM {phase_table}"
    ).fetchall()

    ambiguous_phases: List[Dict[str, Any]] = []
    phase_to_goal_map: Dict[int, int] = {}

    for p in legacy_phases:
        p_id = p[0]
        arc = p[1]
        title = p[2]

        # Find matching goals
        matching_goals = conn.execute(
            "SELECT id FROM goals WHERE arc_version = ? AND phase_title = ? ORDER BY id ASC",
            (arc, title)
        ).fetchall()

        if not matching_goals:
            continue

        goal_ids = [g[0] for g in matching_goals]
        # Lowest goals.id wins on ties
        phase_to_goal_map[p_id] = goal_ids[0]

        if len(goal_ids) > 1:
            ambiguous_phases.append({
                "legacy_phase_id": p_id,
                "arc_version": arc,
                "phase_title": title,
                "selected_goal_id": goal_ids[0],
                "candidate_goal_ids": goal_ids,
            })

    migrated_count = 0
    for old_pid, new_gid in phase_to_goal_map.items():
        res = conn.execute(
            "UPDATE cost_entries SET phase_id = ? WHERE phase_id = ?",
            (new_gid, old_pid)
        )
        migrated_count += res.rowcount

    conn.commit()

    return {
        "migrated_count": migrated_count,
        "ambiguous_phases": ambiguous_phases,
    }
