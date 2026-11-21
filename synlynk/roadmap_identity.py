"""Shared resolver + explicit regroup operations for arc_uid/phase_uid.

docs/superpowers/specs/2026-11-21-stable-roadmap-arc-phase-identity-design.md

An uid is "bound" once something outside goals/roadmap_uid_aliases
references it (today: github_sync_map; in future, any other consumer
should check the same way). Bound uids may not be silently reassigned by
rename/reorder -- they must go through merge_arcs/split_arc/move_phase,
which record the retirement in roadmap_uid_aliases so resolve_arc_uid/
resolve_phase_uid can still find the current uid for an old reference.
"""
from __future__ import annotations

import sqlite3
import uuid


def _is_bound(conn: sqlite3.Connection, uid: str, uid_kind: str) -> bool:
    entity_type = "roadmap_arc" if uid_kind == "arc" else "roadmap_phase"
    row = conn.execute(
        "SELECT 1 FROM github_sync_map "
        "WHERE entity_type = ? AND entity_id = ? LIMIT 1",
        (entity_type, uid),
    ).fetchone()
    return row is not None


def _resolve(conn: sqlite3.Connection, uid: str, uid_kind: str) -> str:
    seen = {uid}
    current = uid
    while True:
        row = conn.execute(
            "SELECT new_uid FROM roadmap_uid_aliases "
            "WHERE old_uid = ? AND uid_kind = ?",
            (current, uid_kind),
        ).fetchone()
        if row is None:
            return current
        new_uid = row[0]
        if new_uid == current:
            return current
        if new_uid in seen:
            raise ValueError(f"alias cycle detected starting from {uid!r}")
        seen.add(new_uid)
        current = new_uid


def resolve_arc_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Follow aliases to the current arc_uid for a possibly stale uid.

    Returns uid unchanged if it has no alias (the common case).
    """
    return _resolve(conn, uid, "arc")


def resolve_phase_uid(conn: sqlite3.Connection, uid: str) -> str:
    """Same as resolve_arc_uid, for phase_uid / uid_kind='phase'."""
    return _resolve(conn, uid, "phase")


def merge_arcs(
    conn: sqlite3.Connection, into_uid: str, merged_uids: list[str], reason: str
) -> None:
    """Merge one or more arc_uids into into_uid.

    Moves every goal currently carrying a merged uid onto into_uid, and
    records each merged uid -> into_uid in roadmap_uid_aliases so a stale
    reference (e.g. an un-migrated github_sync_map row) still resolves.
    Raises ValueError if into_uid is not itself bound to a consumer --
    an unbound group can simply be re-pointed by editing arc_version
    directly, no explicit operation needed.
    """
    if not _is_bound(conn, into_uid, "arc"):
        raise ValueError(
            f"arc_uid {into_uid!r} is not bound to a consumer; "
            "merge_arcs is only needed for bound uids"
        )
    for old_uid in merged_uids:
        conn.execute(
            "UPDATE goals SET arc_uid = ? WHERE arc_uid = ?", (into_uid, old_uid)
        )
        conn.execute(
            "INSERT OR REPLACE INTO roadmap_uid_aliases "
            "(old_uid, new_uid, uid_kind, reason) VALUES (?, ?, 'arc', ?)",
            (old_uid, into_uid, reason),
        )


def split_arc(
    conn: sqlite3.Connection, from_uid: str, goal_ids_to_move: list[str], reason: str
) -> str:
    """Move the given goal_ids off from_uid onto a freshly minted arc_uid.

    Returns the new uid. Raises ValueError if from_uid is not bound -- an
    unbound group can simply have its goals' arc_version edited directly.
    """
    if not _is_bound(conn, from_uid, "arc"):
        raise ValueError(
            f"arc_uid {from_uid!r} is not bound to a consumer; "
            "split_arc is only needed for bound uids"
        )
    if not goal_ids_to_move:
        raise ValueError("goal_ids_to_move must not be empty")
    new_uid = f"arc-{uuid.uuid4().hex[:12]}"
    conn.execute(
        f"UPDATE goals SET arc_uid = ? WHERE goal_id IN "
        f"({','.join('?' for _ in goal_ids_to_move)})",
        (new_uid, *goal_ids_to_move),
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases "
        "(old_uid, new_uid, uid_kind, reason) "
        "VALUES (?, ?, 'arc', ?) ON CONFLICT(old_uid) DO NOTHING",
        (new_uid, new_uid, f"split from {from_uid}: {reason}"),
    )
    return new_uid


def move_phase(
    conn: sqlite3.Connection, phase_uid: str, new_arc_version: str, reason: str
) -> None:
    """Move all goals in phase_uid to new_arc_version, retaining phase_uid.

    Raises ValueError if phase_uid is not bound -- an unbound phase can
    simply have its goals' arc_version edited directly.
    """
    if not _is_bound(conn, phase_uid, "phase"):
        raise ValueError(
            f"phase_uid {phase_uid!r} is not bound to a consumer; "
            "move_phase is only needed for bound uids"
        )
    conn.execute(
        "UPDATE goals SET arc_version = ? WHERE phase_uid = ?",
        (new_arc_version, phase_uid),
    )
