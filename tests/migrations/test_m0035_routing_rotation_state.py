import sqlite3

from synlynk.migrations.m0035_routing_rotation_state import MIGRATION


def test_m0035_creates_table_and_indexes():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE capability_ratings (
            story_id TEXT, agent TEXT, discipline TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE cost_entries (
            agent TEXT, type_id TEXT
        )
    """)
    MIGRATION.up(conn)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "routing_rotation_state" in tables
    indexes = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert "idx_capability_ratings_harness_task" in indexes
    assert "idx_cost_entries_harness_task" in indexes


def test_m0035_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT, discipline TEXT)")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    MIGRATION.up(conn)
    MIGRATION.up(conn)  # must not raise
