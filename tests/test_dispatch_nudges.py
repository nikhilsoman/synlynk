from unittest.mock import MagicMock, patch

from synlynk.dispatch import _print_pending_nudges, exec_command


def test_print_pending_nudges_reads_config_gate(project_dir, capsys):
    from synlynk import _update_config
    from synlynk.events import emit_event

    emit_event("story_done", {"story_id": "s1", "goal_ids": []}, emitted_by="test")
    _update_config({"nudges": {"enabled": False, "dismissed_ids": [], "last_shown": {}}})

    _print_pending_nudges()

    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_pending_nudges_invokes_workspace_agent_when_enabled(project_dir):
    with patch("synlynk.workspace_agent.cmd_workspace_agent_run") as run_agent:
        _print_pending_nudges()

    run_agent.assert_called_once_with()


def test_exec_command_calls_pending_nudge_hook(project_dir):
    mock_process = MagicMock(returncode=0)
    mock_process.stdout.readline.side_effect = [b""]

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")), \
         patch("subprocess.Popen", return_value=mock_process), \
         patch("synlynk.dispatch._print_pending_nudges") as print_nudges:
        exec_command(["echo", "hello"])

    print_nudges.assert_called_once_with()
