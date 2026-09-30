import sqlite3

import pytest

from synlynk.db import _migrate_db
from synlynk.governs_engine import associate_story, scoped_goals


def _workspace(tmp_path, name, product_id, *, with_goal=True):
    path = tmp_path / f"{name}.db"
    conn = sqlite3.connect(str(path), check_same_thread=False)
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity (product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', canonical_path TEXT NOT NULL DEFAULT '')"
    )
    conn.execute("INSERT INTO state_identity(product_id) VALUES (?)", (product_id,))
    if with_goal:
        conn.execute(
            "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES (?, ?, ?, ?, 'active')",
            ("goal-shared", "Same outcome", "same criterion", product_id),
        )
        conn.execute(
            "INSERT INTO goal_aliases (goal_id, pattern, product_id) VALUES (?, ?, ?)",
            ("goal-shared", name, product_id),
        )
    conn.commit()
    return conn


@pytest.mark.parametrize("case", ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"])
def test_multi_workspace_matrix(case, tmp_path):
    a = _workspace(tmp_path, "synlynk", "prod-a")
    b = _workspace(tmp_path, "rxcc", "prod-b", with_goal=case not in {"M2", "M3"})

    if case == "M1":
        a.execute("INSERT INTO stories (story_id, title) VALUES ('story-a', 'synlynk work')")
        resolution = associate_story(a, "story-a", title="synlynk work", emit=False)
        assert resolution.goal_id == "goal-shared"
        assert not any(g["product_id"] == "prod-b" for g in scoped_goals(a))
    elif case == "M2":
        b.execute("INSERT INTO stories (story_id, title) VALUES ('story-b', 'unmapped work')")
        resolution = associate_story(b, "story-b", title="unmapped work", emit=False)
        assert resolution.goal_id is None
        assert b.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0
    elif case == "M3":
        assert scoped_goals(b) == []
        assert b.execute("SELECT COUNT(*) FROM stories").fetchone()[0] == 0
    elif case == "M4":
        for conn, product in ((a, "prod-a"), (b, "prod-b")):
            conn.execute("INSERT INTO stories (story_id, title) VALUES (?, 'Same outcome')", (product,))
            assert associate_story(conn, product, explicit_goal="goal-shared", emit=False).goal_id == "goal-shared"
        assert a.execute("SELECT product_id FROM goals WHERE goal_id='goal-shared'").fetchone() == ("prod-a",)
        assert b.execute("SELECT product_id FROM goals WHERE goal_id='goal-shared'").fetchone() == ("prod-b",)
    elif case == "M5":
        a.execute("INSERT INTO stories (story_id, title) VALUES ('story-a', 'Same outcome')")
        b.execute("INSERT INTO stories (story_id, title) VALUES ('story-b', 'Same outcome')")
        assert associate_story(a, "story-a", title="Same outcome", emit=False).goal_id == "goal-shared"
        assert associate_story(b, "story-b", title="Same outcome", emit=False).goal_id == "goal-shared"
        assert a.execute("SELECT goal_id FROM stories WHERE story_id='story-a'").fetchone() == ("goal-shared",)
        assert b.execute("SELECT goal_id FROM stories WHERE story_id='story-b'").fetchone() == ("goal-shared",)
    elif case == "M6":
        legacy = sqlite3.connect(str(tmp_path / "legacy.db"))
        _migrate_db(legacy)
        legacy.execute("INSERT INTO goals (goal_id, outcome, criterion, status) VALUES ('goal-legacy', 'Legacy goal', 'legacy criterion', 'active')")
        legacy.execute("INSERT INTO stories (story_id, title) VALUES ('legacy-story', 'Legacy goal')")
        legacy.commit()
        assert scoped_goals(legacy)[0]["goal_id"] == "goal-legacy"
        assert associate_story(legacy, "legacy-story", title="Legacy goal", emit=False).goal_id == "goal-legacy"
    elif case == "M7":
        a.execute("INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES ('goal-phantom', 'x', 'Auto-reconciled during GOVERNS sweep', 'prod-a', 'active')")
        a.commit()
        _migrate_db(a)
        assert a.execute("SELECT status FROM goals WHERE goal_id='goal-phantom'").fetchone()[0] == "quarantined"
    elif case == "M8":
        a.execute("INSERT INTO stories (story_id, title) VALUES ('story-a', 'synlynk work')")
        b.execute("INSERT INTO stories (story_id, title) VALUES ('story-b', 'rxcc work')")
        assert associate_story(a, "story-a", title="synlynk work", emit=False).goal_id == "goal-shared"
        assert associate_story(b, "story-b", title="rxcc work", emit=False).goal_id == "goal-shared"

    a.close()
    b.close()
