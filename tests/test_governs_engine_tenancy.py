import json
import os
import sqlite3

from synlynk.db import _migrate_db


def _connection(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity ("
        "product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', "
        "canonical_path TEXT NOT NULL DEFAULT ''"
        ")"
    )
    return conn


def test_goals_schema_has_product_id(tmp_path):
    conn = _connection(tmp_path)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}

    assert "product_id" in cols


def test_goal_aliases_schema_has_workspace_columns(tmp_path):
    conn = _connection(tmp_path)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_aliases)")}

    assert {"goal_id", "pattern", "product_id"} <= cols


def test_goal_contributions_schema_records_resolution_metadata(tmp_path):
    conn = _connection(tmp_path)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}

    assert {"resolution_reason", "resolved_at"} <= cols


def test_migration_backfills_product_and_quarantines_phantom_goals(tmp_path):
    conn = _connection(tmp_path)
    conn.execute(
        "INSERT INTO state_identity (product_id, mode, canonical_path) VALUES (?, ?, ?)",
        ("prod-local", "repo", str(tmp_path)),
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, status) VALUES (?, ?, ?, ?)",
        (
            "goal-phantom",
            "Foreign",
            "Auto-reconciled during GOVERNS sweep",
            "active",
        ),
    )
    conn.commit()

    _migrate_db(conn)

    goal = conn.execute(
        "SELECT product_id, status FROM goals WHERE goal_id=?", ("goal-phantom",)
    ).fetchone()
    assert goal == ("prod-local", "quarantined")


def test_config_aliases_reads_from_workspace_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "workspace.json", "w", encoding="utf-8") as f:
        json.dump({"goal_aliases": {"goal-1": ["alias-a", "alias-b"]}}, f)
    from synlynk.governs_engine import _config_aliases
    result = _config_aliases(repo_root=str(tmp_path))
    assert result == {"goal-1": ["alias-a", "alias-b"]}


def test_config_aliases_falls_back_to_legacy_config_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"goal_aliases": {"goal-2": ["alias-c"]}}, f)
    from synlynk.governs_engine import _config_aliases
    result = _config_aliases(repo_root=str(tmp_path))
    assert result == {"goal-2": ["alias-c"]}
