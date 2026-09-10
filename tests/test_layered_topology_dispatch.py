"""Unit tests for Layered Topology & Dispatch Hardening (Sprint 3: #1426, #1369, #1351)."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from synlynk.dispatch import _permissions_to_flags, _CODEX_NETWORK_PERMISSION
from synlynk.jobs import (
    _daemon_job_worktree_path,
    _reap_zombie_worktree,
    _maybe_open_worktree_pr,
    _resolve_default_base_branch,
)


def test_codex_review_with_local_write_grant_uses_workspace_write():
    """Issue #1351: Codex review tasks with local write:* grants should get workspace-write."""
    # 1. Pure review (no write grants) -> read-only
    flags_ro = _permissions_to_flags("codex", ["read:*"], read_only=True)
    assert "-s" in flags_ro
    assert flags_ro[flags_ro.index("-s") + 1] == "read-only"
    assert "sandbox_workspace_write.network_access=true" not in " ".join(flags_ro)

    # 2. Review with write grant (e.g. write:project-docs or write:*) -> workspace-write without network
    flags_write = _permissions_to_flags("codex", ["read:*", "write:docs/assessments"], read_only=True)
    assert "-s" in flags_write
    assert flags_write[flags_write.index("-s") + 1] == "workspace-write"
    # Must NOT have network access enabled
    assert "sandbox_workspace_write.network_access=true" not in " ".join(flags_write)

    # 3. Review with network permission -> workspace-write with network flag
    flags_net = _permissions_to_flags("codex", ["read:*", _CODEX_NETWORK_PERMISSION], read_only=True)
    assert "-s" in flags_net
    assert flags_net[flags_net.index("-s") + 1] == "workspace-write"
    assert "sandbox_workspace_write.network_access=true" in " ".join(flags_net)


def test_nested_worktree_path_resolution_prevents_outer_deletion(tmp_path):
    """Issue #1369: _daemon_job_worktree_path must resolve innermost worktree."""
    outer_worktree = tmp_path / "worktrees" / "parent-session-wt"
    inner_worktree = outer_worktree / "worktrees" / "job-12345678"
    inner_logs = inner_worktree / ".synlynk" / "logs"
    inner_logs.mkdir(parents=True)
    log_file = inner_logs / "job-12345678.log"
    log_file.write_text("dummy log")

    resolved = _daemon_job_worktree_path("job-12345678", str(log_file))
    assert resolved == str(inner_worktree)
    assert resolved != str(outer_worktree)


def test_reap_zombie_worktree_safety_guard_rejects_parent_dir(tmp_path):
    """Issue #1369: _reap_zombie_worktree must refuse to delete directories not matching job_id."""
    parent_wt = tmp_path / "worktrees" / "parent-session-wt"
    parent_wt.mkdir(parents=True)

    with patch("synlynk.jobs._daemon_job_worktree_path", return_value=str(parent_wt)):
        reaped = _reap_zombie_worktree("job-target99", str(parent_wt / "log.log"))
        assert reaped is False
        assert parent_wt.exists()


def test_maybe_open_worktree_pr_skips_when_no_diff_or_skip_phrases():
    """Issue #1426: Auto-PR creation must be skipped for zero-diff or explicit push-to-branch instructions."""
    job_no_diff = {
        "id": "job-111",
        "task": "do work",
        "task_type": "default",
        "requires_gh_write": False,
        "base_branch": "feat/existing",
    }
    with patch("synlynk.jobs._worktree_has_no_diff_against_base_branch", return_value=True), \
         patch("synlynk.jobs._pkg", return_value=lambda: ("owner", "repo")):
        # Zero-diff must skip
        pr_num = _maybe_open_worktree_pr(job_no_diff, "/dummy/path", "dispatch/codex/job-111")
        assert pr_num is None

    job_skip_phrase = {
        "id": "job-222",
        "task": "Fix bug and push to the existing feat/existing branch -- do not start a separate pull request",
        "task_type": "default",
        "requires_gh_write": True,
        "base_branch": "feat/existing",
    }
    with patch("synlynk.jobs._worktree_has_no_diff_against_base_branch", return_value=False), \
         patch("synlynk.jobs._pkg", return_value=lambda: ("owner", "repo")):
        pr_num2 = _maybe_open_worktree_pr(job_skip_phrase, "/dummy/path", "dispatch/codex/job-222")
        assert pr_num2 is None


def test_resolve_default_base_branch_prefers_unstable(tmp_path):
    """Layered release protocol: default base branch resolution checks unstable."""
    with patch("synlynk.jobs._worktree_path_is_available", return_value=True):
        def _mock_run(cmd, *args, **kwargs):
            ref = cmd[-1]
            if ref == "refs/remotes/origin/HEAD":
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
            if ref == "origin/unstable":
                return subprocess.CompletedProcess(cmd, 0, stdout="sha123\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=_mock_run):
            base = _resolve_default_base_branch(str(tmp_path))
            assert base == "unstable"
