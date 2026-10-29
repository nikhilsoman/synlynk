"""Migration 29: roadmap arc milestone eligibility and normalization.

Flag non-version identifiers and pre-granularity range strings so the
GitHub Milestone sync never tries to create a milestone for them. Collapse
the ``1.0.0`` duplicate into ``v1.0.0`` after repointing its references.
"""

import sqlite3

from synlynk.migrations import Migration


_NOT_MILESTONE_ELIGIBLE = {
    "Future Expansions",
    "epic-job-truth-2026-08",
    "v0.1–v0.3.0",
}
_DUPLICATE_VERSION = "1.0.0"
_CANONICAL_VERSION = "v1.0.0"


def _up(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    if "is_milestone_eligible" not in cols:
        conn.execute(
            "ALTER TABLE roadmap_arcs ADD COLUMN is_milestone_eligible "
            "BOOLEAN NOT NULL DEFAULT 1"
        )

    placeholders = ",".join("?" for _ in _NOT_MILESTONE_ELIGIBLE)
    conn.execute(
        f"UPDATE roadmap_arcs SET is_milestone_eligible = 0 "
        f"WHERE version IN ({placeholders})",
        tuple(_NOT_MILESTONE_ELIGIBLE),
    )

    duplicate = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version = ?", (_DUPLICATE_VERSION,)
    ).fetchone()
    canonical = conn.execute(
        "SELECT id FROM roadmap_arcs WHERE version = ?", (_CANONICAL_VERSION,)
    ).fetchone()
    if duplicate and canonical:
        duplicate_id = duplicate[0]
        conn.execute(
            "UPDATE roadmap_phases SET arc_version = ? WHERE arc_version = ?",
            (_CANONICAL_VERSION, _DUPLICATE_VERSION),
        )
        conn.execute(
            "UPDATE cost_entries SET epic_id = ? WHERE epic_id = ?",
            (canonical[0], duplicate_id),
        )
        conn.execute("DELETE FROM roadmap_arcs WHERE id = ?", (duplicate_id,))


MIGRATION = Migration(
    version=29,
    name="roadmap_arcs_milestone_eligibility",
    up=_up,
)
