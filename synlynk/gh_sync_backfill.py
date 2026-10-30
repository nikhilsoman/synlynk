"""One-time full-history backfill to GitHub (gh:#2653 design, §5).

Backfill is unconditional: every story across every arc regardless of status,
with no skip rule or volume cap, per explicit user instruction overriding an
earlier draft that proposed skipping old shipped-arc stories.
"""

from synlynk import gh_sync


def run_backfill(conn, owner: str, repo: str, role: str = "pm") -> dict:
    arc_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM roadmap_arcs "
            "WHERE is_milestone_eligible = 1 ORDER BY id ASC"
        ).fetchall()
    ]
    for arc_id in arc_ids:
        gh_sync.sync_arc(
            conn, arc_id=arc_id, owner=owner, repo=repo, role=role
        )

    story_ids = [
        row[0]
        for row in conn.execute(
            "SELECT story_id FROM stories ORDER BY story_id ASC"
        ).fetchall()
    ]
    for story_id in story_ids:
        phase = conn.execute(
            "SELECT arc_version FROM roadmap_phases WHERE story_id=?", (story_id,)
        ).fetchone()
        milestone_number = None
        if phase:
            mapped = conn.execute(
                "SELECT gm.github_number FROM github_sync_map gm "
                "JOIN roadmap_arcs ra ON ra.id = CAST(gm.entity_id AS INTEGER) "
                "WHERE gm.entity_type='roadmap_arc' AND ra.version=?",
                (phase[0],),
            ).fetchone()
            milestone_number = mapped[0] if mapped else None
        gh_sync.sync_story(
            conn,
            story_id=story_id,
            owner=owner,
            repo=repo,
            milestone_number=milestone_number,
            role=role,
        )

    decision_ids = [
        row[0]
        for row in conn.execute(
            "SELECT decision_id FROM decisions ORDER BY decision_id ASC"
        ).fetchall()
    ]
    for decision_id in decision_ids:
        gh_sync.sync_decision(
            conn,
            decision_id=decision_id,
            owner=owner,
            repo=repo,
            role=role,
        )

    return {
        "arcs_synced": len(arc_ids),
        "stories_synced": len(story_ids),
        "decisions_synced": len(decision_ids),
    }
