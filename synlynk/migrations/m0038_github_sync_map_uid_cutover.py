"""Migration 38: cut github_sync_map over from positional id to arc_uid/phase_uid.

Must run after migration 37 (goals.arc_uid/phase_uid backfill) and lands in
the same PR as the synlynk/gh_sync.py call-site switch to arc_uid -- see
docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md
and docs/rca/2026-11-21-LIVE-34-stale-github-sync-map-milestone-corruption-risk.md.

The two rows the LIVE-34 RCA already confirmed are drifted are deleted
outright rather than reconciled, since the RCA explicitly does not yet know
*why* they drifted (root-caused further under gh:#5443 items 1/2/4, out of
this migration's scope). Deleting them makes the next real sync_arc() call
recreate them correctly, keyed by arc_uid.
"""
import sqlite3

from synlynk.migrations import Migration

_LIVE34_CONFIRMED_BAD_ENTITY_IDS = ("2", "10")


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        "DELETE FROM github_sync_map WHERE entity_type = 'roadmap_arc' AND entity_id IN (?, ?)",
        _LIVE34_CONFIRMED_BAD_ENTITY_IDS,
    )

    rows = conn.execute(
        "SELECT entity_id, github_number FROM github_sync_map WHERE entity_type = 'roadmap_arc'"
    ).fetchall()
    for entity_id, github_number in rows:
        if not entity_id.isdigit():
            continue  # already migrated to a uid in a prior run
        # Positional entity_id is 1-based over distinct arc_version
        # (placed goals only), the same population and order as the derived
        # arc view. goals.id is not that index, so a multi-goal arc must not
        # shift later rows.
        arc_uid = conn.execute(
            "SELECT arc_uid FROM ("
            "SELECT CASE WHEN COUNT(DISTINCT arc_uid) = 1 THEN MIN(arc_uid) ELSE NULL END AS arc_uid "
            "FROM goals "
            "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
            "GROUP BY arc_version "
            "ORDER BY arc_version "
            "LIMIT 1 OFFSET ?"
            ")",
            (int(entity_id) - 1,),
        ).fetchone()
        if arc_uid is None or arc_uid[0] is None:
            continue
        conn.execute(
            "UPDATE github_sync_map SET entity_id = ? "
            "WHERE entity_type = 'roadmap_arc' AND github_number = ?",
            (arc_uid[0], github_number),
        )


MIGRATION = Migration(
    version=38,
    name="github_sync_map_uid_cutover",
    up=_up,
)
