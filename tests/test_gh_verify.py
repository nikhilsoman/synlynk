import subprocess

from synlynk.gh_verify import gh_write_verified


def test_gh_write_verified_true_when_issue_closed(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "issue", "view"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"CLOSED"}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is True


def test_gh_write_verified_false_when_issue_still_open(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"OPEN"}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is False


def test_gh_write_verified_true_when_pr_merged(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "pr", "view"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"state":"MERGED"}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("pr:964", expect="merged") is True


def test_gh_write_verified_unknown_when_target_none():
    assert gh_write_verified(None, expect="closed") is None


def test_gh_write_verified_unknown_when_gh_cli_errors(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="gh: not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is None


def test_gh_write_verified_unknown_when_gh_cli_times_out(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 5))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified("issue:701", expect="closed") is None


def test_gh_write_verified_rejects_malformed_target():
    assert gh_write_verified("not-a-valid-target", expect="closed") is None
