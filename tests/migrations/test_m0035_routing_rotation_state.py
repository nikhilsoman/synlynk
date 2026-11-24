import sqlite3

from synlynk.migrations.m0035_routing_rotation_state import MIGRATION
from synlynk.migrations.m0039_exploration_spend_cap import MIGRATION as M0039


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


def test_m0039_adds_cached_exploration_spend_column_idempotently():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE routing_rotation_state ("
        "task_type TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, "
        "updated_at TEXT)"
    )

    M0039.up(conn)
    M0039.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(routing_rotation_state)")}
    assert "exploration_spend_usd" in columns
