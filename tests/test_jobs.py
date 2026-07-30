import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_dispatch_ready_jobs_prints_fence_when_schedule_allowlisted(monkeypatch, capsys):
    from synlynk.fencing import FenceData
    from synlynk.jobs import _dispatch_ready_jobs

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, "
        "story_id TEXT, depends_on TEXT, log_path TEXT, priority INTEGER, "
        "enqueued_at TEXT, status TEXT, pid INTEGER, started_at TEXT, completed_at TEXT)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, depends_on, log_path, "
        "priority, enqueued_at, status) VALUES "
        "('job-abc123', 'codex', 'do the thing', 'story-x', '[]', '/tmp/x-log', 1, "
        "'2026-07-17T00:00:00', 'queued')"
    )
    conn.commit()

    fake_job = {
        "id": "job-abc123",
        "pid": 999,
        "started_at": "2026-07-17T00:00:00",
        "log_file": "/tmp/x-log",
        "fence": FenceData(
            command="schedule",
            kind="estimate",
            in_tokens=100,
            out_tokens=50,
            cost_usd=0.01,
            basis="prompt_estimate",
        ),
    }

    import synlynk.jobs as jobs_mod
    from synlynk.fencing import render_task_fence

    def pkg_side_effect(name, default=None):
        if name == "_get_db":
            return lambda: conn
        if name == "dispatch_agent":
            return lambda *a, **k: fake_job
        if name == "render_task_fence":
            return render_task_fence
        return default

    monkeypatch.setattr(jobs_mod, "_pkg", pkg_side_effect)

    launched = _dispatch_ready_jobs(max_parallel=4)

    assert launched == 1
    out = capsys.readouterr().out
    assert "schedule" in out
    assert "$0.01" in out


def test_write_job_summary_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-123",
        "claude",
        "story-9",
        0,
        12.4,
        42100,
        3200,
        0.14,
        [],
    )

    summary_path = tmp_path / ".synlynk" / "logs" / "job-123.summary"
    assert summary_path.exists()
    assert summary_path.read_text() == text


def test_write_job_summary_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-abc",
        "agy",
        "story-42",
        0,
        3.0,
        1000,
        250,
        0.03,
        ["src/app.py", "tests/test_app.py"],
    )

    assert "agent:    agy   story: story-42" in text
    assert "status:   OK (exit 0)" in text
    assert "duration: 3.0s" in text
    assert "cost:   $0.03  (1,000 in / 250 out, structured_output)" in text


def test_write_job_summary_failed_job(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    text = synlynk._write_job_summary(
        "job-fail",
        "codex",
        None,
        1,
        8.0,
        0,
        0,
        0.0,
        [],
    )

    assert "status:   FAILED (exit 1)" in text


def test_cmd_jobs_summary_flag_reads_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    summary_text = synlynk._write_job_summary(
        "job-read",
        "claude",
        "story-1",
        0,
        2.5,
        10,
        20,
        0.01,
        [],
    )

    synlynk.cmd_jobs(summary="job-read")
    out = capsys.readouterr().out
    assert out == summary_text


def test_cmd_jobs_summary_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    synlynk.cmd_jobs(summary="nonexistent")
    out = capsys.readouterr().out
    assert "No summary for nonexistent -- job may still be running or predates this feature" in out


def test_reconcile_jobs_writes_and_prints_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 42\nOutput tokens: 3200\n")
    (log_path.parent / "job-run.log.exit").write_text("0")

    jobs = [{
        "id": "job-run",
        "agent": "claude",
        "story_id": "story-7",
        "task": "task",
        "pid": 99999999,
        "log_file": str(log_path),
        "started_at": "2026-07-03T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
    }]
    synlynk._save_jobs(jobs)

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    assert "-- job job-run complete ---------" in out
    assert "status:   OK (exit 0)" in out
    summary_path = tmp_path / ".synlynk" / "logs" / "job-run.summary"
    assert summary_path.exists()


def test_reconcile_jobs_marks_permission_denied_headless_auto_denial(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-denied.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "jetski: no output produced - a tool required the \"command\" permission that headless mode cannot prompt for, so it was auto-denied\n"
        '{"conversation_id":"job-a59f065a","status":"SUCCESS","response":"","duration_seconds":149,"num_turns":1,"usage":{"input_tokens":10,"output_tokens":0}}\n'
        "postscript: cleanup complete\n"
    )
    (log_path.parent / "job-denied.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-denied",
            "agent": "agy",
            "story_id": "story-denied",
            "task": "review the PR",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-07-19T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    synlynk.cmd_jobs(all_jobs=True)
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-denied")

    assert reconciled["status"] == "permission_denied"
    assert "PERMISSION_DENIED" in out
    assert "OK (exit 0)" not in out


def test_apply_dispatch_gate_downgrades_status_on_suite_failure(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    config_path = ".synlynk/config.json"
    import json
    with open(config_path, "w") as f:
        json.dump({"dispatch": {"gate_suite_cmd": "pytest tests/ -q"}}, f)

    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_run_dispatch_gate": lambda job, cmd: {"passed": 3, "failed": 2, "skipped": 0},
        }.get(name, default),
    )

    job = {"id": "job-gate1", "status": "completed", "worktree_path": "worktrees/job-gate1"}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "needs_fix"
    assert job["suite_result"]["failed"] == 2


def test_apply_dispatch_gate_leaves_status_completed_when_no_gate_configured(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    monkeypatch.setattr(jobs_mod, "_pkg", lambda name, default=None: {"load_config": sl.load_config}.get(name, default))

    job = {"id": "job-gate2", "status": "completed", "worktree_path": "worktrees/job-gate2"}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "completed"
    assert job.get("suite_result") is None


def test_apply_dispatch_gate_flags_stale_base(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_check_dispatch_base_still_fresh": lambda job: False,
        }.get(name, default),
    )

    job = {
        "id": "job-stale1", "status": "completed",
        "worktree_path": "worktrees/job-stale1",
        "base_branch": "feat/example", "base_sha": "abc123",
    }
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "stale_base"


def test_apply_dispatch_gate_end_to_end_with_real_failing_suite(git_worktree_repo, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod
    import synlynk.dispatch as dispatch_mod
    import synlynk as sl
    import json
    import os
    import subprocess

    tests_dir = os.path.join(str(git_worktree_repo), "tests")
    os.makedirs(tests_dir, exist_ok=True)
    with open(os.path.join(tests_dir, "test_deliberate_failure.py"), "w") as f:
        f.write("def test_deliberately_fails():\n    assert 1 == 2\n")
    subprocess.run(["git", "add", "."], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "seed failing test"], cwd=git_worktree_repo, capture_output=True, check=True)

    config_path = os.path.join(str(git_worktree_repo), ".synlynk", "config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"dispatch": {"gate_suite_cmd": "python3 -m pytest tests/ -q"}}, f)

    monkeypatch.chdir(git_worktree_repo)
    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_run_dispatch_gate": dispatch_mod._run_dispatch_gate,
        }.get(name, default),
    )

    job = {"id": "job-realgate", "status": "completed", "worktree_path": str(git_worktree_repo)}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "needs_fix"
    assert job["suite_result"]["failed"] >= 1


@pytest.mark.parametrize(
    "available_refs, expected_base",
    [
        ({"origin/main"}, "main"),
        ({"origin/master"}, "master"),
    ],
)
def test_resolve_default_base_branch_prefers_origin_head_then_fallbacks(
    tmp_path, monkeypatch, available_refs, expected_base
):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()

    def fake_run(cmd, **kwargs):
        if cmd[:4] == ["git", "-C", str(worktree_path), "symbolic-ref"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:5] == ["git", "-C", str(worktree_path), "rev-parse", "--verify"]:
            candidate = cmd[5]
            if candidate in available_refs:
                return subprocess.CompletedProcess(cmd, 0, stdout="deadbeef\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)

    assert jobs_mod._resolve_default_base_branch(str(worktree_path)) == expected_base


def test_maybe_open_worktree_pr_uses_resolved_base_branch(tmp_path, monkeypatch):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    captured = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        if cmd[:4] == ["git", "-C", str(worktree_path), "symbolic-ref"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:5] == ["git", "-C", str(worktree_path), "rev-parse", "--verify"]:
            candidate = cmd[5]
            if candidate == "origin/master":
                return subprocess.CompletedProcess(cmd, 0, stdout="deadbeef\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/octo/repo/pull/42\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("octo", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {"id": "job-1", "task": "do the thing"},
        str(worktree_path),
        "feat/example",
    )

    assert pr_number == 42
    create_call = next(cmd for cmd in captured if cmd[:3] == ["gh", "pr", "create"])
    assert "--base" in create_call
    assert create_call[create_call.index("--base") + 1] == "master"
