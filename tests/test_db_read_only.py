import sqlite3

import pytest


def test_read_only_db_connection_cannot_write_or_migrate(tmp_path, monkeypatch):
    from synlynk import _get_db

    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE marker (value TEXT)")
    conn.commit()
    conn.close()
    before = path.read_bytes()

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(path))
    read_conn = _get_db(read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        read_conn.execute("CREATE TABLE should_not_exist (value TEXT)")
    read_conn.close()

    assert path.read_bytes() == before


def test_read_only_db_connection_fails_closed_on_corruption(tmp_path, monkeypatch):
    from synlynk import _get_db

    path = tmp_path / "state.db"
    path.write_bytes(b"not a sqlite database")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(path))

    with pytest.raises(sqlite3.DatabaseError):
        _get_db(read_only=True)
