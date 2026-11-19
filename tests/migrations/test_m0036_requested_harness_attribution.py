import sqlite3

from synlynk.migrations.m0036_requested_harness_attribution import MIGRATION


def test_m0036_adds_requested_harness_to_both_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT)")
    MIGRATION.up(conn)
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    cap_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    assert "requested_harness" in cost_cols
    assert "requested_harness" in cap_cols


def test_m0036_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cost_entries (agent TEXT, type_id TEXT)")
    conn.execute("CREATE TABLE capability_ratings (story_id TEXT, agent TEXT)")
    MIGRATION.up(conn)
    MIGRATION.up(conn)  # must not raise
