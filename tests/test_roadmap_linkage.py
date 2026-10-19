"""Roadmap phase completion follows a linked story's terminal state (#2413)."""

from __future__ import annotations


def test_story_done_completes_linked_roadmap_phase_and_regenerates(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    regenerated = []
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: regenerated.append(True))
    monkeypatch.setattr("synlynk.events.emit_event", lambda *_a, **_kw: None)

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO stories (story_id, title) VALUES ('story-linked', 'Linked work')")
        conn.execute("INSERT INTO roadmap_arcs (version, status) VALUES ('v1.1.0', 'in_progress')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status, story_id) VALUES (?, ?, ?, ?)",
            ("v1.1.0", "Linked phase", "in_progress", "story-linked"),
        )
        conn.commit()
    finally:
        conn.close()

    db.cmd_story_done("story-linked")

    conn = synlynk._get_db()
    try:
        assert conn.execute("SELECT status FROM stories WHERE story_id='story-linked'").fetchone()[0] == "done"
        assert conn.execute("SELECT status FROM roadmap_phases WHERE story_id='story-linked'").fetchone()[0] == "done"
    finally:
        conn.close()
    assert regenerated == [True]


def test_story_ready_starts_a_planned_linked_roadmap_phase(tmp_path, monkeypatch):
    import synlynk
    import synlynk.db as db

    db_path = tmp_path / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(db_path))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)

    conn = synlynk._get_db()
    try:
        conn.execute("INSERT INTO stories (story_id, title) VALUES ('story-ready', 'Ready work')")
        conn.execute("INSERT INTO roadmap_arcs (version) VALUES ('v1.1.0')")
        conn.execute(
            "INSERT INTO roadmap_phases (arc_version, phase_title, status, story_id) VALUES (?, ?, ?, ?)",
            ("v1.1.0", "Ready phase", "planned", "story-ready"),
        )
        conn.commit()
    finally:
        conn.close()

    db.cmd_story_ready("story-ready")

    conn = synlynk._get_db()
    try:
        assert conn.execute("SELECT status FROM roadmap_phases WHERE story_id='story-ready'").fetchone()[0] == "in_progress"
    finally:
        conn.close()
