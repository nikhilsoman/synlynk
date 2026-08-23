from unittest.mock import MagicMock, patch

from synlynk.db import cmd_goal_create, cmd_goal_link, cmd_story_create, cmd_story_done
from synlynk.workspace_agent import cmd_workspace_agent_run


def test_nudges_on_goal_fully_closed(project_dir, capsys):
    story_id = cmd_story_create(title="Only story")
    goal_id = cmd_goal_create("Ship the thing", "All stories done", role="pm")
    cmd_goal_link(story_id, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert goal_id in captured.out
    assert "closed" in captured.out.lower()


def test_no_nudge_when_goal_still_has_open_stories(project_dir, capsys):
    story_id = cmd_story_create(title="Story one")
    story_id_2 = cmd_story_create(title="Story two")
    goal_id = cmd_goal_create("Ship the thing", "All stories done", role="pm")
    cmd_goal_link(story_id, goal_id)
    cmd_goal_link(story_id_2, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert "closed" not in captured.out.lower()


def test_nudges_use_agent_specific_checkpoint_no_repeat(project_dir, capsys):
    story_id = cmd_story_create(title="Only story")
    goal_id = cmd_goal_create("Ship the thing", "All stories done", role="pm")
    cmd_goal_link(story_id, goal_id)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmd_story_done(story_id)
        cmd_workspace_agent_run()
        capsys.readouterr()
        cmd_workspace_agent_run()

    captured = capsys.readouterr()
    assert goal_id not in captured.out
