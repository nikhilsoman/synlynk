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


def test_doctor_uid_consistency_does_not_close_shared_connection(tmp_path, monkeypatch):
    """_hc_roadmap_uid_consistency must not close the connection from _get_db() --
    doctor's own health-check loop and TC-probe steps share one connection
    across the whole cmd_doctor() run (see tests/test_tc9_gh_write_probe.py).
    """
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    monkeypatch.setattr(synlynk, "_get_db", lambda: conn)

    doctor._hc_roadmap_uid_consistency()

    # The shared connection must still be usable by a later consumer.
    conn.execute("SELECT 1")
