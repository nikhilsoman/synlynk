import json
from pathlib import Path

from synlynk.policy_cli import cmd_policy_check_merge
from unittest.mock import patch, MagicMock

from synlynk.policy_cli import cmd_policy_sync_branch_protection


def test_cmd_policy_check_merge_exits_zero_for_authorized_role(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    exit_code = cmd_policy_check_merge(role="qa")
    assert exit_code == 0
    assert "cleared to merge" in capsys.readouterr().out


def test_cmd_policy_check_merge_exits_nonzero_for_unauthorized_role(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    exit_code = cmd_policy_check_merge(role="dev")
    assert exit_code != 0
    assert "not authorized" in capsys.readouterr().out


def test_cmd_policy_sync_branch_protection_calls_gh_api_with_required_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with patch("synlynk.policy_cli.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        exit_code = cmd_policy_sync_branch_protection()
    assert exit_code == 0
    called_args = mock_run.call_args[0][0]
    assert "branches/main/protection" in " ".join(called_args)
    request_body = json.loads(mock_run.call_args.kwargs["input"])
    assert "qa-gate" in request_body["required_status_checks"]["contexts"]


def test_cmd_policy_sync_branch_protection_dry_run_does_not_call_gh(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with patch("synlynk.policy_cli.subprocess.run") as mock_run:
        exit_code = cmd_policy_sync_branch_protection(dry_run=True)
    assert exit_code == 0
    mock_run.assert_not_called()
