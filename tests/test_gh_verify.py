import subprocess

from synlynk.gh_verify import _parse_iso8601, gh_write_verified


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


def test_parse_iso8601_handles_z_suffix():
    dt = _parse_iso8601("2026-08-18T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 8 and dt.day == 18
    assert dt.hour == 10


def test_parse_iso8601_handles_offset_suffix():
    dt = _parse_iso8601("2026-08-18T10:00:00+00:00")
    assert dt is not None
    assert dt.hour == 10


def test_parse_iso8601_returns_none_for_garbage():
    assert _parse_iso8601("not-a-timestamp") is None


def test_parse_iso8601_returns_none_for_none():
    assert _parse_iso8601(None) is None
