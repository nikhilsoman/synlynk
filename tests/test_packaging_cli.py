import sqlite3
import pytest
from synlynk import _get_db
from synlynk.cli import main


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_pkg_cli.db")
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", db_path)
    conn = _get_db(db_path=db_path)
    conn.commit()
    conn.close()
    return db_path


def test_story_umbrella_flag_cli(isolated_db):
    conn = _get_db(db_path=isolated_db)
    conn.execute(
        """INSERT INTO stories (story_id, title, role, stage, status, readiness, umbrella)
           VALUES ('story-umb-1', 'Test Story', 'dev', 'open', 'ready', 'ready', 0)"""
    )
    conn.commit()
    conn.close()

    # Set --umbrella
    with pytest.raises(SystemExit) as exc:
        main(["story", "update", "story-umb-1", "--umbrella"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    row = conn.execute("SELECT umbrella FROM stories WHERE story_id='story-umb-1'").fetchone()
    assert row[0] == 1
    conn.close()

    # Clear with --no-umbrella
    with pytest.raises(SystemExit) as exc:
        main(["story", "update", "story-umb-1", "--no-umbrella"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    row = conn.execute("SELECT umbrella FROM stories WHERE story_id='story-umb-1'").fetchone()
    assert row[0] == 0
    conn.close()


def test_story_depend_cli(isolated_db):
    # Test self-dependency rejection
    with pytest.raises(SystemExit) as exc:
        main(["story", "depend", "story-1", "--on", "story-1"])
    assert exc.value.code == 1

    # Test valid dependency recording
    with pytest.raises(SystemExit) as exc:
        main(["story", "depend", "story-2", "--on", "story-1"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    rows = conn.execute("SELECT story_id, depends_on_story_id FROM story_dependencies").fetchall()
    assert rows == [("story-2", "story-1")]
    conn.close()


def test_release_split_approve_cli(isolated_db):
    # Non-pm role denied
    with pytest.raises(SystemExit) as exc:
        main(["release-split", "approve", "--goal", "goal-1", "--phase", "Phase 1", "--role", "dev"])
    assert exc.value.code == 1

    # PM role authorized
    with pytest.raises(SystemExit) as exc:
        main(["release-split", "approve", "--goal", "goal-1", "--phase", "Phase 1", "--role", "pm"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    rows = conn.execute("SELECT goal_id, phase, approved_by FROM release_split_approvals").fetchall()
    assert rows == [("goal-1", "Phase 1", "pm")]
    conn.close()


def test_goal_packaging_cli(isolated_db):
    # Enable independent phases
    with pytest.raises(SystemExit) as exc:
        main(["goal", "packaging", "--goal", "goal-pkg", "--independent-phases"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    row = conn.execute("SELECT independent_phases FROM goal_packaging_flags WHERE goal_id='goal-pkg'").fetchone()
    assert row[0] == 1
    conn.close()

    # Disable independent phases
    with pytest.raises(SystemExit) as exc:
        main(["goal", "packaging", "--goal", "goal-pkg", "--no-independent-phases"])
    assert exc.value.code == 0

    conn = _get_db(db_path=isolated_db)
    row = conn.execute("SELECT independent_phases FROM goal_packaging_flags WHERE goal_id='goal-pkg'").fetchone()
    assert row[0] == 0
    conn.close()


def test_unflagged_umbrella_reference_warning(tmp_path):
    from synlynk.tpm_sweep import package_next_release_proposal

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, role TEXT, estimated_tokens INTEGER, gh_issue TEXT, readiness TEXT, status TEXT, goal_id TEXT, priority INTEGER, umbrella INTEGER DEFAULT 0, phase TEXT)")
        conn.execute("CREATE TABLE goals (id INTEGER PRIMARY KEY, goal_id TEXT, outcome TEXT, phase_title TEXT, status TEXT, roadmap_priority TEXT)")

        conn.execute("INSERT INTO goals (id, goal_id, outcome, phase_title, status, roadmap_priority) VALUES (1, 'goal-ref', 'Ref Outcome', 'Ref Theme', 'active', 'P1')")
        # Story 1 has reference to Fixes #5498 while umbrella is 0
        conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase, umbrella) VALUES ('s1', 'Refactor backend (Fixes #5498)', 'ready', 'open', 'goal-ref', 1, 'Phase 1', 0)")
        # Story 2 is normal
        conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase, umbrella) VALUES ('s2', 'Normal story', 'ready', 'open', 'goal-ref', 2, 'Phase 1', 0)")
        # Story 3 has reference but umbrella is already 1
        conn.execute("INSERT INTO stories (story_id, title, readiness, status, goal_id, priority, phase, umbrella) VALUES ('s3', 'Epic umbrella (part of #1234)', 'ready', 'open', 'goal-ref', 3, 'Phase 1', 1)")
        conn.commit()

        proposal = package_next_release_proposal(conn=conn, repo_root=str(tmp_path))
        assert proposal is not None
        warnings = proposal.get("warnings", [])
        assert any("Story s1 looks like an umbrella; set the flag" in w for w in warnings)
        assert not any("s3" in w for w in warnings)
        # Story counts are never silently changed
        assert len(proposal["stories"]) == 2  # s1 and s2 (s3 is umbrella=1, so it lands in context)
        assert len(proposal["context_stories"]) == 1
        assert proposal["context_stories"][0]["story_id"] == "s3"
    finally:
        conn.close()
