from unittest.mock import patch

import synlynk

from synlynk.db import cmd_goal_create, cmd_goal_link, cmd_pr_check, cmd_story_create


def test_pr_check_soft_warns_on_unlinked_story(project_dir, capsys):
    story_id = cmd_story_create(title="PR story")
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 42, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()
    captured = capsys.readouterr()
    assert "no linked GOVERNS goal" in captured.out
    assert story_id in captured.out


def test_pr_check_does_not_warn_when_goal_linked(project_dir, capsys):
    story_id = cmd_story_create(title="PR story")
    goal_id = cmd_goal_create("Outcome", "Criterion")
    cmd_goal_link(story_id, goal_id)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 43, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()
    captured = capsys.readouterr()
    assert "no linked GOVERNS goal" not in captured.out


def test_pr_check_soft_warn_does_not_change_exit_code(project_dir):
    story_id = cmd_story_create(title="PR story")
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, pr_number, quality, signal_source) "
        "VALUES (?, 'codex', 'gpt-5', 44, 8.0, 'human')",
        (story_id,),
    )
    conn.commit()
    conn.close()
    with patch("synlynk.pr_multiplier._is_github_remote", return_value=False):
        cmd_pr_check()
