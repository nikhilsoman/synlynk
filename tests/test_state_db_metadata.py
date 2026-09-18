import sqlite3

import pytest

import synlynk


def test_explicit_db_gets_ephemeral_metadata(tmp_path):
    path = tmp_path / "test.db"
    conn = synlynk.open_state_db(str(path), mode="ephemeral-test")
    assert dict(conn.execute("SELECT key, value FROM state_metadata")) == {
        "product_id": "ephemeral-test",
        "mode": "ephemeral-test",
        "schema": "1",
    }
    conn.close()


def test_mode_mismatch_fails_closed(tmp_path):
    path = tmp_path / "restore.db"
    conn = synlynk.open_state_db(str(path), mode="restore")
    conn.close()
    with pytest.raises(RuntimeError, match="metadata mismatch"):
        synlynk.open_state_db(str(path), mode="backup")


def test_metadata_corruption_is_rejected(tmp_path):
    path = tmp_path / "test.db"
    conn = synlynk.open_state_db(str(path), mode="ephemeral-test")
    conn.execute("UPDATE state_metadata SET value = 'other' WHERE key = 'mode'")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="metadata mismatch"):
        synlynk.open_state_db(str(path), mode="ephemeral-test")


def test_noncanonical_mode_requires_explicit_path():
    with pytest.raises(ValueError, match="requires an explicit database path"):
        synlynk.open_state_db(mode="restore")
