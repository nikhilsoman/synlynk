"""resolve_arc_uid/resolve_phase_uid + merge_arcs/split_arc/move_phase (gh:#5443 item 3)."""

import sqlite3

import pytest


def _conn_with_goals(tmp_path):
    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id TEXT UNIQUE,
            outcome TEXT, criterion TEXT, status TEXT,
            arc_version TEXT, phase_title TEXT, placement_status TEXT,
            arc_uid TEXT, phase_uid TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE roadmap_uid_aliases (
            old_uid TEXT PRIMARY KEY,
            new_uid TEXT NOT NULL,
            uid_kind TEXT NOT NULL CHECK (uid_kind IN ('arc', 'phase')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE github_sync_map (
            entity_type TEXT, entity_id TEXT, github_number INTEGER,
            PRIMARY KEY (entity_type, entity_id)
        )"""
    )
    return conn


def test_resolve_arc_uid_returns_input_unchanged_when_no_alias(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    assert resolve_arc_uid(conn, "arc-abc") == "arc-abc"
    conn.close()


def test_resolve_arc_uid_follows_a_chain_of_aliases(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-old', 'arc-mid', 'arc', 'merge')"
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-mid', 'arc-new', 'arc', 'merge')"
    )
    conn.commit()
    assert resolve_arc_uid(conn, "arc-old") == "arc-new"
    conn.close()


def test_resolve_arc_uid_raises_on_cycle(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-a', 'arc-b', 'arc', 'test')"
    )
    conn.execute(
        "INSERT INTO roadmap_uid_aliases (old_uid, new_uid, uid_kind, reason) "
        "VALUES ('arc-b', 'arc-a', 'arc', 'test')"
    )
    conn.commit()
    with pytest.raises(ValueError, match="cycle"):
        resolve_arc_uid(conn, "arc-a")
    conn.close()


def test_merge_arcs_rewrites_goals_and_records_alias(tmp_path):
    from synlynk.roadmap_identity import merge_arcs

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-into')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g2', 'o2', 'c2', 'active', 'v2.0.0', 'placed', 'arc-merged')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', 'arc-into', 10)"
    )
    conn.commit()

    merge_arcs(conn, into_uid="arc-into", merged_uids=["arc-merged"], reason="consolidate v1/v2")
    conn.commit()

    assert conn.execute(
        "SELECT arc_uid FROM goals WHERE goal_id='g2'"
    ).fetchone()[0] == "arc-into"
    alias = conn.execute(
        "SELECT new_uid, uid_kind, reason FROM roadmap_uid_aliases WHERE old_uid='arc-merged'"
    ).fetchone()
    assert alias == ("arc-into", "arc", "consolidate v1/v2")
    conn.close()


def test_merge_arcs_rejects_an_unbound_into_uid(tmp_path):
    from synlynk.roadmap_identity import merge_arcs

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-unbound')"
    )
    conn.commit()

    with pytest.raises(ValueError, match="not bound"):
        merge_arcs(conn, into_uid="arc-unbound", merged_uids=["arc-other"], reason="merge test")
    conn.close()


def test_split_arc_requires_bound_uid_and_raises_otherwise(tmp_path):
    from synlynk.roadmap_identity import split_arc

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-unbound')"
    )
    conn.commit()

    with pytest.raises(ValueError, match="not bound"):
        split_arc(conn, from_uid="arc-unbound", goal_ids_to_move=["g1"], reason="split test")
    conn.close()


def test_split_arc_rejects_an_empty_goal_list(tmp_path):
    from synlynk.roadmap_identity import split_arc

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-split')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', 'arc-split', 10)"
    )
    conn.commit()

    with pytest.raises(ValueError, match="must not be empty"):
        split_arc(conn, from_uid="arc-split", goal_ids_to_move=[], reason="empty test")
    conn.close()


def test_split_arc_moves_selected_goals_to_a_new_uid(tmp_path):
    from synlynk.roadmap_identity import resolve_arc_uid, split_arc

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed', 'arc-split')"
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status, arc_uid) "
        "VALUES ('g2', 'o2', 'c2', 'active', 'v1.0.0', 'placed', 'arc-split')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_arc', 'arc-split', 10)"
    )
    conn.commit()

    new_uid = split_arc(conn, from_uid="arc-split", goal_ids_to_move=["g2"], reason="split test")
    conn.commit()

    assert conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g1'").fetchone()[0] == "arc-split"
    assert conn.execute("SELECT arc_uid FROM goals WHERE goal_id='g2'").fetchone()[0] == new_uid
    assert new_uid != "arc-split"
    assert resolve_arc_uid(conn, new_uid) == new_uid
    conn.close()


def test_move_phase_rejects_an_unbound_phase_uid(tmp_path):
    from synlynk.roadmap_identity import move_phase

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status, arc_uid, phase_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'Phase A', 'placed', 'arc-a', 'phase-unbound')"
    )
    conn.commit()

    with pytest.raises(ValueError, match="not bound"):
        move_phase(conn, phase_uid="phase-unbound", new_arc_version="v2.0.0", reason="move test")
    conn.close()


def test_move_phase_rewrites_arc_version_for_all_goals_in_the_phase(tmp_path):
    from synlynk.roadmap_identity import move_phase

    conn = _conn_with_goals(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, phase_title, placement_status, arc_uid, phase_uid) "
        "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'Phase A', 'placed', 'arc-a', 'phase-bound')"
    )
    conn.execute(
        "INSERT INTO github_sync_map (entity_type, entity_id, github_number) "
        "VALUES ('roadmap_phase', 'phase-bound', 20)"
    )
    conn.commit()

    move_phase(conn, phase_uid="phase-bound", new_arc_version="v2.0.0", reason="move test")
    conn.commit()

    row = conn.execute(
        "SELECT arc_version, phase_uid FROM goals WHERE goal_id='g1'"
    ).fetchone()
    assert row == ("v2.0.0", "phase-bound")
    conn.close()
