import sqlite3

import pytest

from synlynk.db import _migrate_db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "state.db"
    connection = sqlite3.connect(str(db_path))
    _migrate_db(connection)
    return connection


def test_capability_watch_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_watch)")}
    assert cols == {"id", "last_probe_at", "last_green_probe_at", "last_smoke_test_at", "last_green_smoke_at"}


def test_capability_watch_singleton_row_seeded(conn):
    row = conn.execute("SELECT id FROM capability_watch WHERE id = 1").fetchone()
    assert row is not None


def test_gh_write_capability_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)")}
    assert cols == {"harness", "mode", "action", "status", "checked_at"}
    pk_cols = {row[1] for row in conn.execute("PRAGMA table_info(gh_write_capability)") if row[5] > 0}
    assert pk_cols == {"harness", "mode", "action"}


def test_capability_incidents_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_incidents)")}
    assert cols == {
        "id", "harness", "failing_path", "classification", "evidence", "detected_at",
    }
