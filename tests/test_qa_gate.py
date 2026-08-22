from unittest.mock import patch, MagicMock
import json
import os
import pytest
import synlynk

from synlynk.qa_gate import (
    _qa_gate_ci_status,
    _qa_gate_sentinel_health,
    _qa_gate_mode,
    _gh_pr_changed_files,
    qa_gate_verdict,
)


def test_qa_gate_mode_defaults_to_block_only_when_key_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "synlynk").mkdir()
    (tmp_path / "synlynk" / "config.json").write_text('{}')
    assert _qa_gate_mode() == 'block-only'


def test_qa_gate_mode_reads_configured_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "synlynk").mkdir()
    (tmp_path / "synlynk" / "config.json").write_text('{"qa_gate_mode": "merge-restricted-classes"}')
    assert _qa_gate_mode() == 'merge-restricted-classes'


def test_qa_gate_mode_defaults_to_block_only_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _qa_gate_mode() == 'block-only'


def test_gh_pr_changed_files_parses_gh_output():
    result = MagicMock(returncode=0, stdout='docs/a.md\ndocs/b.md\n')
    with patch('subprocess.run', return_value=result) as mock_run:
        files = _gh_pr_changed_files(1234)
    assert files == ['docs/a.md', 'docs/b.md']
    assert mock_run.call_args.args[0] == ['gh', 'pr', 'diff', '1234', '--name-only']


def test_gh_pr_changed_files_returns_empty_list_on_gh_failure():
    result = MagicMock(returncode=1, stdout='')
    with patch('subprocess.run', return_value=result):
        assert _gh_pr_changed_files(1234) == []


def test_qa_gate_ci_status_green_when_ci_passes():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=True):
        assert _qa_gate_ci_status() is True


def test_qa_gate_ci_status_red_when_ci_fails():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=False):
        assert _qa_gate_ci_status() is False


def test_qa_gate_ci_status_none_when_undeterminable():
    with patch("synlynk.qa_gate._extract_verified_by_ci", return_value=None):
        assert _qa_gate_ci_status() is None


_SENTINEL_ISSUES_HIGH = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ FLATLINE: 3 consecutive exec failures", "number": 501},
])
_SENTINEL_ISSUES_MEDIUM_ONLY = json.dumps([
    {"title": "[support] sentinel_alerts: ⚠ slow response time observed", "number": 502},
])
_SENTINEL_ISSUES_NONE = json.dumps([])
_SENTINEL_ISSUES_UNRELATED = json.dumps([
    {"title": "[support] telemetry_anomaly: high failure rate", "number": 503},
])


def _mock_gh_issue_list(stdout, returncode=0):
    result = type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})()
    return result


def test_qa_gate_sentinel_health_red_on_high_severity_open_issue():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_HIGH)):
        assert _qa_gate_sentinel_health("owner", "repo") is False


def test_qa_gate_sentinel_health_green_on_medium_only():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_MEDIUM_ONLY)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_green_on_no_open_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_NONE)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_ignores_unrelated_support_issues():
    with patch("subprocess.run", return_value=_mock_gh_issue_list(_SENTINEL_ISSUES_UNRELATED)):
        assert _qa_gate_sentinel_health("owner", "repo") is True


def test_qa_gate_sentinel_health_none_when_gh_errors():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("", returncode=1)):
        assert _qa_gate_sentinel_health("owner", "repo") is None


def test_qa_gate_sentinel_health_none_on_malformed_json():
    with patch("subprocess.run", return_value=_mock_gh_issue_list("not json")):
        assert _qa_gate_sentinel_health("owner", "repo") is None


def test_qa_gate_verdict_green_when_both_signals_healthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "green"
    assert verdict["ci_status"] is True
    assert verdict["sentinel_status"] is True


def test_qa_gate_verdict_red_when_ci_fails():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=False), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "CI" in verdict["reason"]


def test_qa_gate_verdict_red_when_sentinel_unhealthy():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=False):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "sentinel" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_ci_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=None), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=True):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()


def test_qa_gate_verdict_fails_closed_when_sentinel_status_undeterminable():
    with patch("synlynk.qa_gate._qa_gate_ci_status", return_value=True), \
         patch("synlynk.qa_gate._qa_gate_sentinel_health", return_value=None):
        verdict = qa_gate_verdict("owner", "repo")
    assert verdict["verdict"] == "red"
    assert "undeterminable" in verdict["reason"].lower()


def test_load_config_defaults_qa_gate_mode_to_block_only(project_dir):
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"


def test_load_config_preserves_explicit_qa_gate_mode(project_dir):
    config_path = project_dir / ".synlynk" / "config.json"
    existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    existing["qa_gate_mode"] = "block-only"
    config_path.write_text(json.dumps(existing))
    config = synlynk.load_config()
    assert config["qa_gate_mode"] == "block-only"


def test_cmd_pr_gate_status_exits_zero_on_green(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    green_verdict = {
        "verdict": "green", "ci_status": True, "sentinel_status": True,
        "reason": "CI green, no unresolved sentinel alert",
    }
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=green_verdict):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "green" in captured.out.lower()


def test_cmd_pr_gate_status_exits_one_on_red(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    red_verdict = {
        "verdict": "red", "ci_status": False, "sentinel_status": True,
        "reason": "CI matrix is red",
    }
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=red_verdict):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "red" in captured.out.lower()


def test_cmd_pr_gate_status_passes_github_head_ref_as_worktree_branch():
    from synlynk.qa_gate import cmd_pr_gate_status
    green_verdict = {
        "verdict": "green", "ci_status": True, "sentinel_status": True,
        "reason": "CI green, no unresolved sentinel alert",
    }
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=green_verdict) as mock_verdict, \
         patch.dict("os.environ", {"GITHUB_HEAD_REF": "feat/qa-gate-ci-workflow"}):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 0
    mock_verdict.assert_called_once_with(
        "nikhilsoman", "synlynk", worktree_branch="feat/qa-gate-ci-workflow"
    )


def test_cmd_pr_gate_status_worktree_branch_none_when_github_head_ref_unset():
    from synlynk.qa_gate import cmd_pr_gate_status
    green_verdict = {
        "verdict": "green", "ci_status": True, "sentinel_status": True,
        "reason": "CI green, no unresolved sentinel alert",
    }
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_HEAD_REF"}
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=("nikhilsoman", "synlynk")), \
         patch("synlynk.qa_gate.qa_gate_verdict", return_value=green_verdict) as mock_verdict, \
         patch.dict("os.environ", env, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 0
    mock_verdict.assert_called_once_with(
        "nikhilsoman", "synlynk", worktree_branch=None
    )


def test_cmd_pr_gate_status_exits_one_when_remote_undetectable(capsys):
    from synlynk.qa_gate import cmd_pr_gate_status
    with patch("synlynk.qa_gate.detect_remote_owner_repo", return_value=(None, None)):
        with pytest.raises(SystemExit) as exc_info:
            cmd_pr_gate_status()
    assert exc_info.value.code == 1


def test_cli_pr_gate_status_invokes_cmd(monkeypatch):
    import sys
    from synlynk import cli

    called = {}

    def fake_cmd():
        called["ran"] = True
        raise SystemExit(0)

    monkeypatch.setattr("synlynk.qa_gate.cmd_pr_gate_status", fake_cmd)
    monkeypatch.setattr(sys, "argv", ["synlynk", "pr", "gate-status"])
    with pytest.raises(SystemExit):
        cli.main()
    assert called.get("ran") is True
