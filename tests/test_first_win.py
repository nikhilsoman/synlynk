import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from synlynk.first_win import dispatch_first_win_task


def test_dispatch_first_win_task_creates_isolated_worktree():
    goal = {"outcome": "Add unit tests", "criterion": "pytest passes"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="worktree added")
        res = dispatch_first_win_task(goal, "/tmp/fake_repo")
        assert res["status"] == "dispatched"
        assert "feat/first-win" in res["branch"]
        assert res["worktree_isolated"] is True


def test_dispatch_first_win_task_handles_git_failure():
    goal = {"outcome": "Add unit tests", "criterion": "pytest passes"}
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("git error")
        res = dispatch_first_win_task(goal, "/tmp/fake_repo")
        assert res["status"] == "error"
        assert "git error" in res["error"]
