import json
import sqlite3
from pathlib import Path

from synlynk.migrations import m0042_release_packaging
from synlynk.migrations.runner import MIGRATIONS
from synlynk.policy import DEFAULT_WORKSPACE_POLICY
from synlynk.release_packaging import DEFAULT_LIMITS, load_limits


EXPECTED_LIMITS = {
    "goal_story_ceiling": 30,
    "goal_token_ceiling": 1_500_000,
    "mixed_pool_cap": 5,
}


def test_default_limits_are_available_in_code_and_policy():
    repo_root = Path(__file__).parents[1]
    repo_policy = json.loads((repo_root / ".synlynk" / "policy.json").read_text())

    assert DEFAULT_LIMITS == EXPECTED_LIMITS
    assert DEFAULT_WORKSPACE_POLICY["defaults"]["release_packaging"] == EXPECTED_LIMITS
    assert repo_policy["overrides"]["release_packaging"] == EXPECTED_LIMITS


def test_load_limits_merges_and_coerces_repo_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    policy_dir = tmp_path / "repo" / ".synlynk"
    policy_dir.mkdir(parents=True)
    (policy_dir / "policy.json").write_text(
        json.dumps(
            {
                "overrides": {
                    "release_packaging": {"goal_story_ceiling": "10"}
                }
            }
        )
    )

    limits = load_limits(str(tmp_path / "repo"))

    assert limits == {
        "goal_story_ceiling": 10,
        "goal_token_ceiling": 1_500_000,
        "mixed_pool_cap": 5,
    }


def test_migration_adds_release_packaging_schema_and_backfills_live_35():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE stories (story_id TEXT UNIQUE, gh_issue TEXT, status TEXT)"
    )
    conn.executemany(
        "INSERT INTO stories (story_id, gh_issue, status) VALUES (?, ?, 'ready')",
        [("parent", "5498"), ("ordinary", "5600")],
    )

    m0042_release_packaging.MIGRATION.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "umbrella" in columns
    assert conn.execute(
        "SELECT umbrella FROM stories WHERE story_id = 'parent'"
    ).fetchone() == (1,)
    assert conn.execute(
        "SELECT umbrella FROM stories WHERE story_id = 'ordinary'"
    ).fetchone() == (0,)

    conn.execute("INSERT INTO story_dependencies VALUES ('a', 'b')")
    conn.execute(
        "INSERT INTO release_split_approvals (goal_id, phase) VALUES ('g', 'p1')"
    )
    conn.execute(
        "INSERT INTO goal_packaging_flags (goal_id, independent_phases) "
        "VALUES ('g', 1)"
    )

    m0042_release_packaging.MIGRATION.up(conn)

    assert conn.execute("SELECT * FROM story_dependencies").fetchall() == [("a", "b")]
    assert conn.execute(
        "SELECT goal_id, phase, approved_by, approved_at "
        "FROM release_split_approvals"
    ).fetchone()[:3] == ("g", "p1", None)
    assert conn.execute("SELECT * FROM goal_packaging_flags").fetchall() == [("g", 1)]


def test_release_packaging_migration_is_registered_last():
    assert m0042_release_packaging.MIGRATION.version == 42
    assert MIGRATIONS[-1] is m0042_release_packaging.MIGRATION


def test_migration_supports_partial_databases_without_stories():
    conn = sqlite3.connect(":memory:")

    m0042_release_packaging.MIGRATION.up(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "story_dependencies",
        "release_split_approvals",
        "goal_packaging_flags",
    } <= tables


def test_migration_supports_partial_stories_table_without_gh_issue():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE stories (story_id TEXT UNIQUE)")

    m0042_release_packaging.MIGRATION.up(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "umbrella" in columns
