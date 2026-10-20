import sqlite3
from pathlib import Path

from synlynk.db import _snapshot_before_migration


def test_migration_snapshot_includes_uncheckpointed_wal_pages(tmp_path):
    source = tmp_path / "state.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE facts (value TEXT)")
    conn.executemany("INSERT INTO facts VALUES (?)", ((f"value-{i}",) for i in range(2000)))
    conn.commit()

    snapshot = _snapshot_before_migration(conn)
    assert snapshot is not None
    snapshot_path = tmp_path / Path(snapshot).name
    assert snapshot_path.exists()
    assert not (tmp_path / f"{snapshot_path.name}.tmp").exists()

    with sqlite3.connect(snapshot_path) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert backup.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 2000
    conn.close()
