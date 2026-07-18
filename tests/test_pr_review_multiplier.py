import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_maybe_open_worktree_pr_returns_pr_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess

    from synlynk import jobs as jobs_mod

    def fake_run(cmd, **kwargs):
        class FakeResult:
            pass

        result = FakeResult()
        if cmd[:3] == ["gh", "pr", "list"]:
            result.returncode = 0
            result.stdout = "[]"
            result.stderr = ""
        elif cmd[:3] == ["gh", "pr", "create"]:
            result.returncode = 0
            result.stdout = "https://github.com/owner/repo/pull/42\n"
            result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("owner", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    job = {"id": "job-1", "task": "test task"}
    pr_number = jobs_mod._maybe_open_worktree_pr(job, "/fake/worktree", "feat/test-branch")
    assert pr_number == 42
