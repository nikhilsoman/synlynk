"""CLI entry point for ``synlynk gh sync-roadmap``."""

from synlynk import _get_db


def cmd_sync_roadmap(
    dry_run: bool,
    backfill: bool,
    owner: str,
    repo: str,
    role: str = "pm",
) -> None:
    from synlynk import gh_sync

    conn = _get_db()
    try:
        eligible_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM roadmap_arcs "
                "WHERE is_milestone_eligible = 1 ORDER BY id ASC"
            ).fetchall()
        ]
        if dry_run:
            print(
                f"  [dry-run] would sync {len(eligible_ids)} "
                "milestone-eligible roadmap_arcs rows"
            )
            if backfill:
                story_count = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
                decision_count = conn.execute(
                    "SELECT COUNT(*) FROM decisions"
                ).fetchone()[0]
                print(
                    f"  [dry-run] would backfill {story_count} stories, "
                    f"{decision_count} decisions"
                )
            return

        for arc_id in eligible_ids:
            gh_sync.sync_arc(
                conn, arc_id=arc_id, owner=owner, repo=repo, role=role
            )

        if backfill:
            from synlynk.gh_sync_backfill import run_backfill

            run_backfill(conn, owner=owner, repo=repo, role=role)
    finally:
        conn.close()
    print("  ✓ sync-roadmap complete")
