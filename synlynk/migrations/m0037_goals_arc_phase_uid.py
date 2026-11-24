"""Migration 37: durable arc_uid/phase_uid identity on goals (gh:#5443 item 3 / LIVE-34).

Adds write-once, opaque identity columns to goals so that consumers like
github_sync_map stop keying off roadmap_arcs/roadmap_phases' positional,
ROW_NUMBER()-derived `id`, which shifts under rename/reorder/regroup
(docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md).

Backfill only assigns uids to already-placed goals (placement_status='placed'
and arc_version IS NOT NULL) -- the same population the roadmap_arcs/
roadmap_phases views draw from. One uid per distinct arc_version group, and
one phase_uid per distinct (arc_version, phase_title) group where
phase_title IS NOT NULL.

Idempotent: only backfills rows where the uid is still NULL, so re-running
after ongoing assignment triggers exist is a no-op.
"""
import sqlite3
import uuid

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS roadmap_uid_aliases (
            old_uid    TEXT PRIMARY KEY,
            new_uid    TEXT NOT NULL,
            uid_kind   TEXT NOT NULL CHECK (uid_kind IN ('arc', 'phase')),
            reason     TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )

    goals_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if not goals_exists:
        return

    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    for col in ("arc_uid", "phase_uid"):
        if col not in cols:
            conn.execute(f"ALTER TABLE goals ADD COLUMN {col} TEXT")

    arc_versions = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT arc_version FROM goals "
            "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
            "AND arc_uid IS NULL"
        ).fetchall()
    ]
    for arc_version in arc_versions:
        new_uid = f"arc-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "UPDATE goals SET arc_uid = ? "
            "WHERE placement_status = 'placed' AND arc_version = ? AND arc_uid IS NULL",
            (new_uid, arc_version),
        )

    phase_groups = conn.execute(
        "SELECT DISTINCT arc_version, phase_title FROM goals "
        "WHERE placement_status = 'placed' AND arc_version IS NOT NULL "
        "AND phase_title IS NOT NULL AND phase_uid IS NULL"
    ).fetchall()
    for arc_version, phase_title in phase_groups:
        new_uid = f"phase-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "UPDATE goals SET phase_uid = ? "
            "WHERE placement_status = 'placed' AND arc_version = ? AND phase_title = ? "
            "AND phase_uid IS NULL",
            (new_uid, arc_version, phase_title),
        )


MIGRATION = Migration(
    version=37,
    name="goals_arc_phase_uid",
    up=_up,
)
