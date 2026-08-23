from unittest.mock import MagicMock, patch

from synlynk.tpm_sweep import run_sweep_pass


def test_run_sweep_pass_advances_authorized_story(isolated_db, project_dir):
    from synlynk.db import cmd_story_create, cmd_story_ready

    story_id = cmd_story_create(title="test story", story_id="story-1")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-1", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    assert summary["parked"] == 0


def test_run_sweep_pass_parks_story_requiring_approval(isolated_db, project_dir):
    from synlynk.db import cmd_story_create, cmd_story_ready

    story_id = cmd_story_create(title="release story", story_id="story-2")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket, \
            patch("synlynk.tpm_sweep.emit_awaiting_approval") as mock_event:
        mock_auth.return_value = MagicMock(
            allowed=True, requires_approval=True, reason="named_release"
        )
        mock_ticket.return_value = "https://github.com/x/y/issues/1"
        summary = run_sweep_pass()
    assert summary["parked"] == 1
    assert summary["advanced"] == 0
