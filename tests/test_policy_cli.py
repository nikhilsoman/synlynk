import json
from pathlib import Path

from synlynk.policy_cli import cmd_policy_check_merge


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
