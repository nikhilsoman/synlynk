import io
from unittest.mock import patch
from synlynk import wizard


def test_wizard_prints_real_job_id(capsys):
    """Assert wizard prints real job id from dispatch_agent dict {"id": "..."} (Fixes #5297)."""
    fake_job = {
        "id": "job-abc12345",
        "agent": "claude",
        "pid": 9999,
    }

    chosen_task = {
        "id": "task-1",
        "title": "Review architecture",
        "agent": "claude",
        "cycle": "Visualize",
        "prompt": "Test prompt",
        "context_mode": "full",
    }

    def mock_pkg(name):
        if name == "dispatch_agent":
            return lambda **kw: fake_job
        if name == "run_workspace_scan":
            return lambda deep=False: {"workspace_name": "test-ws"}
        if name in ("_generate_launch_tasks", "_select_launch_tasks"):
            return lambda scan: [chosen_task]
        return None

    with patch.dict(wizard.__dict__, {"_pkg": mock_pkg}), \
         patch("synlynk.wizard._launch_screen_tasks", return_value=chosen_task), \
         patch("synlynk.wizard._launch_screen_preview", return_value=(True, "Test prompt")):

        wizard.cmd_launch_ftue(dry_run=False, list_mode=False)
        captured = capsys.readouterr().out
        assert "[job-abc12345] claude dispatched" in captured
        assert "Log: synlynk logs --job job-abc12345" in captured
        assert "unknown" not in captured
