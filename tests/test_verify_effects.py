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


def test_review_only_job_completes_from_cross_branch_pr_review(temp_git_repo, monkeypatch):
    """A review dispatch with an empty worktree completes from the target PR.

    #2056: the job's own branch has no commits. A review submitted after
    dispatch start on the PR named in the task is the completion evidence.
    """
    import json
    from synlynk.verify_effects import verify_job_effects

    tmpdir, base_sha = temp_git_repo
    payload = {
        "headRefName": "feat/unrelated",
        "reviews": [
            {
                "author": {"login": "someone-else"},
                "state": "COMMENTED",
                "submittedAt": "2020-01-01T00:00:00Z",
            },
            {
                "author": {"login": "synlynk-qa[bot]"},
                "state": "APPROVED",
                "submittedAt": "2099-01-01T00:00:00Z",
            },
        ],
        "commits": [],
    }
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("synlynk.gh_verify.subprocess.run", fake_run)
    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        worktree_branch="dispatch/grok/job-review",
        task_class="review",
        started_at="2026-10-06T12:00:00",
        cross_branch_pr="pr:2054",
        gh_verify_kwargs={"expect": "review_posted", "expect_author": "synlynk-qa[bot]"},
        exit_code=0,
    )

    assert seen["cmd"] == ["gh", "pr", "view", "2054", "--json", "reviews,commits,headRefName"]
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert result.gh_verified is True
    assert result.evidence.get("matched_event") == "review"


def test_cross_branch_fix_job_completes_from_fresh_commit(temp_git_repo, monkeypatch):
    """A push onto another PR completes even when this worktree diff is empty."""
    import json
    from synlynk.verify_effects import verify_job_effects

    tmpdir, base_sha = temp_git_repo
    payload = {
        "headRefName": "fix/other-pr",
        "reviews": [],
        "commits": [{"oid": "abc", "committedDate": "2099-01-01T00:00:00Z"}],
    }

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("synlynk.gh_verify.subprocess.run", fake_run)
    result = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=base_sha,
        worktree_branch="dispatch/grok/job-fix",
        task_class="mutating",
        started_at="2026-10-06T12:00:00",
        cross_branch_pr="pr:2058",
        exit_code=0,
    )
    assert result.verified is True
    assert result.status == STATUS_COMPLETED
    assert result.evidence.get("matched_event") == "commit"


def test_in_worktree_completion_does_not_query_cross_branch_pr(temp_git_repo, monkeypatch):
    """Jobs with no recorded cross-branch PR keep the local-diff completion path."""
    from synlynk.verify_effects import verify_job_effects

    def forbid_cross_branch(*args, **kwargs):
        raise AssertionError("in-worktree jobs must not query a cross-branch PR")

    monkeypatch.setattr(
        "synlynk.verify_effects.cross_branch_pr_effect_verified",
        forbid_cross_branch,
    )
    tmpdir, base_sha = temp_git_repo
    new_file = os.path.join(tmpdir, "feature.py")
    with open(new_file, "w") as handle:
        handle.write("def hello(): pass\n")
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

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmpdir, check=True, capture_output=True, text=True,
    ).stdout.strip()
    empty = verify_job_effects(
        worktree_path=tmpdir,
        base_sha=head,
        task_class="mutating",
    )
    assert empty.verified is False
    assert empty.status == STATUS_COMPLETED_WITHOUT_CHANGES


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
