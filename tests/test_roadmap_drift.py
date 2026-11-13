from __future__ import annotations


def _fresh_db(tmp_path, monkeypatch):
    import synlynk

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    return synlynk._get_db()


def test_finds_decision_linked_to_unplaced_goal(tmp_path, monkeypatch):
    from synlynk.roadmap_drift import find_roadmap_drift

    conn = _fresh_db(tmp_path, monkeypatch)
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-unplaced-1', 'ship X', 'X ships', 'unplaced')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-test-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-unplaced-1')"
        )
        conn.commit()

        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "DECISION_GOAL_UNPLACED"]
    assert len(matches) == 1
    assert matches[0]["decision_id"] == "dec-test-1"
    assert matches[0]["goal_id"] == "goal-unplaced-1"
    assert "goal-unplaced-1" in matches[0]["detail"]
    assert "unplaced" in matches[0]["detail"]


def test_finds_arc_with_no_backing_decision(tmp_path, monkeypatch):
    from synlynk.roadmap_drift import find_roadmap_drift

    conn = _fresh_db(tmp_path, monkeypatch)
    try:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, placement_status) "
            "VALUES ('goal-no-dec-1', 'ship Y', 'Y ships', 'placed')"
        )
        conn.execute(
            "INSERT INTO roadmap_arcs (version, goal_id) "
            "VALUES ('v9.9.0', 'goal-no-dec-1')"
        )
        conn.commit()

        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "ARC_NO_DECISION"]
    assert len(matches) == 1
    assert matches[0]["arc_version"] == "v9.9.0"
    assert matches[0]["goal_id"] == "goal-no-dec-1"


def test_finds_decision_with_dangling_goal_id(tmp_path, monkeypatch):
    import sqlite3

    import synlynk
    from synlynk.roadmap_drift import find_roadmap_drift

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))

    conn = synlynk._get_db()
    conn.close()

    raw = sqlite3.connect(str(db_path))
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute(
            "INSERT INTO decisions (decision_id, topic, date, panel, status, inputs, synthesis, decision_text, goal_id) "
            "VALUES ('dec-dangling-1', 'topic', '2026-11-13', 'pm', 'approved', 'in', 'syn', 'text', 'goal-does-not-exist')"
        )
        raw.commit()
    finally:
        raw.close()

    conn = synlynk._get_db()
    try:
        findings = find_roadmap_drift(conn)
    finally:
        conn.close()

    matches = [f for f in findings if f["kind"] == "DECISION_GOAL_MISSING"]
    assert len(matches) == 1
    assert matches[0]["decision_id"] == "dec-dangling-1"
    assert matches[0]["goal_id"] == "goal-does-not-exist"


def test_classify_roadmap_drift_pass_when_empty():
    from synlynk.roadmap_drift import classify_roadmap_drift

    status, detail = classify_roadmap_drift([])
    assert status == "pass"
    assert "no roadmap drift" in detail


def test_classify_roadmap_drift_warn_when_findings_present():
    from synlynk.roadmap_drift import classify_roadmap_drift

    status, detail = classify_roadmap_drift(
        [
            {
                "kind": "DECISION_GOAL_UNPLACED",
                "decision_id": "dec-1",
                "goal_id": "goal-1",
                "detail": (
                    "decision dec-1 links goal goal-1, but that goal's "
                    "placement_status is 'unplaced'"
                ),
            }
        ]
    )
    assert status == "warn"
    assert "dec-1" in detail
