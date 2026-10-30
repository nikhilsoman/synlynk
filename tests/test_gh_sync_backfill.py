def test_run_backfill_syncs_every_arc_story_and_decision(tmp_path, monkeypatch):
    import sqlite3

    from synlynk import gh_sync_backfill

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        "CREATE TABLE roadmap_arcs (id INTEGER PRIMARY KEY, version TEXT, title TEXT, "
        "status TEXT, target_date TEXT, notes TEXT, is_milestone_eligible BOOLEAN)"
    )
    conn.execute(
        "CREATE TABLE roadmap_phases (id INTEGER PRIMARY KEY, arc_version TEXT, "
        "phase_title TEXT, status TEXT, priority TEXT, story_id TEXT, notes TEXT)"
    )
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, status TEXT, gh_issue TEXT)"
    )
    conn.execute(
        "CREATE TABLE decisions (decision_id TEXT PRIMARY KEY, topic TEXT, status TEXT, "
        "synthesis TEXT, decision_text TEXT)"
    )
    conn.execute(
        "CREATE TABLE github_sync_map (entity_type TEXT, entity_id TEXT, github_number INTEGER, "
        "github_node_id TEXT, content_hash TEXT, last_synced_at TEXT, "
        "PRIMARY KEY (entity_type, entity_id))"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(1, 'v1.0.0', 'First', 'shipped', NULL, NULL, 1)"
    )
    conn.execute(
        "INSERT INTO roadmap_arcs VALUES "
        "(2, 'Future Expansions', NULL, 'planned', NULL, NULL, 0)"
    )
    conn.execute("INSERT INTO stories VALUES ('story-a', 'A', 'done', NULL)")
    conn.execute("INSERT INTO stories VALUES ('story-b', 'B', 'open', '42')")
    conn.execute(
        "INSERT INTO decisions VALUES ('dec-1', 'Topic', 'decided', 'syn', 'text')"
    )
    conn.commit()

    arc_calls, story_calls, decision_calls = [], [], []
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_arc",
        lambda conn, arc_id, **kw: arc_calls.append(arc_id),
    )
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_story",
        lambda conn, story_id, **kw: story_calls.append(story_id),
    )
    monkeypatch.setattr(
        gh_sync_backfill.gh_sync,
        "sync_decision",
        lambda conn, decision_id, **kw: decision_calls.append(decision_id),
    )

    gh_sync_backfill.run_backfill(conn, owner="o", repo="r")

    assert arc_calls == [1]
    assert sorted(story_calls) == ["story-a", "story-b"]
    assert decision_calls == ["dec-1"]
    conn.close()
