import json
import inspect
import os
import sqlite3

from synlynk.db import _migrate_db
from synlynk.viz import collect_data
from synlynk.vizor_daemon import build_workspace_routing_handler


def _seed_goal(db_path, product_id, goal_id, outcome):
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity ("
        "product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', "
        "canonical_path TEXT NOT NULL DEFAULT ''"
        ")"
    )
    conn.execute(
        "INSERT INTO state_identity (product_id, mode, canonical_path) VALUES (?, 'repo', ?)",
        (product_id, str(db_path)),
    )
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES (?, ?, ?, ?, 'active')",
        (goal_id, outcome, "Criterion", product_id),
    )
    conn.commit()
    conn.close()


def test_goals_read_through_scoped_db_path(tmp_path):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    _seed_goal(db_a, "prod-a", "goal-a", "Goal A")
    _seed_goal(db_b, "prod-b", "goal-b", "Goal B")

    data_b = collect_data(db_path=str(db_b))
    goal_ids_b = [g["goal_id"] for g in data_b["goals"]]
    assert goal_ids_b == ["goal-b"]


def test_missing_db_path_yields_empty_goals():
    assert collect_data(db_path="/does/not/exist/state.db") == {"goals": []}
    assert collect_data() == {"goals": []}


def test_workspace_goals_route_is_scoped(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    db_path = tmp_path / "state.db"
    _seed_goal(db_path, "prod-a", "goal-a", "Goal A")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "products": {
            "workspace-a": {
                "repo_path": str(repo),
                "canonical_path": str(db_path),
            }
        }
    }))
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(registry))

    handler = build_workspace_routing_handler()
    route_source = inspect.getsource(handler._route_path)
    assert 'api_route == "goals"' in route_source
    assert "collect_data(db_path=str(ctx.db_path))" in route_source


def test_goal_collection_does_not_depend_on_daemon_cwd(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    _seed_goal(db_path, "prod-a", "goal-a", "Goal A")
    old_cwd = os.getcwd()
    try:
        os.chdir("/")
        assert collect_data(db_path=str(db_path))["goals"][0]["goal_id"] == "goal-a"
    finally:
        os.chdir(old_cwd)
