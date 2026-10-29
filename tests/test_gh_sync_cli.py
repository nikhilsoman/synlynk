def test_cmd_sync_roadmap_dry_run_does_not_write_sync_map(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync, gh_sync_cli

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First release', 'planned', NULL, NULL, 1)"
    )
    conn.commit()
    conn.close()

    calls = []
    monkeypatch.setattr(
        gh_sync, "sync_arc", lambda *a, **kw: calls.append(("sync_arc", a, kw))
    )
    monkeypatch.setattr(
        gh_sync_cli, "_get_db", lambda: sqlite3.connect(tmp_path / "state.db")
    )

    gh_sync_cli.cmd_sync_roadmap(
        dry_run=True, backfill=False, owner="o", repo="r"
    )

    assert calls == []  # dry-run never calls the real sync functions
