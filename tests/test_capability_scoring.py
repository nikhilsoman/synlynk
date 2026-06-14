import os
import sqlite3
import tempfile
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))

def test_get_db_creates_state_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    conn.close()
    assert os.path.exists(".synlynk/state/state.db")

def test_migrate_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "stories" in tables
    assert "capability_ratings" in tables

def test_migrate_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    _get_db().close()
    _get_db().close()  # second call must not crash
