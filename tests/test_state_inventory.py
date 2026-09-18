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
