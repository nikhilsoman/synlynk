import json
import sqlite3

from synlynk.db import _migrate_db
from synlynk.governs_engine import GoalResolution, associate_story, scoped_goals


def _db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "state.db"))
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity (product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', canonical_path TEXT NOT NULL DEFAULT '')"
    )
    conn.execute("INSERT INTO state_identity(product_id) VALUES ('prod-rxcc')")
    conn.commit()
    return conn


def test_no_hardcoded_goal_ids_in_source():
    import synlynk.governs_resolver as resolver

    assert not hasattr(resolver, "DEFAULT_MASTER_GOAL")
    assert not hasattr(resolver, "_DOMAIN_GOAL_MAP")


def test_waterfall_resolves_via_workspace_alias(tmp_path):
    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES (?, ?, ?, ?, 'active')",
        ("goal-rxcc1", "RxCC Engine", "Criteria", "prod-rxcc"),
    )
    conn.execute(
        "INSERT INTO goal_aliases (goal_id, pattern, product_id) VALUES (?, ?, ?)",
        ("goal-rxcc1", "billing|stripe|invoice", "prod-rxcc"),
    )
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?, ?)", ("story-101", "Fix billing stripe webhook"))
    conn.commit()

    resolution = associate_story(conn, "story-101", title="Fix billing stripe webhook", emit=False)

    assert resolution == GoalResolution("goal-rxcc1", "workspace_alias", "inferred")
    assert conn.execute("SELECT goal_id FROM stories WHERE story_id='story-101'").fetchone()[0] == "goal-rxcc1"


def test_unresolved_story_is_recorded_without_a_foreign_goal(tmp_path):
    conn = _db(tmp_path)
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?, ?)", ("story-unmapped", "Quantum widget optimizer"))
    conn.commit()

    resolution = associate_story(conn, "story-unmapped", title="Quantum widget optimizer", emit=False)

    assert resolution.goal_id is None
    assert resolution.reason == "unresolved"
    row = conn.execute(
        "SELECT link_status, skip_reason FROM goal_contributions WHERE story_id='story-unmapped'"
    ).fetchone()
    assert row == ("unresolved", "no scoped goal matched")


def test_scoped_goals_accept_config_aliases(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".synlynk").mkdir(parents=True)
    (root / ".synlynk" / "config.json").write_text(
        json.dumps({"goal_aliases": {"goal-rxcc1": ["payments"]}})
    )
    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES (?, ?, ?, ?, 'active')",
        ("goal-rxcc1", "RxCC Engine", "Criteria", "prod-rxcc"),
    )
    conn.commit()

    goals = scoped_goals(conn, repo_root=str(root))

    assert goals[0]["aliases"] == ["payments"]


def test_cmd_story_create_associates_in_its_write_transaction(tmp_path):
    db_path = tmp_path / "state.db"
    conn = _db(tmp_path)
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) "
        "VALUES ('goal-alpha', 'User Authentication Flow', 'Login', 'prod-rxcc', 'active')"
    )
    conn.commit()
    conn.close()

    from synlynk.db import cmd_story_create

    story_id = cmd_story_create("Add user login and authentication", db_path=str(db_path))

    conn = sqlite3.connect(str(db_path))
    assert conn.execute(
        "SELECT goal_id FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()[0] == "goal-alpha"
    assert conn.execute(
        "SELECT link_status FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchone()[0] == "linked"
    conn.close()


def test_story_write_without_matching_goal_records_unresolved(tmp_path):
    conn = _db(tmp_path)
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?, ?)", ("story-write", "Unmapped work"))
    from synlynk.governs_engine import associate_story

    associate_story(conn, "story-write", title="Unmapped work", emit=False)
    row = conn.execute(
        "SELECT link_status, skip_reason FROM goal_contributions WHERE story_id=?",
        ("story-write",),
    ).fetchone()
    assert row == ("unresolved", "no scoped goal matched")
