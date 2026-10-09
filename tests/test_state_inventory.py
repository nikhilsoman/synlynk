import sqlite3

from synlynk.state_inventory import inventory


def test_inventory_is_read_only_and_classifies_repo_artifact(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.commit()
    conn.close()

    before = db.read_bytes()
    rows = inventory(repo)

    assert len(rows) == 1
    assert rows[0]["class"] == "repo-local"
    assert rows[0]["integrity"] == "ok"
    assert rows[0]["sha256"]
    assert db.read_bytes() == before


def test_inventory_reports_row_count_and_staleness(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE stories (id INTEGER PRIMARY KEY, story_id TEXT, title TEXT, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-1', 'Example story')")
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('s-2', 'Another story')")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert len(rows) == 1
    assert rows[0]["row_count"] == 2
    assert "mtime_iso" in rows[0]
    assert rows[0]["staleness_days"] >= 0


def test_inventory_row_count_zero_when_no_stories_table(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".synlynk"
    db_dir.mkdir(parents=True)
    db = db_dir / "state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sample (value TEXT)")
    conn.commit()
    conn.close()

    rows = inventory(repo)

    assert rows[0]["row_count"] is None
