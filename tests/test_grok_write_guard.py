import os
from unittest.mock import MagicMock, patch
import pytest

from synlynk.dispatch import (
    task_requires_write,
    check_grok_sandbox_write_capability,
    dispatch_agent,
)


def test_task_requires_write_variations():
    assert task_requires_write("implement something new", task_type=None) is True
    assert task_requires_write("fix bug in cli", task_type=None) is True
    assert task_requires_write("read documentation", task_type="read") is False
    assert task_requires_write("some task", requires_gh_write=True) is True
    assert task_requires_write("arbitrary task", permissions=["run:shell"]) is True
    assert task_requires_write("explore workspace", task_type="research") is False


def test_check_grok_sandbox_write_capability_env_override(monkeypatch):
    monkeypatch.setenv("SYNLYNK_GROK_DENY_WRITE", "1")
    assert check_grok_sandbox_write_capability() is False

    monkeypatch.delenv("SYNLYNK_GROK_DENY_WRITE", raising=False)
    monkeypatch.setenv("SYNLYNK_GROK_WRITE_CAPABLE", "false")
    assert check_grok_sandbox_write_capability() is False


def test_check_grok_sandbox_write_capability_disk_probe(tmp_path):
    assert check_grok_sandbox_write_capability(worktree_path=str(tmp_path)) is True

    # Read-only directory simulation
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    os.chmod(str(ro_dir), 0o444)
    try:
        assert check_grok_sandbox_write_capability(worktree_path=str(ro_dir)) is False
    finally:
        os.chmod(str(ro_dir), 0o755)


def test_grok_write_guard_failover_when_denied(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNLYNK_GROK_DENY_WRITE", "1")
    
    with patch("synlynk.dispatch.subprocess.Popen") as mock_popen, \
         patch("synlynk.dispatch._create_job_worktree") as mock_wt, \
         patch("synlynk.dispatch._secondary_harness", return_value="codex"):
        
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        mock_wt.return_value = {
            "path": str(tmp_path),
            "base_branch": "main",
            "base_sha": "abcd123",
        }

        # Dispatch grok with a write-required task
        res = dispatch_agent(
            "grok",
            task="implement feature X",
            skip_preflight=True,
            _startup_failover=True,
        )

        # Should have routed to codex
        assert res["agent"] == "codex"


def test_grok_write_guard_raises_when_forced(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNLYNK_GROK_DENY_WRITE", "1")
    
    with pytest.raises(RuntimeError, match="Grok sandbox denies write capability"):
        dispatch_agent(
            "grok",
            task="implement feature X",
            force_agent=True,
            skip_preflight=True,
            _startup_failover=False,
        )
