import sqlite3
from synlynk import _get_db


def test_goals_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goals)")}
    assert cols == {
        "id", "goal_id", "product_id", "outcome", "criterion", "deadline",
        "status", "created_at", "kind",
    }
    conn.close()


def test_goal_contributions_table_created():
    conn = _get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    assert cols == {
        "id", "goal_id", "story_id", "link_status", "skip_reason",
        "resolution_reason", "resolved_at",
    }
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
        role="pm",
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
    cmd_goal_create(outcome="Outcome A", criterion="Criterion A", role="pm")
    cmd_goal_list()
    captured = capsys.readouterr()
    assert "Outcome A" in captured.out


def test_goal_link_sets_primary_goal_id_on_story():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_id = cmd_goal_create(outcome="O", criterion="C", role="pm")
    story_id = cmd_story_create(title="Do the thing")
    cmd_goal_link(story_id, goal_id)
    conn = _get_db()
    row = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    conn.close()
    assert row[0] == goal_id


def test_goal_link_secondary_writes_contribution_not_primary():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link
    goal_a = cmd_goal_create(outcome="A", criterion="C", role="pm")
    goal_b = cmd_goal_create(outcome="B", criterion="C", role="pm")
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
    goal_id = cmd_goal_create(outcome="Ship it", criterion="All stories done", role="pm")
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


def test_goal_update_changes_status():
    from synlynk.db import cmd_goal_create, cmd_goal_update

    goal_id = cmd_goal_create(outcome="Ship it", criterion="Done", role="pm")
    cmd_goal_update(goal_id, status="done")
    conn = _get_db()
    status = conn.execute("SELECT status FROM goals WHERE goal_id=?", (goal_id,)).fetchone()[0]
    conn.close()
    assert status == "done"


def test_goal_update_changes_deadline():
    from synlynk.db import cmd_goal_create, cmd_goal_update

    goal_id = cmd_goal_create(outcome="Ship it", criterion="Done", role="pm")
    cmd_goal_update(goal_id, deadline="2026-12-31")
    conn = _get_db()
    deadline = conn.execute("SELECT deadline FROM goals WHERE goal_id=?", (goal_id,)).fetchone()[0]
    conn.close()
    assert deadline == "2026-12-31"


def test_goal_update_supersede_relinks_open_stories_but_not_done_stories():
    from synlynk.db import cmd_goal_create, cmd_story_create, cmd_goal_link, cmd_goal_update

    old_goal = cmd_goal_create(outcome="Old", criterion="Replace me", role="pm")
    new_goal = cmd_goal_create(outcome="New", criterion="Replacement", role="pm")
    open_primary = cmd_story_create(title="Open primary")
    open_secondary = cmd_story_create(title="Open secondary")
    done_story = cmd_story_create(title="Done story")
    cmd_goal_link(open_primary, old_goal)
    cmd_goal_link(open_secondary, old_goal, secondary=True)
    cmd_goal_link(done_story, old_goal)
    conn = _get_db()
    conn.execute("UPDATE stories SET status='done' WHERE story_id=?", (done_story,))
    conn.commit()
    conn.close()

    cmd_goal_update(old_goal, supersede_with=new_goal)

    conn = _get_db()
    story_rows = conn.execute(
        "SELECT story_id, goal_id FROM stories WHERE story_id IN (?, ?, ?) ORDER BY story_id",
        (open_primary, open_secondary, done_story),
    ).fetchall()
    contributions = conn.execute(
        "SELECT story_id, goal_id FROM goal_contributions WHERE story_id=?",
        (open_secondary,),
    ).fetchall()
    old_status = conn.execute("SELECT status FROM goals WHERE goal_id=?", (old_goal,)).fetchone()[0]
    conn.close()
    assert dict(story_rows)[open_primary] == new_goal
    assert dict(story_rows)[open_secondary] == new_goal
    assert dict(story_rows)[done_story] == old_goal
    assert contributions == [(open_secondary, new_goal)]
    assert old_status == "superseded"


def test_goal_update_rejects_invalid_values():
    import pytest
    from synlynk.db import cmd_goal_create, cmd_goal_update

    goal_id = cmd_goal_create(outcome="O", criterion="C", role="pm")
    with pytest.raises(ValueError, match="Invalid goal status"):
        cmd_goal_update(goal_id, status="paused")
    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        cmd_goal_update(goal_id, deadline="2026-2-30")
    with pytest.raises(ValueError, match="Goal 'goal-missing' not found"):
        cmd_goal_update("goal-missing", status="done")
    with pytest.raises(ValueError, match="Goal 'goal-missing' not found"):
        cmd_goal_update(goal_id, supersede_with="goal-missing")


def test_cli_goal_create_and_list(capsys, monkeypatch):
    import sys
    from synlynk.cli import main
    monkeypatch.setattr(
        sys, "argv",
        ["synlynk", "goal", "create", "--outcome", "Ship BS-8", "--criterion", "goals table exists", "--role", "pm"]
    )
    main()
    captured = capsys.readouterr()
    assert "Goal created: goal-" in captured.out

    monkeypatch.setattr(sys, "argv", ["synlynk", "goal", "list"])
    main()
    captured = capsys.readouterr()
    assert "Ship BS-8" in captured.out


def test_cli_goal_update_status(capsys, monkeypatch):
    import sys
    from synlynk.cli import main

    monkeypatch.setattr(
        sys,
        "argv",
        ["synlynk", "goal", "create", "--outcome", "CLI goal", "--criterion", "works", "--role", "pm"],
    )
    main()
    created = capsys.readouterr().out
    goal_id = created.split("Goal created: ", 1)[1].split()[0]
    monkeypatch.setattr(sys, "argv", ["synlynk", "goal", "update", goal_id, "--status", "done"])
    main()
    assert "Goal updated: " + goal_id in capsys.readouterr().out


def test_context_from_db_includes_active_goal(tmp_path, monkeypatch):
    from synlynk.db import cmd_goal_create
    from synlynk import _generate_context_from_db
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    cmd_goal_create(
        outcome="Ship BS-8",
        criterion="goals table exists and CLI works",
        deadline="2026-09-01",
        role="pm",
    )
    context = _generate_context_from_db(out_path=str(tmp_path / ".synlynk" / "context.md"))
    assert "## Active Goal" in context
    assert "Ship BS-8" in context
    assert "goals table exists and CLI works" in context
