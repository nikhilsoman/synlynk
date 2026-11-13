from __future__ import annotations


def test_cmd_roadmap_check_reports_no_drift(tmp_path, monkeypatch, capsys):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    from synlynk.db import cmd_roadmap_check

    exit_code = cmd_roadmap_check()
    assert exit_code == 0
    assert "no roadmap drift" in capsys.readouterr().out.lower()


def test_cmd_roadmap_check_reports_drift_and_returns_nonzero(
    tmp_path, monkeypatch, capsys
):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-cli-1', 'ship V', 'V ships', 'unresolved')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-cli-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-cli-1')"
        )
        conn.commit()
    finally:
        conn.close()

    from synlynk.db import cmd_roadmap_check

    exit_code = cmd_roadmap_check()
    assert exit_code == 1
    assert "dec-cli-1" in capsys.readouterr().out
