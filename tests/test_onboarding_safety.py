"""Tests for Zero-Risk Onboarding, Dirty-Tree Safety Guard, and First-Win Auto-Remediation."""

import os
import subprocess
import tarfile
import time
from unittest.mock import MagicMock, patch

import pytest

from synlynk.agent_cli import SEED_CHARTERS
from synlynk.launch import (
    dispatch_first_win_remediation,
    find_top_scan_finding,
    prompt_first_win_remediation,
)
from synlynk.wizard import BackupResult, cmd_wizard_init, guard_dirty_worktree


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary initialized git repository with an initial commit."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\nInitial content\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


def test_guard_dirty_worktree_clean_tree(git_repo):
    """Clean git tree returns None and creates no backup."""
    result = guard_dirty_worktree(repo_dir=str(git_repo))
    assert result is None
    backup_dir = git_repo / ".synlynk" / "backups"
    assert not backup_dir.exists()


def test_guard_dirty_worktree_dirty_tree(git_repo):
    """Dirty or untracked state creates tar.gz in .synlynk/backups/ and git stash."""
    # Modify tracked file and add untracked file
    readme = git_repo / "README.md"
    readme.write_text("# Test Repo\nModified work-in-progress\n")
    untracked = git_repo / "feature.py"
    untracked.write_text("print('hello uncommitted')\n")

    result = guard_dirty_worktree(repo_dir=str(git_repo))

    assert result is not None
    assert isinstance(result, BackupResult)
    assert result.dirty is True
    assert result.stash_created is True
    assert os.path.exists(result.backup_path)
    assert "init-" in str(result)
    assert str(result).endswith(".tar.gz")

    # Verify backup tar contents
    with tarfile.open(result.backup_path, "r:gz") as tar:
        names = tar.getnames()
        assert "README.md" in names
        assert "feature.py" in names

    # Verify git stash was recorded
    stash_proc = subprocess.run(
        ["git", "stash", "list"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "synlynk-init-safety-backup-" in stash_proc.stdout


def test_cmd_wizard_init_speed_and_charters(tmp_path, monkeypatch):
    """cmd_wizard_init probes harnesses, detects stack, provisions 8 charters in <5s, and ingests backlog."""
    # Seed simple python file to detect Python stack
    (tmp_path / "app.py").write_text("def main(): pass\n")

    harnesses_mock = [{"name": "claude", "cli": "claude", "version": "1.0", "path": "/bin/claude"}]
    backlog_mock = {"ingested": 5, "fetched": 5, "duplicates": 0}

    monkeypatch.setattr("synlynk.scan._detect_harnesses_on_path", lambda *a, **kw: harnesses_mock)
    monkeypatch.setattr("synlynk.backlog.ingest_backlog", lambda *a, **kw: backlog_mock)

    start = time.time()
    res = cmd_wizard_init(
        repo_dir=str(tmp_path),
        dry_run=False,
        sync_github=True,
        prompt_remediation=False,
    )
    duration = time.time() - start

    assert duration < 5.0, f"Onboarding took {duration:.2f}s, exceeding 5s target"
    assert res["elapsed_seconds"] < 5.0
    assert len(res["charters_provisioned"]) == 8
    assert set(res["charters_provisioned"]) == set(SEED_CHARTERS.keys())

    # Verify physical charter files in .synlynk/agents/
    agents_dir = tmp_path / ".synlynk" / "agents"
    assert agents_dir.exists()
    for role in SEED_CHARTERS.keys():
        charter_file = agents_dir / f"{role}.md"
        assert charter_file.exists()
        assert f"role: {role}" in charter_file.read_text()

    # Verify backlog ingest result
    assert res["backlog_ingest"]["ingested"] == 5


def test_find_top_scan_finding_hygiene_and_coverage(tmp_path):
    """find_top_scan_finding correctly flags gitignore gaps and coverage deficits."""
    # 1. Flag missing .gitignore rules
    finding = find_top_scan_finding(repo_dir=str(tmp_path))
    assert finding["category"] == "hygiene"
    assert "gitignore" in finding["id"]

    # 2. Flag test coverage deficit when gitignore is present
    (tmp_path / ".gitignore").write_text(".synlynk/backups/\n__pycache__/\n*.pyc\n.DS_Store\n")
    finding_cov = find_top_scan_finding(scan={"test_ratio": 0.1}, repo_dir=str(tmp_path))
    assert finding_cov["category"] == "testing"
    assert finding_cov["agent"] == "qa"


def test_first_win_auto_remediation_dispatch(tmp_path, monkeypatch):
    """dispatch_first_win_remediation dispatches fix with requires_gh_write=True."""
    mock_dispatch = MagicMock(return_value={"job_id": "job-first-win-123"})
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", mock_dispatch)

    res = dispatch_first_win_remediation(repo_dir=str(tmp_path))
    assert res["status"] == "dispatched"
    assert res["job_id"] == "job-first-win-123"

    mock_dispatch.assert_called_once()
    _, kwargs = mock_dispatch.call_args
    assert kwargs.get("requires_gh_write") is True
    assert kwargs.get("force_agent") is True


def test_prompt_first_win_remediation(tmp_path, monkeypatch):
    """prompt_first_win_remediation honors confirmation and skip actions."""
    mock_dispatch = MagicMock(return_value={"job_id": "job-first-win-456"})
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", mock_dispatch)

    # User confirms
    monkeypatch.setattr("builtins.input", lambda _: "y")
    confirmed_res = prompt_first_win_remediation(repo_dir=str(tmp_path), auto_confirm=False)
    assert confirmed_res["status"] == "dispatched"

    # User skips
    monkeypatch.setattr("builtins.input", lambda _: "n")
    skipped_res = prompt_first_win_remediation(repo_dir=str(tmp_path), auto_confirm=False)
    assert skipped_res["status"] == "skipped"
