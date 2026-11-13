from __future__ import annotations


def test_roadmap_gate_not_triggered_when_no_decisions_changed(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.pr_check import check_pr_roadmap_gate

    conn = synlynk._get_db()
    try:
        result = check_pr_roadmap_gate(
            conn,
            changed_files=["synlynk/db.py", "README.md"],
        )
    finally:
        conn.close()

    assert result["passed"] is True
    assert result["triggered"] is False
    assert "decision records" in result["message"].lower()


def test_roadmap_gate_triggered_and_fails_on_drift(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.pr_check import check_pr_roadmap_gate

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-gate-1', 'ship W', 'W ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-gate-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-gate-1')"
        )
        conn.commit()

        result = check_pr_roadmap_gate(
            conn,
            changed_files=["project-docs/decisions/dec-gate-1.md"],
        )
    finally:
        conn.close()

    assert result["triggered"] is True
    assert result["passed"] is False
    assert "dec-gate-1" in result["message"]
    assert len(result["findings"]) == 1
