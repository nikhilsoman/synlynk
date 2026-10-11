import subprocess


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _job_worktree(repo, name="dispatch/codex/noop"):
    path = repo / "worktrees" / name.rsplit("/", 1)[-1]
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", name, str(path), "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return path


def test_noop_job_removes_clean_worktree_and_branch(git_worktree_repo):
    import synlynk.jobs as jobs

    repo = git_worktree_repo
    path = _job_worktree(repo)
    job = {"id": "job-noop", "worktree_path": str(path), "worktree_branch": "dispatch/codex/noop"}

    assert jobs._cleanup_noop_worktree(job) is True
    assert not path.exists()
    assert subprocess.run(
        ["git", "-C", str(repo), "show-ref", "--verify", "refs/heads/dispatch/codex/noop"],
        capture_output=True,
    ).returncode != 0


def test_completed_noop_job_calls_worktree_cleanup(monkeypatch):
    import synlynk.jobs as jobs

    calls = []
    monkeypatch.setattr(jobs, "_cleanup_noop_worktree", lambda job: calls.append(job))
    monkeypatch.setattr(jobs, "_job_has_real_work_landed", lambda state: False)

    jobs._finalize_completed_worktree_job({"id": "job-noop"}, {"dirty": False})

    assert calls == [{"id": "job-noop"}]


def test_noop_cleanup_keeps_dirty_worktree(git_worktree_repo):
    import synlynk.jobs as jobs

    repo = git_worktree_repo
    path = _job_worktree(repo)
    (path / "untracked.txt").write_text("keep me")
    job = {"id": "job-dirty", "worktree_path": str(path), "worktree_branch": "dispatch/codex/noop"}

    assert jobs._cleanup_noop_worktree(job) is False
    assert path.exists()
    assert _git(repo, "show-ref", "--verify", "refs/heads/dispatch/codex/noop").returncode == 0


def test_noop_cleanup_keeps_branch_with_diff_from_origin_main(git_worktree_repo):
    import synlynk.jobs as jobs

    repo = git_worktree_repo
    path = _job_worktree(repo)
    (path / "change.txt").write_text("committed change")
    _git(path, "add", "change.txt")
    _git(path, "commit", "-m", "change")
    job = {"id": "job-diff", "worktree_path": str(path), "worktree_branch": "dispatch/codex/noop"}

    assert jobs._cleanup_noop_worktree(job) is False
    assert path.exists()
    assert _git(repo, "show-ref", "--verify", "refs/heads/dispatch/codex/noop").returncode == 0
