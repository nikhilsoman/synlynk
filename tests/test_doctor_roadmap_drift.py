"""Merged-PR / roadmap parity diagnostics (#2413)."""

from __future__ import annotations


def test_doctor_warns_and_repairs_merged_pr_phase_drift(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(doctor, "_merged_pr_numbers_from_origin_main", lambda: {2434})
    regenerated = []
    monkeypatch.setattr("synlynk.db._generate_roadmap_md", lambda: regenerated.append(True))

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO roadmap_arcs (version) VALUES ('v1.1.0')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status, notes) VALUES (?, ?, ?, ?)",
            ("v1.1.0", "Merge write-through", "in_progress", "Delivered in #2434"),
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_merge_parity()
    assert result.status == "warn"
    assert "#2434" in result.message

    assert doctor.repair_roadmap_merge_parity() == 1
    conn = synlynk._get_db()
    try:
        assert conn.execute("SELECT status FROM roadmap_phases").fetchone()[0] == "done"
    finally:
        conn.close()
    assert regenerated == [True]


def test_doctor_warns_on_roadmap_decision_drift(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-drift-1', 'ship Z', 'Z ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-drift-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-drift-1')"
        )
        conn.commit()
    finally:
        conn.close()

    result = doctor._hc_roadmap_decision_drift()
    assert result.status == "warn"
    assert "dec-drift-1" in result.message
    assert "goal-drift-1" in result.message


def test_doctor_passes_when_no_roadmap_decision_drift(tmp_path, monkeypatch):
    import synlynk
    import synlynk.doctor as doctor

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    conn.close()

    result = doctor._hc_roadmap_decision_drift()
    assert result.status == "ok"
