"""_hc_roadmap_uid_consistency: warn when an arc/phase group has >1 uid (gh:#5443 item 3)."""


def test_doctor_warns_on_arc_uid_divergence(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v3.0.0', 'arc-one', 'placed')"
        )
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, arc_uid, placement_status) "
            "VALUES ('g2', 'o2', 'c2', 'active', 'v3.0.0', 'arc-two', 'placed')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_uid_consistency()
    assert result.status == "warn"
    assert "v3.0.0" in result.message


def test_doctor_passes_when_every_group_has_exactly_one_uid(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, status, arc_version, placement_status) "
            "VALUES ('g1', 'o1', 'c1', 'active', 'v3.0.0', 'placed')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_uid_consistency()
    assert result.status == "ok"
