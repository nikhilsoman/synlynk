"""Tests for inline best-effort roadmap GitHub sync hooks."""


def test_cmd_roadmap_add_triggers_arc_sync(tmp_path, monkeypatch):
    from synlynk import db

    sync_calls = []
    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)
    monkeypatch.setattr(
        db, "_try_sync_arc_by_version", lambda version: sync_calls.append(version)
    )
    monkeypatch.setattr(
        "synlynk.policy.check_authority",
        lambda *a, **kw: type("A", (), {"allowed": True})(),
    )

    import sqlite3

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
        "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db.cmd_roadmap_add(version="v2.0.0", title="Second release")

    assert sync_calls == ["v2.0.0"]


def test_cmd_roadmap_add_does_not_raise_when_sync_fails(tmp_path, monkeypatch):
    from synlynk import db

    def failing_sync(version):
        raise RuntimeError("gh api down")

    monkeypatch.setattr(db, "_generate_roadmap_md", lambda: None)
    monkeypatch.setattr(db, "_try_sync_arc_by_version", failing_sync)
    monkeypatch.setattr(
        "synlynk.policy.check_authority",
        lambda *a, **kw: type("A", (), {"allowed": True})(),
    )

    import sqlite3

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
        "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db"))

    db.cmd_roadmap_add(version="v2.0.0", title="Second release")
