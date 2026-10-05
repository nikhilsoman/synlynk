"""Unit tests for Pure Effect Verification Engine (Invariant 1)."""

import os
import subprocess
import sys
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.jobs import (
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITHOUT_CHANGES,
    STATUS_FAILED_NOOP_DENIED,
    STATUS_FAILED_VERIFICATION,
)


@pytest.fixture
def temp_git_repo():
    """Creates a temporary git repo with an initial commit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@synlynk.dev"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.name", "Test Committer"], cwd=tmpdir, check=True)
        
        # Initial commit
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Initial\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmpdir, check=True, capture_output=True)
        
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmpdir, check=True, capture_output=True, text=True)
        base_sha = res.stdout.strip()
        yield tmpdir, base_sha


def test_mutating_task_with_empty_diff_returns_completed_without_changes(temp_git_repo):
    from synlynk.verify_effects import verify_job_effects, EffectVerificationResult
    tmpdir, base_sha = temp_git_repo

    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        task_class="mutating",
    )
    assert isinstance(result, EffectVerificationResult)
    assert result.verified is False
    assert result.status == STATUS_COMPLETED_WITHOUT_CHANGES
    assert result.files_touched == []
    assert "zero files touched" in result.reason.lower() or "zero git diff" in result.reason.lower()


def test_mutating_task_with_committed_changes_returns_completed(temp_git_repo):
    from synlynk.verify_effects import verify_job_effects
    tmpdir, base_sha = temp_git_repo

    # Add a new committed file
    new_file = os.path.join(tmpdir, "feature.py")
    with open(new_file, "w") as f:
        f.write("def hello(): pass\n")
    subprocess.run(["git", "add", "feature.py"], cwd=tmpdir, check=True)
    subprocess.run(["git", "commit", "-m", "feat: add feature"], cwd=tmpdir, check=True, capture_output=True)

    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        task_class="mutating",
    )
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert "feature.py" in result.files_touched


def test_mutating_task_with_uncommitted_working_tree_changes_returns_completed(temp_git_repo):
    from synlynk.verify_effects import verify_job_effects
    tmpdir, base_sha = temp_git_repo

    # Add an uncommitted file
    new_file = os.path.join(tmpdir, "scratch.txt")
    with open(new_file, "w") as f:
        f.write("working tree change\n")

    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        task_class="mutating",
    )
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert "scratch.txt" in result.files_touched


def test_gh_write_task_unverified_returns_failed_noop_denied():
    from synlynk.verify_effects import verify_job_effects

    with patch("synlynk.verify_effects.gh_write_verified", return_value=False):
        result = verify_job_effects(
            task_class="gh_write",
            expected_gh_effect="review_posted",
            gh_verify_kwargs={"target": "pr:100", "expect_author": "qa"},
        )
        assert result.verified is False
        assert result.status == STATUS_FAILED_NOOP_DENIED
        assert result.gh_verified is False


def test_gh_write_task_verified_returns_completed():
    from synlynk.verify_effects import verify_job_effects

    with patch("synlynk.verify_effects.gh_write_verified", return_value=True):
        result = verify_job_effects(
            task_class="gh_write",
            expected_gh_effect="comment_posted",
            gh_verify_kwargs={"target": "issue:100"},
        )
        assert result.verified is True
        assert result.status == STATUS_COMPLETED
        assert result.gh_verified is True


def test_mutating_task_accepts_github_pr_when_merged_branch_is_gone(monkeypatch):
    from synlynk.verify_effects import verify_job_effects

    monkeypatch.setattr("synlynk.verify_effects.local_commits_pushed", lambda *args: False)
    monkeypatch.setattr(
        "synlynk.verify_effects.github_branch_effect_verified",
        lambda *args, **kwargs: True,
    )

    result = verify_job_effects(
        task_class="mutating",
        worktree_branch="fix/job-merged",
        base_sha="base-sha",
        git_state={"commits_ahead": 1},
        started_at="2026-10-04T09:00:00",
    )

    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert "GitHub PR exists" in result.reason


def test_mutating_task_still_rejects_unpushed_branch_without_github_effect(monkeypatch, tmp_path):
    from synlynk.verify_effects import verify_job_effects

    monkeypatch.setattr("synlynk.verify_effects.local_commits_pushed", lambda *args: False)
    monkeypatch.setattr(
        "synlynk.verify_effects.github_branch_effect_verified",
        lambda *args, **kwargs: False,
    )

    result = verify_job_effects(
        task_class="mutating",
        worktree_path=str(tmp_path),
        worktree_branch="fix/job-unpushed",
        base_sha="base-sha",
        git_state={"commits_ahead": 1},
    )

    assert result.verified is False
    assert result.status == "unpushed_branch"


def test_analysis_task_receipt_verification(tmp_path):
    from synlynk.verify_effects import verify_job_effects

    receipt_file = str(tmp_path / "receipt.json")
    with open(receipt_file, "w") as f:
        f.write('{"ok": true}')

    # Present receipt
    res_ok = verify_job_effects(
        task_class="analysis",
        receipt_path=receipt_file,
    )
    assert res_ok.verified is True
    assert res_ok.status == STATUS_COMPLETED

    # Missing receipt
    res_missing = verify_job_effects(
        task_class="analysis",
        receipt_path=str(tmp_path / "non_existent.json"),
    )
    assert res_missing.verified is False
    assert res_missing.status == STATUS_COMPLETED_WITHOUT_CHANGES


def test_verification_cmd_failure_returns_failed_verification(temp_git_repo):
    from synlynk.verify_effects import verify_job_effects
    tmpdir, base_sha = temp_git_repo

    # Add change so diff passes
    new_file = os.path.join(tmpdir, "fix.py")
    with open(new_file, "w") as f:
        f.write("x = 1\n")

    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        task_class="mutating",
        verification_cmd="python3 -c 'import sys; sys.exit(1)'",
    )
    assert result.verified is False
    assert result.status == STATUS_FAILED_VERIFICATION
    assert result.tests_passed is False


def test_verification_cmd_success_returns_completed(temp_git_repo):
    from synlynk.verify_effects import verify_job_effects
    tmpdir, base_sha = temp_git_repo

    # Add change so diff passes
    new_file = os.path.join(tmpdir, "fix.py")
    with open(new_file, "w") as f:
        f.write("x = 1\n")

    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        task_class="mutating",
        verification_cmd="python3 -c 'import sys; sys.exit(0)'",
    )
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert result.tests_passed is True


def test_structured_completion_overrides_nonzero_wrapper_exit():
    from synlynk.verify_effects import verify_job_effects

    result = verify_job_effects(
        task_class="analysis",
        exit_code=17,
        structured_telemetry={"available": True, "completed": True},
    )
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
