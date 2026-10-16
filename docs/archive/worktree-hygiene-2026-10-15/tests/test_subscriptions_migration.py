import sqlite3

from unittest.mock import MagicMock, patch


def test_migration_0022_renames_legacy_subscriptions_column_and_preserves_data(tmp_path):
    from synlynk.migrations.m0022_subscriptions_harness_name import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.execute(
        """CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            last_seen_event_id INTEGER NOT NULL DEFAULT 0,
            UNIQUE(agent_name, event_type)
        )"""
    )
    conn.execute(
        "INSERT INTO subscriptions (agent_name, event_type, last_seen_event_id) VALUES (?, ?, ?)",
        ("workspace-lifecycle-nudge", "cron_heartbeat", 42),
    )

    MIGRATION.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)")}
    assert "harness_name" in columns
    assert "agent_name" not in columns
    assert conn.execute(
        "SELECT harness_name, event_type, last_seen_event_id FROM subscriptions"
    ).fetchone() == ("workspace-lifecycle-nudge", "cron_heartbeat", 42)

    # Re-running the repair is safe for retries and startup races.
    MIGRATION.up(conn)
    assert conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 1


def test_version_21_database_is_repaired_before_scan_local_events(tmp_path, monkeypatch):
    import synlynk
    from synlynk.db import _migrate_db

    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "state.db"))
    conn = synlynk._get_db()
    conn.execute("ALTER TABLE subscriptions RENAME COLUMN harness_name TO agent_name")
    conn.execute("PRAGMA user_version = 21")
    conn.commit()

    _migrate_db(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)")}
    assert "harness_name" in columns
    assert "agent_name" not in columns
    conn.close()

    from synlynk.events import scan_local_events

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="[]")):
        scan_local_events("some-harness-name")
