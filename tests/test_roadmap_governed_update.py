"""Tests for governed roadmap phase update and reassignment (gh:#2535)."""

from __future__ import annotations

import pytest


def test_cmd_roadmap_update_by_phase_id(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    regenerated = []
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: regenerated.append(True))
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status, priority, notes) "
            "VALUES ('v0.25.6', 'Phase 1', 'planned', 'P1', 'initial notes')"
        )
        conn.commit()
        phase_id = conn.execute("SELECT id FROM roadmap_phases WHERE phase_title='Phase 1'").fetchone()[0]
    finally:
        conn.close()

    db.cmd_roadmap_update(
        phase_id=phase_id,
        status="in_progress",
        priority="P0",
        notes="updated notes",
    )

    conn = synlynk._get_db()
    try:
        row = conn.execute("SELECT status, priority, notes FROM roadmap_phases WHERE id=?", (phase_id,)).fetchone()
        assert row == ("in_progress", "P0", "updated notes")
    finally:
        conn.close()

    assert regenerated == [True]


def test_cmd_roadmap_update_by_arc_and_title(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v0.25.6', 'Old Title', 'planned')"
        )
        conn.commit()
    finally:
        conn.close()

    db.cmd_roadmap_update(
        arc="v0.25.6",
        phase_title="Old Title",
        title="New Title",
        status="done",
    )

    conn = synlynk._get_db()
    try:
        row = conn.execute("SELECT phase_title, status FROM roadmap_phases WHERE arc_version='v0.25.6'").fetchone()
        assert row == ("New Title", "done")
    finally:
        conn.close()


def test_cmd_roadmap_reassign_to_new_arc(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    regenerated = []
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: regenerated.append(True))
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.26.0', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v0.25.6', 'Defer Me', 'planned')"
        )
        conn.commit()
        phase_id = conn.execute("SELECT id FROM roadmap_phases WHERE phase_title='Defer Me'").fetchone()[0]
    finally:
        conn.close()

    db.cmd_roadmap_update(
        phase_id=phase_id,
        target_arc="v0.26.0",
        status="deferred",
        notes="Deferred to next release",
    )

    conn = synlynk._get_db()
    try:
        row = conn.execute("SELECT arc_version, status, notes FROM roadmap_phases WHERE id=?", (phase_id,)).fetchone()
        assert row == ("v0.26.0", "deferred", "Deferred to next release")
    finally:
        conn.close()

    assert regenerated == [True]


def test_cmd_roadmap_reassign_to_nonexistent_arc_fails(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v0.25.6', 'Stay Here', 'planned')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Target arc version 'v9.9.9' does not exist"):
        db.cmd_roadmap_update(
            arc="v0.25.6",
            phase_title="Stay Here",
            target_arc="v9.9.9",
        )


def test_cmd_roadmap_update_policy_rejected(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(
        "synlynk.policy.check_authority",
        lambda *a, **kw: AuthorityResult(allowed=False, reason="role unauthorized"),
    )

    with pytest.raises(RuntimeError, match="Roadmap edit refused"):
        db.cmd_roadmap_update(
            phase_id=1,
            status="done",
            role="guest",
        )


def test_cmd_roadmap_update_invalid_status_fails(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v0.25.6', 'Phase X', 'planned')"
        )
        conn.commit()
        phase_id = conn.execute("SELECT id FROM roadmap_phases WHERE phase_title='Phase X'").fetchone()[0]
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Invalid phase status: 'bogus'"):
        db.cmd_roadmap_update(
            phase_id=phase_id,
            status="bogus",
        )


def test_cmd_roadmap_update_missing_identifier(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db
    from synlynk.policy import AuthorityResult

    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    with pytest.raises(ValueError, match="Must specify either --phase-id or both --arc and --phase-title"):
        db.cmd_roadmap_update(status="done")


def test_cmd_roadmap_cli_dispatch(tmp_path, monkeypatch):
    import synlynk
    import synlynk.cli as cli
    from synlynk.policy import AuthorityResult

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr("synlynk.db._generate_roadmap_md", lambda: None)
    monkeypatch.setattr("synlynk.policy.check_authority", lambda *a, **kw: AuthorityResult(allowed=True, reason="ok"))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.25.6', 'planned')")
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v0.26.0', 'planned')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status) VALUES ('v0.25.6', 'CLI Phase', 'planned')"
        )
        conn.commit()
        phase_id = conn.execute("SELECT id FROM roadmap_phases WHERE phase_title='CLI Phase'").fetchone()[0]
    finally:
        conn.close()

    parser = cli.build_parser()
    args = parser.parse_args([
        "roadmap", "reassign",
        "--phase-id", str(phase_id),
        "--target-arc", "v0.26.0",
        "--status", "deferred",
    ])
    assert args.roadmap_action == "reassign"
    assert args.target_arc == "v0.26.0"
    assert args.status == "deferred"
