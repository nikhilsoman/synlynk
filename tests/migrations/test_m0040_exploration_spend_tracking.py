import sqlite3

from synlynk.migrations.m0040_exploration_spend_tracking import MIGRATION


def test_m0040_creates_per_harness_exploration_spend_table():
    conn = sqlite3.connect(":memory:")

    MIGRATION.up(conn)

    columns = {
        row[1]: row for row in conn.execute("PRAGMA table_info(exploration_spend)")
    }
    assert set(columns) == {"harness", "total_cost_usd", "sample_count", "updated_at"}
    assert columns["harness"][5] == 1
    assert columns["total_cost_usd"][4] == "0.0"
    assert columns["sample_count"][4] == "0"

    conn.execute("INSERT INTO exploration_spend (harness) VALUES ('codex')")
    row = conn.execute(
        "SELECT harness, total_cost_usd, sample_count FROM exploration_spend"
    ).fetchone()
    assert row == ("codex", 0.0, 0)


def test_m0040_is_idempotent_and_preserves_existing_spend():
    conn = sqlite3.connect(":memory:")

    MIGRATION.up(conn)
    conn.execute(
        "INSERT INTO exploration_spend (harness, total_cost_usd, sample_count) "
        "VALUES ('claude', 1.25, 3)"
    )

    MIGRATION.up(conn)

    row = conn.execute(
        "SELECT total_cost_usd, sample_count FROM exploration_spend WHERE harness='claude'"
    ).fetchone()
    assert row == (1.25, 3)

