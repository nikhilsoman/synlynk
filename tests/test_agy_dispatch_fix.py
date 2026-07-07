import hashlib
import os


def _job_id(agent: str, task: str, timestamp: float) -> str:
    return "job-" + hashlib.md5(f"{agent}{task}{timestamp}".encode()).hexdigest()[:8]


def test_dispatch_perjob_git_worktree_isolation_creates_branch_and_worktree(project_dir, monkeypatch):
    import synlynk as sl

    captured_run = {}

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        captured_run["cmd"] = cmd
        captured_run["kwargs"] = kwargs

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    def fake_popen(cmd, **kwargs):
        captured_run["popen"] = kwargs
        return FakeProc()

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(sl.time, "time", lambda: 1_725_000_000.123)

    job = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)
    expected_job_id = _job_id("codex", "fix bug", 1_725_000_000.123)
    expected_branch = f"dispatch/codex/{expected_job_id}"
    expected_worktree = os.path.join("worktrees", expected_job_id)

    assert captured_run["cmd"] == ["git", "worktree", "add", expected_worktree, "-b", expected_branch]
    assert captured_run["kwargs"]["cwd"] == os.getcwd()
    assert captured_run["kwargs"]["stderr"] is not None
    assert job["worktree_path"] == expected_worktree
    assert job["worktree_branch"] == expected_branch
    assert captured_run["popen"]["cwd"] == expected_worktree
    assert job["log_file"].startswith(os.path.abspath(expected_worktree))


def test_dispatch_perjob_git_worktree_isolation_uses_distinct_worktrees(project_dir, monkeypatch):
    import synlynk as sl

    created = []
    spawned = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

    def fake_run(cmd, **kwargs):
        created.append((cmd, kwargs))

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    def fake_popen(cmd, **kwargs):
        spawned.append(kwargs["cwd"])
        return FakeProc(1000 + len(spawned))

    times = iter([1_725_000_000.111, 1_725_000_000.222])
    monkeypatch.setattr(sl.time, "time", lambda: next(times))
    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)

    job_a = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)
    job_b = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    assert job_a["worktree_path"] != job_b["worktree_path"]
    assert spawned == [job_a["worktree_path"], job_b["worktree_path"]]
    assert len({job_a["worktree_branch"], job_b["worktree_branch"]}) == 2
    assert len(created) == 2


def test_dispatch_perjob_git_worktree_isolation_fails_loudly_on_worktree_error(project_dir, monkeypatch):
    import synlynk as sl

    spawned = []

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "dirty worktree"

    def fake_run(cmd, **kwargs):
        return FakeResult()

    def fake_popen(*_args, **_kwargs):
        spawned.append(True)
        raise AssertionError("Popen must not run after worktree creation fails")

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)

    try:
        sl.dispatch_agent("codex", "fix bug", skip_preflight=True)
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "Failed to create worktree" in str(exc)
        assert "dirty worktree" in str(exc)

    assert raised is True
    assert spawned == []


def test_dispatch_perjob_git_worktree_isolation_summary_includes_worktree(project_dir, capsys):
    import synlynk as sl

    text = sl._format_job_summary(
        "job-123",
        "codex",
        "story-9",
        0,
        12.4,
        100,
        20,
        0.14,
        [],
        worktree_path="worktrees/job-123",
        worktree_branch="dispatch/codex/job-123",
    )

    assert "worktree: worktrees/job-123 (branch: dispatch/codex/job-123)" in text

    sl._save_jobs([
        {
            "id": "job-123",
            "agent": "codex",
            "pid": 1,
            "status": "completed",
            "story_id": "story-9",
            "task": "task",
            "started_at": "2026-07-07T10:00:00",
            "ended_at": "2026-07-07T10:05:00",
            "exit_code": 0,
            "log_file": os.path.join(".synlynk", "logs", "job-123.log"),
            "worktree_path": "worktrees/job-123",
            "worktree_branch": "dispatch/codex/job-123",
        }
    ])
    sl._write_job_summary(
        "job-123",
        "codex",
        "story-9",
        0,
        300.0,
        100,
        20,
        0.14,
        [],
        worktree_path="worktrees/job-123",
        worktree_branch="dispatch/codex/job-123",
    )

    sl.cmd_jobs(summary="job-123")
    out = capsys.readouterr().out
    assert "worktree: worktrees/job-123 (branch: dispatch/codex/job-123)" in out
