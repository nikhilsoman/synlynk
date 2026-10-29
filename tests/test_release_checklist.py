def test_release_checklist_marks_roadmap_arc_shipped(tmp_path, monkeypatch):
    import synlynk as synlynk_init

    sync_calls = []
    monkeypatch.setattr(
        synlynk_init,
        "_try_sync_arc_by_version",
        lambda version: sync_calls.append(version),
        raising=False,
    )

    import sqlite3

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES (1, 'v1.0.0', 'First', 'planned', NULL, NULL)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(synlynk_init, "_get_db", lambda: sqlite3.connect(db_path))

    synlynk_init._mark_roadmap_arc_shipped("v1.0.0")

    conn = sqlite3.connect(db_path)
    status = conn.execute(
        "SELECT status FROM roadmap_arcs WHERE version='v1.0.0'"
    ).fetchone()[0]
    conn.close()
    assert status == "shipped"
    assert sync_calls == ["v1.0.0"]
