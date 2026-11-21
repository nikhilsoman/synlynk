"""arc_uid/phase_uid assignment + divergence guard (gh:#5443 item 3)."""


def test_new_goal_in_existing_arc_gets_the_arc_existing_uid(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        first_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g1'"
        ).fetchone()[0]
        assert first_uid is not None

        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        second_uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g2'"
        ).fetchone()[0]
        assert second_uid == first_uid
    finally:
        conn.close()


def test_rename_keeps_the_same_arc_uid(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v1.0.0', 'placed')"
        )
        conn.commit()
        uid = conn.execute(
            "SELECT arc_uid FROM goals WHERE goal_id='g1'"
        ).fetchone()[0]
        assert uid is not None

        conn.execute("UPDATE goals SET arc_version='v1.1.0' WHERE arc_version='v1.0.0'")
        conn.commit()
        renamed = conn.execute(
            "SELECT arc_version, arc_uid FROM goals WHERE goal_id='g1'"
        ).fetchone()
        assert renamed == ("v1.1.0", uid)
    finally:
        conn.close()


def test_roadmap_arcs_view_surfaces_null_uid_on_divergence(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v2.0.0', 'arc-aaa', 'placed')"
        )
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v2.0.0', 'arc-bbb', 'placed')"
        )
        conn.commit()
        uid = conn.execute(
            "SELECT arc_uid FROM roadmap_arcs WHERE version='v2.0.0'"
        ).fetchone()[0]
        assert uid is None
    finally:
        conn.close()


def test_roadmap_phases_view_surfaces_null_uid_on_divergence(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals "
            "(goal_id, outcome, criterion, status, arc_version, phase_title, phase_uid, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v2.0.0', 'Phase 1', 'phase-aaa', 'placed')"
        )
        conn.execute(
            "INSERT INTO goals "
            "(goal_id, outcome, criterion, status, arc_version, phase_title, phase_uid, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v2.0.0', 'Phase 1', 'phase-bbb', 'placed')"
        )
        conn.commit()
        uid = conn.execute(
            "SELECT phase_uid FROM roadmap_phases "
            "WHERE arc_version='v2.0.0' AND phase_title='Phase 1'"
        ).fetchone()[0]
        assert uid is None
    finally:
        conn.close()
