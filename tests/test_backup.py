import json
import sqlite3

from synlynk.backup import create_snapshot, verify_snapshot


def test_create_snapshot_uses_online_backup_and_writes_manifest(tmp_path):
    source = tmp_path / "state.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("INSERT INTO events (body) VALUES ('kept')")
    conn.commit()
    conn.close()

    result = create_snapshot(source=source, output_dir=tmp_path / "backups")
    snapshot_path = tmp_path / "backups" / result["snapshot"].split("/")[-1]
    manifest_path = snapshot_path.with_suffix(".json")

    assert snapshot_path.exists()
    assert manifest_path.exists()
    assert not list((tmp_path / "backups").glob(".*.tmp-wal"))
    assert not list((tmp_path / "backups").glob(".*.tmp-shm"))
    assert result["integrity_check"] == "ok"
    assert result["row_counts"]["events"] == 1
    assert json.loads(manifest_path.read_text())["sha256"] == result["sha256"]
    assert verify_snapshot(snapshot_path)["integrity_check"] == "ok"


def test_verify_snapshot_rejects_corruption(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"not sqlite")

    try:
        verify_snapshot(path)
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("corrupt snapshot unexpectedly verified")
