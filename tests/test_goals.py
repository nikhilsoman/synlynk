import sqlite3
from synlynk import _get_db


def test_goals_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    assert cols == {"id", "goal_id", "outcome", "criterion", "deadline", "status", "created_at"}
    conn.close()


def test_goal_contributions_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    assert cols == {"id", "goal_id", "story_id"}
    conn.close()


def test_stories_and_arcs_have_goal_id_column():
    conn = _get_db()
    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    arc_cols = {row[1] for row in conn.execute("PRAGMA table_info(roadmap_arcs)")}
    assert "goal_id" in story_cols
    assert "goal_id" in arc_cols
    conn.close()


def test_goal_create_returns_goal_id_and_persists():
    from synlynk.db import cmd_goal_create
    goal_id = cmd_goal_create(
        outcome="Ship agent role split to v0.10.0",
        criterion="synlynk dispatch routes 100% of implementation work to non-Claude agents",
        deadline="2026-09-01",
    )
    assert goal_id.startswith("goal-")
    conn = _get_db()
    row = conn.execute(
        "SELECT outcome, criterion, deadline, status FROM goals WHERE goal_id=?", (goal_id,)
    ).fetchone()
    conn.close()
    assert row == (
        "Ship agent role split to v0.10.0",
        "synlynk dispatch routes 100% of implementation work to non-Claude agents",
        "2026-09-01",
        "active",
    )


def test_goal_list_prints_active_goals(capsys):
    from synlynk.db import cmd_goal_create, cmd_goal_list
    cmd_goal_create(outcome="Outcome A", criterion="Criterion A")
    cmd_goal_list()
    captured = capsys.readouterr()
    assert "Outcome A" in captured.out


def test_goal_link_sets_primary_goal_id_on_story():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_id = cmd_goal_create(outcome="O", criterion="C")
    story_id = cmd_story_create(title="Do the thing")
    cmd_goal_link(story_id, goal_id)
    conn = _get_db()
    row = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    conn.close()
    assert row[0] == goal_id


def test_goal_link_secondary_writes_contribution_not_primary():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_a = cmd_goal_create(outcome="A", criterion="C")
    goal_b = cmd_goal_create(outcome="B", criterion="C")
    story_id = cmd_story_create(title="Cross-cutting work")
    cmd_goal_link(story_id, goal_a)
    cmd_goal_link(story_id, goal_b, secondary=True)
    conn = _get_db()
    primary = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()[0]
    contributions = conn.execute(
        "SELECT goal_id FROM goal_contributions WHERE story_id=?", (story_id,)
    ).fetchall()
    conn.close()
    assert primary == goal_a
    assert contributions == [(goal_b,)]


def test_goal_status_reports_story_counts(capsys):
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link, cmd_goal_status
    from synlynk import _get_db
    goal_id = cmd_goal_create(outcome="Ship it", criterion="All stories done")
    s1 = cmd_story_create(title="Story one")
    s2 = cmd_story_create(title="Story two")
    cmd_goal_link(s1, goal_id)
    cmd_goal_link(s2, goal_id)
    conn = _get_db()
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (s1,))
    conn.commit()
    conn.close()
    cmd_goal_status()
    captured = capsys.readouterr()
    assert "Ship it" in captured.out
    assert "1/2" in captured.out


def test_cli_goal_create_and_list(capsys, monkeypatch):
    import sys
    from synlynk.cli import main
    monkeypatch.setattr(
        sys, "argv",
        ["synlynk", "goal", "create", "--outcome", "Ship BS-8", "--criterion", "goals table exists"]
    )
    main()
    captured = capsys.readouterr()
    assert "Goal created: goal-" in captured.out

    monkeypatch.setattr(sys, "argv", ["synlynk", "goal", "list"])
    main()
    captured = capsys.readouterr()
    assert "Ship BS-8" in captured.out


def test_context_from_db_includes_active_goal(tmp_path, monkeypatch):
    from synlynk.db import cmd_goal_create
    from synlynk import _generate_context_from_db
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    cmd_goal_create(
        outcome="Ship BS-8",
        criterion="goals table exists and CLI works",
        deadline="2026-09-01",
    )
    context = _generate_context_from_db(out_path=str(tmp_path / ".synlynk" / "context.md"))
    assert "## Active Goal" in context
    assert "Ship BS-8" in context
    assert "goals table exists and CLI works" in context
