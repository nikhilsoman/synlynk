from unittest.mock import MagicMock, patch

from synlynk.approval_gate import raise_approval_ticket


def test_raise_approval_ticket_calls_gh_issue_create_with_assignee_and_context():
    with patch("synlynk.approval_gate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/x/y/issues/123\n",
            stderr="",
        )
        url = raise_approval_ticket(
            story_id="story-1",
            action="release_cut",
            reason="named_release",
            assignee="nikhilsoman",
            context="Goal: ship v0.16.0\nNo PR yet\n",
        )
    assert url == "https://github.com/x/y/issues/123"
    args = mock_run.call_args[0][0]
    assert "--assignee" in args and "nikhilsoman" in args
    assert any("APPROVAL" in arg for arg in args)


def test_raise_approval_ticket_returns_empty_on_gh_failure():
    with patch("synlynk.approval_gate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="rate limited")
        url = raise_approval_ticket(
            story_id="story-1",
            action="release_cut",
            reason="named_release",
            assignee="nikhilsoman",
            context="x",
        )
    assert url == ""
