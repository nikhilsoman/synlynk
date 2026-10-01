import sqlite3

from synlynk.db import _migrate_onboarding_sessions
from synlynk.db_schema import ONBOARDING_SESSIONS_SCHEMA


def test_onboarding_sessions_schema_creation(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(ONBOARDING_SESSIONS_SCHEMA)
    conn.commit()

    cursor = conn.execute("PRAGMA table_info(onboarding_sessions)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert "session_id" in columns
    assert "product_id" in columns
    assert "current_stage" in columns
    assert "topology_status" in columns
    assert "topology_candidate" in columns
    assert "topology_confirmed" in columns
    assert "harness_probes" in columns
    assert "dependency_checks" in columns
    assert "first_win_meta" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    conn.close()


def test_migrate_onboarding_sessions_idempotent(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_onboarding_sessions(conn)
    _migrate_onboarding_sessions(conn)

    cursor = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name='onboarding_sessions'"
    )
    assert cursor.fetchone() is not None
    conn.close()
