def test_release_checklist_marks_roadmap_arc_shipped(tmp_path, monkeypatch):
    import synlynk as synlynk_init

    sync_calls = []
    monkeypatch.setattr(
        synlynk_init,
        "_try_sync_arc_by_version",
        lambda version: sync_calls.append(version),
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


def test_release_dry_run_does_not_mark_roadmap_arc_shipped(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    import synlynk as synlynk_init
    import synlynk.release_marketing as release_marketing
    import synlynk.release_readme as release_readme

    mark_calls = []
    sync_calls = []
    monkeypatch.setattr(
        synlynk_init, "_mark_roadmap_arc_shipped", lambda version: mark_calls.append(version)
    )
    monkeypatch.setattr(
        synlynk_init, "_try_sync_arc_by_version", lambda version: sync_calls.append(version)
    )
    monkeypatch.setattr(release_readme, "validate_readme_for_release", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        release_marketing,
        "execute_release_ceremony",
        lambda **kwargs: SimpleNamespace(
            ok=True, errors=[], website_updated=False, docs_updated=[]
        ),
    )
    monkeypatch.setattr(synlynk_init.subprocess, "check_output", lambda *args, **kwargs: b"")
    (tmp_path / "VERSION").write_text("1.0.0\n")
    monkeypatch.chdir(tmp_path)

    synlynk_init.cmd_release(dry_run=True, role="pm")

    assert mark_calls == []
    assert sync_calls == []
    assert "[ ] Roadmap row would be marked shipped and Milestone closed — 1.0.1" in capsys.readouterr().out
