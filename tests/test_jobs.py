import os
import sys
import sqlite3
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_check_scope_compliance_all_files_match_single_glob():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "docs/superpowers/specs/bar.md"],
        ["docs/superpowers/specs/*"],
    ) is True


def test_check_scope_compliance_files_match_any_of_several_globs():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "docs/blog/README.md"],
        ["docs/superpowers/specs/*", "docs/blog/*"],
    ) is True


def test_check_scope_compliance_file_matching_no_glob_is_violation():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(
        ["docs/superpowers/specs/foo.md", "synlynk/jobs.py"],
        ["docs/superpowers/specs/*"],
    ) is False


def test_check_scope_compliance_empty_scope_paths_is_always_compliant():
    from synlynk.jobs import _check_scope_compliance

    assert _check_scope_compliance(["synlynk/jobs.py"], []) is True
    assert _check_scope_compliance(["synlynk/jobs.py"], None) is True


def test_check_task_receipt_ok_when_marker_is_first_line():
    import synlynk.jobs as jobs_mod

    log_text = "SYNLYNK_TASK_RECEIVED: abc123\nsome work happened\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "ok"


def test_check_task_receipt_late_when_marker_present_but_not_first():
    import synlynk.jobs as jobs_mod

    log_text = "starting work\nSYNLYNK_TASK_RECEIVED: abc123\nmore work\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "late"


def test_check_task_receipt_mismatch_when_first_line_wrong_digest():
    import synlynk.jobs as jobs_mod

    log_text = "SYNLYNK_TASK_RECEIVED: wrongdigest\nsome work\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "mismatch"


def test_check_task_receipt_absent_when_no_marker_anywhere():
    import synlynk.jobs as jobs_mod

    log_text = "just did the work with no marker at all\n"
    assert jobs_mod._check_task_receipt(log_text, "abc123") == "absent"


def test_check_task_receipt_returns_none_for_empty_log_or_digest():
    import synlynk.jobs as jobs_mod

    assert jobs_mod._check_task_receipt("", "abc123") is None
    assert jobs_mod._check_task_receipt("some log", None) is None


def test_classify_task_delivery_hard_fail_when_no_marker_and_no_activity():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("absent", has_corroborating_activity=False)
    assert result == {"hard_fail": True, "warn": False}


def test_classify_task_delivery_warn_when_no_marker_but_activity_present():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("mismatch", has_corroborating_activity=True)
    assert result == {"hard_fail": False, "warn": True}


def test_classify_task_delivery_clean_when_receipt_ok():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery("ok", has_corroborating_activity=False)
    assert result == {"hard_fail": False, "warn": False}


def test_classify_task_delivery_clean_when_receipt_status_none():
    import synlynk.jobs as jobs_mod

    result = jobs_mod._classify_task_delivery(None, has_corroborating_activity=False)
    assert result == {"hard_fail": False, "warn": False}


def test_task_sha256_and_preview_returns_none_for_falsy_task():
    from synlynk.jobs import _task_sha256_and_preview

    assert _task_sha256_and_preview(None) == (None, None)
    assert _task_sha256_and_preview("") == (None, None)


def test_task_sha256_and_preview_computes_digest_and_collapses_whitespace():
    from synlynk.jobs import _task_sha256_and_preview
    import hashlib

    task = "line one\n  line two   with   spaces\nline three"
    task_sha256, task_preview = _task_sha256_and_preview(task)

    assert task_sha256 == hashlib.sha256(task.encode("utf-8")).hexdigest()
    assert task_preview == "line one line two with spaces line three"
    assert "\n" not in task_preview


def test_inspect_worktree_git_state_includes_changed_files_from_diff_and_status(tmp_path, monkeypatch):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    prefix = ["git", "-C", str(worktree_path)]

    def fake_run(cmd, **kwargs):
        cmd = list(cmd)
        if cmd == prefix + ["status", "--short"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M synlynk/jobs.py\n", stderr="")
        if cmd == prefix + ["rev-list", "--count", "deadbeef..HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="1\n", stderr="")
        if cmd == prefix + ["diff", "--name-only", "deadbeef..HEAD"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="docs/superpowers/specs/foo.md\n", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: (
            lambda wt: {"base_commit": "deadbeef", "base_ref": "origin/main"}
        ) if name == "_resolve_worktree_base_commit" else default,
    )

    git_state = jobs_mod._inspect_worktree_git_state(str(worktree_path), "feat/x", "2026-08-07T00:00:00")

    assert git_state["changed_files"] == ["docs/superpowers/specs/foo.md", "synlynk/jobs.py"]


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


def test_dispatch_ready_jobs_stays_queued_when_all_exhausted(project_dir, monkeypatch):
    import synlynk as sl

    conn = sl._get_db()
    sl._upsert_agent_quota(
        "codex", "5h", limit_tokens=1_000, used_tokens=1_000, unit="tokens", conn=conn
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, "
        "phase, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-exh1", "Exhaustion test", "backend", "platform", "ott", "build", 5_000),
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, enqueued_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("job-exh1", "codex", "task", "story-exh1", "queued", 5, "[]", "2026-08-08T00:00:00"),
    )
    conn.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dispatch_agent must not be called when all candidates exhausted")

    monkeypatch.setattr(sl, "dispatch_agent", fail_if_called)

    launched = sl._dispatch_ready_jobs(max_parallel=4)

    assert launched == 0
    status = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-exh1'"
    ).fetchone()[0]
    assert status == "queued"


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
        "task": None,
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


def test_reconcile_jobs_summary_includes_task_sha256_matching_local_computation(tmp_path, monkeypatch, capsys):
    import hashlib

    monkeypatch.chdir(tmp_path)
    import synlynk

    task_text = "Fix issue #720 fail-closed on empty tasks"
    expected_digest = hashlib.sha256(task_text.encode("utf-8")).hexdigest()

    log_path = tmp_path / ".synlynk" / "logs" / "job-720test.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 42\nOutput tokens: 3200\n")
    (log_path.parent / "job-720test.log.exit").write_text("0")

    jobs = [{
        "id": "job-720test",
        "agent": "codex",
        "story_id": "story-720",
        "task": task_text,
        "pid": 99999999,
        "log_file": str(log_path),
        "started_at": "2026-08-07T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
    }]
    synlynk._save_jobs(jobs)

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    synlynk._reconcile_jobs()
    capsys.readouterr()

    summary_path = tmp_path / ".synlynk" / "logs" / "job-720test.summary"
    with open(summary_path) as f:
        summary_text = f.read()

    assert f"task_sha256: {expected_digest}" in summary_text
    assert "task:     Fix issue #720 fail-closed on empty tasks" in summary_text


def test_reconcile_jobs_marks_task_delivery_failed_when_marker_absent_and_no_activity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-noreceipt.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("did some stuff without printing the receipt marker\n")
    (log_path.parent / "job-noreceipt.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-noreceipt",
            "agent": "claude",
            "story_id": "story-noreceipt",
            "task": "implement the thing",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-08-07T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "waitpid", lambda pid, opts: (pid, 0))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-noreceipt")

    assert reconciled["status"] == "task_delivery_failed"
    assert "TASK_DELIVERY_FAILED" in out


def test_reconcile_jobs_orphaned_story_cost_does_not_abort(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-orphan.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 1\nOutput tokens: 1\n")
    old = time.time() - 3600
    os.utime(log_path, (old, old))
    synlynk._save_jobs([{
        "id": "job-orphan",
        "agent": "claude",
        "story_id": "story-missing",
        "task": "stalled task",
        "pid": 99999999,
        "log_file": str(log_path),
        "started_at": "2026-07-03T01:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
    }])
    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(
        synlynk,
        "update_costs",
        lambda *a, **kw: (_ for _ in ()).throw(sqlite3.IntegrityError("FOREIGN KEY constraint failed")),
    )

    synlynk._reconcile_jobs()

    job = synlynk._load_jobs()[0]
    assert job["status"] == "failed"
    assert "job-orphan" in (tmp_path / ".synlynk" / "sentinel.md").read_text()
    assert "story-missing" in (tmp_path / ".synlynk" / "sentinel.md").read_text()


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


def test_reconcile_jobs_waitpid_ignores_denial_shape_when_log_shows_earlier_tool_use(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-waitpid-corroborated.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit",'
        '"input":{"file_path":"a.py"}}]}}\n'
        '{"conversation_id":"job-waitpid-corroborated","status":"SUCCESS","response":"",'
        '"duration_seconds":1,"num_turns":1,"usage":{"input_tokens":1,"output_tokens":0}}\n'
    )

    synlynk._save_jobs([
        {
            "id": "job-waitpid-corroborated",
            "agent": "agy",
            "story_id": "story-waitpid-corroborated",
            "task": "review the PR",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-08-07T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    def fake_waitpid(pid, opts):
        return (pid, 0)

    monkeypatch.setattr(synlynk.os, "waitpid", fake_waitpid)

    synlynk._reconcile_jobs()

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-waitpid-corroborated")

    assert reconciled["status"] != "permission_denied"


def test_reconcile_jobs_waitpid_ignores_denial_shape_when_git_state_shows_activity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import subprocess
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "_inspect_worktree_git_state", jobs_mod._inspect_worktree_git_state)

    worktree = tmp_path / "wt-waitpid"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "t"], check=True)
    (worktree / "README.md").write_text("hello")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-q", "-b", "work"], check=True)
    (worktree / "feature.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "real work"], check=True)

    log_path = tmp_path / ".synlynk" / "logs" / "job-waitpid-git-corroborated.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "jetski: no output produced - a tool required the \"command\" permission that "
        "headless mode cannot prompt for, so it was auto-denied\n"
    )

    synlynk._save_jobs([
        {
            "id": "job-waitpid-git-corroborated",
            "agent": "grok",
            "story_id": "story-waitpid-git-corroborated",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": str(worktree),
            "worktree_branch": "dispatch/grok/job-waitpid-git-corroborated",
            "started_at": "2026-08-07T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    def fake_waitpid(pid, opts):
        return (pid, 0)

    monkeypatch.setattr(synlynk.os, "waitpid", fake_waitpid)

    synlynk._reconcile_jobs()

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-waitpid-git-corroborated")

    assert reconciled["status"] != "permission_denied"
    assert reconciled["status"] == "completed"


def test_reconcile_jobs_dead_pid_ignores_denial_shape_when_git_state_shows_activity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import subprocess
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "_inspect_worktree_git_state", jobs_mod._inspect_worktree_git_state)

    worktree = tmp_path / "wt-deadpid"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "t"], check=True)
    (worktree / "README.md").write_text("hello")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-q", "-b", "work"], check=True)
    (worktree / "feature.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "real work"], check=True)

    log_path = tmp_path / ".synlynk" / "logs" / "job-deadpid-git-corroborated.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "jetski: no output produced - a tool required the \"command\" permission that "
        "headless mode cannot prompt for, so it was auto-denied\n"
    )
    (log_path.parent / "job-deadpid-git-corroborated.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-deadpid-git-corroborated",
            "agent": "grok",
            "story_id": "story-deadpid-git-corroborated",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": str(worktree),
            "worktree_branch": "dispatch/grok/job-deadpid-git-corroborated",
            "started_at": "2026-08-07T18:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-deadpid-git-corroborated")

    assert reconciled["status"] != "permission_denied"


def test_reconcile_jobs_dead_pid_marks_task_delivery_failed_when_marker_absent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import synlynk

    log_path = tmp_path / ".synlynk" / "logs" / "job-deadpid-noreceipt.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("worked on it, no receipt marker anywhere\n")
    (log_path.parent / "job-deadpid-noreceipt.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-deadpid-noreceipt",
            "agent": "grok",
            "story_id": "story-deadpid",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "started_at": "2026-08-07T19:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-deadpid-noreceipt")

    assert reconciled["status"] == "task_delivery_failed"
    assert "TASK_DELIVERY_FAILED" in out


def test_reconcile_jobs_dead_pid_warns_but_does_not_fail_when_activity_present(tmp_path, monkeypatch, capsys, git_worktree_repo):
    monkeypatch.chdir(tmp_path)
    import subprocess
    import synlynk

    worktree = tmp_path / "wt"
    worktree.mkdir()
    subprocess.run(["git", "init", "-q", str(worktree)], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(worktree), "config", "user.name", "t"], check=True)
    (worktree / "README.md").write_text("hello")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(worktree), "checkout", "-q", "-b", "work"], check=True)
    (worktree / "feature.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "real work"], check=True)

    log_path = tmp_path / ".synlynk" / "logs" / "job-deadpid-warn.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("did real work but forgot the receipt marker\n")
    (log_path.parent / "job-deadpid-warn.log.exit").write_text("0")

    synlynk._save_jobs([
        {
            "id": "job-deadpid-warn",
            "agent": "grok",
            "story_id": "story-warn",
            "task": "wire the canvas renderer",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": str(worktree),
            "worktree_branch": "dispatch/grok/job-deadpid-warn",
            "started_at": "2026-08-07T19:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    monkeypatch.setattr(synlynk.os, "kill", lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()))

    synlynk._reconcile_jobs()
    out = capsys.readouterr().out

    jobs = synlynk._load_jobs()
    reconciled = next(job for job in jobs if job["id"] == "job-deadpid-warn")

    assert reconciled["status"] != "task_delivery_failed"
    assert "task-receipt" in out


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


# --- #753 jobs reap -----------------------------------------------------------

def _seed_daemon_job(conn, job_id, agent="agy", status="running", pid=None, started_at="2026-08-07T07:00:00"):
    conn.execute(
        "INSERT OR REPLACE INTO daemon_jobs "
        "(job_id, agent, task, story_id, status, priority, depends_on, pid, enqueued_at, started_at, "
        " completed_at, exit_code, log_path, handoff_count) "
        "VALUES (?, ?, 'task', NULL, ?, 5, '[]', ?, ?, ?, NULL, NULL, NULL, 0)",
        (job_id, agent, status, pid, started_at, started_at),
    )
    conn.commit()


def test_pid_is_alive_null_and_dead(monkeypatch):
    from synlynk.jobs import _pid_is_alive

    assert _pid_is_alive(None) is False
    assert _pid_is_alive("not-a-pid") is False

    def boom(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr("os.kill", boom)
    assert _pid_is_alive(12345) is False


def test_pid_is_alive_permission_treated_alive(monkeypatch):
    from synlynk.jobs import _pid_is_alive

    def denied(pid, sig):
        raise PermissionError()

    monkeypatch.setattr("os.kill", denied)
    assert _pid_is_alive(999) is True


def test_mark_daemon_job_terminal_only_running(project_dir):
    from synlynk import _get_db
    from synlynk.jobs import mark_daemon_job_terminal

    conn = _get_db()
    _seed_daemon_job(conn, "job-dead0001", pid=1)
    _seed_daemon_job(conn, "job-done0001", status="done", pid=2)
    assert mark_daemon_job_terminal(conn, "job-dead0001") is True
    assert mark_daemon_job_terminal(conn, "job-done0001") is False
    conn.commit()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id='job-dead0001'"
    ).fetchone()
    assert row[0] == "timed_out"
    assert row[1] == -9
    conn.close()


def test_reconcile_releases_reservation_on_settlement(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    conn = sl._get_db()
    rid = sl._open_reservation(
        conn, "codex", 4_000, scope="adhoc", job_id="job-settle1"
    )
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at) "
        "VALUES ('job-settle1', 'codex', 'task', 'running', 999999, "
        "'2026-08-08T00:00:00', '2026-08-08T00:00:00')"
    )
    conn.commit()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    status = conn.execute(
        "SELECT status FROM agent_reservations WHERE id=?", (rid,)
    ).fetchone()[0]
    assert status == "released"


def test_scan_and_apply_reap_zombies(tmp_path, monkeypatch):
    from synlynk.jobs import scan_zombie_running_jobs, apply_reap_zombies
    import sqlite3

    db = tmp_path / "state.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE daemon_jobs ("
        "job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, status TEXT, "
        "priority INTEGER, depends_on TEXT, pid INTEGER, enqueued_at TEXT, started_at TEXT, "
        "completed_at TEXT, exit_code INTEGER, log_path TEXT, handoff_count INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs VALUES "
        "('job-z1','agy','t',NULL,'running',5,'[]',111,'2026-08-01T00:00:00','2026-08-01T00:00:00',NULL,NULL,NULL,0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs VALUES "
        "('job-z2','claude','t',NULL,'running',5,'[]',222,'2026-08-01T00:00:00','2026-08-01T00:00:00',NULL,NULL,NULL,0)"
    )
    conn.commit()
    conn.close()

    def fake_kill(pid, sig):
        if int(pid) == 111:
            raise ProcessLookupError()
        # 222 alive

    monkeypatch.setattr("os.kill", fake_kill)
    cands = scan_zombie_running_jobs(str(db))
    by_id = {c["job_id"]: c for c in cands}
    assert by_id["job-z1"]["action"] == "reap"
    assert by_id["job-z2"]["action"] == "keep"

    reaped = apply_reap_zombies(cands)
    assert len(reaped) == 1
    assert reaped[0]["job_id"] == "job-z1"
    conn = sqlite3.connect(str(db))
    rows = {
        r[0]: (r[1], r[2])
        for r in conn.execute("SELECT job_id, status, exit_code FROM daemon_jobs")
    }
    assert rows["job-z1"] == ("timed_out", -9)
    assert rows["job-z2"][0] == "running"
    conn.close()


def test_cmd_jobs_reap_dry_run_and_apply(tmp_path, monkeypatch, capsys):
    from synlynk.jobs import cmd_jobs_reap
    import sqlite3

    db = tmp_path / "proj" / "state.db"
    db.parent.mkdir()
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE daemon_jobs ("
        "job_id TEXT PRIMARY KEY, agent TEXT, task TEXT, story_id TEXT, status TEXT, "
        "priority INTEGER, depends_on TEXT, pid INTEGER, enqueued_at TEXT, started_at TEXT, "
        "completed_at TEXT, exit_code INTEGER, log_path TEXT, handoff_count INTEGER DEFAULT 0)"
    )
    conn.execute(
        "INSERT INTO daemon_jobs VALUES "
        "('job-dry1','agy','t',NULL,'running',5,'[]',333,'2026-08-01T00:00:00','2026-08-01T00:00:00',NULL,NULL,NULL,0)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("os.kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setattr(
        "synlynk.jobs._iter_project_state_dbs",
        lambda all_projects=False: [str(db)],
    )

    assert cmd_jobs_reap(apply=False) == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "job-dry1" in out
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT status FROM daemon_jobs WHERE job_id='job-dry1'").fetchone()[0] == "running"
    conn.close()

    assert cmd_jobs_reap(apply=True) == 0
    out = capsys.readouterr().out
    assert "APPLY" in out
    assert "Reaped 1" in out
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT status, exit_code FROM daemon_jobs WHERE job_id='job-dry1'").fetchone() == (
        "timed_out",
        -9,
    )
    conn.close()


def test_auto_reap_job_from_sentinel(project_dir):
    from synlynk import _get_db
    from synlynk.jobs import auto_reap_job_from_sentinel

    conn = _get_db()
    _seed_daemon_job(conn, "job-ad59d3ea", agent="agy", pid=99999)
    conn.close()

    # Pretend PID is dead
    import synlynk.jobs as jobs_mod
    # auto_reap does not check PID — it marks running → timed_out on sentinel code
    updated = auto_reap_job_from_sentinel(
        "HARNESS_INTERNAL_TIMEOUT",
        "Job job-ad59d3ea on agent 'agy' died from an internal harness timeout",
    )
    assert updated == "job-ad59d3ea"
    conn = _get_db()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id='job-ad59d3ea'"
    ).fetchone()
    conn.close()
    assert row == ("timed_out", -9)


def test_write_sentinel_stall_auto_reaps(project_dir, monkeypatch):
    """_write_sentinel_alert(STALL_NO_OUTPUT) flips daemon_jobs running → timed_out."""
    from synlynk import _get_db, _write_sentinel_alert

    conn = _get_db()
    _seed_daemon_job(conn, "job-bd8ff601", agent="claude", pid=1)
    conn.close()

    _write_sentinel_alert(
        "CRITICAL",
        "STALL_NO_OUTPUT",
        "Job job-bd8ff601 on agent 'claude' stalled with zero output after 30min. Process killed.",
    )
    conn = _get_db()
    row = conn.execute(
        "SELECT status FROM daemon_jobs WHERE job_id='job-bd8ff601'"
    ).fetchone()
    conn.close()
    assert row[0] == "timed_out"


def test_jobs_reap_cli_parser():
    from synlynk.cli import build_parser

    args = build_parser().parse_args(["jobs", "reap", "--apply", "--all-projects"])
    assert args.command == "jobs"
    assert args.jobs_cmd == "reap"
    assert args.apply is True
    assert args.all_projects is True


# --- Epic A1: daemon_jobs GTV -------------------------------------------------

def test_gtv_status_dead_pid_with_git_activity_is_failed_unverified():
    from synlynk.jobs import _gtv_status_for_daemon_exit

    git_state = {
        "has_activity": True,
        "remote_has_activity": False,
        "changed_files": ["src/foo.py"],
        "commits_ahead": 1,
        "dirty": False,
    }
    status, exit_code, label, note = _gtv_status_for_daemon_exit(None, git_state)
    assert status == "failed_unverified"
    assert exit_code is None
    assert "FAILED_UNVERIFIED" in (label or "")
    assert note and "GTV" in note


def test_gtv_status_remote_only_activity_is_done():
    from synlynk.jobs import _gtv_status_for_daemon_exit

    git_state = {
        "has_activity": False,
        "remote_has_activity": True,
        "remote_ref": "origin/dispatch/grok/job-x",
        "changed_files": [],
        "remote_files_touched": ["docs/a.md"],
    }
    status, exit_code, label, note = _gtv_status_for_daemon_exit(None, git_state)
    assert status == "done"
    assert exit_code == 0


def test_gtv_status_no_exit_no_git_is_timed_out():
    from synlynk.jobs import _gtv_status_for_daemon_exit

    status, exit_code, label, note = _gtv_status_for_daemon_exit(None, None)
    assert status == "timed_out"
    assert exit_code == -9


def test_daemon_job_worktree_path_from_log(tmp_path):
    from synlynk.jobs import _daemon_job_worktree_path

    wt = tmp_path / "worktrees" / "job-abc"
    log = wt / ".synlynk" / "logs" / "job-abc.log"
    log.parent.mkdir(parents=True)
    log.write_text("x")
    assert _daemon_job_worktree_path("job-abc", str(log)) == str(wt)


def test_reconcile_daemon_jobs_gtv_uses_files_not_empty_summary(project_dir, monkeypatch):
    """Dead PID + git activity → failed_unverified with files in summary (#579)."""
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-gtv1"
    wt = project_dir / "worktrees" / job_id
    log = wt / ".synlynk" / "logs" / f"{job_id}.log"
    log.parent.mkdir(parents=True)
    log.write_text("agent did work\n")
    # no .exit file

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, depends_on, "
        "pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id, "grok", "do thing", "story-gtv", "running", 5, "[]",
            99999999, "2026-08-09T10:00:00", "2026-08-09T10:00:01", str(log),
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(
        jobs_mod,
        "_inspect_worktree_git_state",
        lambda path, branch=None, started_at=None: {
            "has_activity": True,
            "remote_has_activity": False,
            "changed_files": ["src/fixed.py"],
            "commits_ahead": 1,
            "dirty": False,
        },
    )
    monkeypatch.setattr(jobs_mod, "_pkg", lambda name, default=None: {
        "_get_db": sl._get_db,
        "extract_tokens": lambda log_text, agent="": type("T", (), {"basis": "none"})() if False else __import__("synlynk").extract_tokens(log_text, agent=agent) if hasattr(__import__("synlynk"), "extract_tokens") else (0, 0),
        "extract_model_version": lambda *a, **k: "test",
        "update_costs": lambda *a, **k: None,
        "_write_job_summary": sl._write_job_summary,
        "_release_reservation": None,
        "_inspect_worktree_git_state": lambda *a, **k: {
            "has_activity": True,
            "remote_has_activity": False,
            "changed_files": ["src/fixed.py"],
            "commits_ahead": 1,
            "dirty": False,
        },
        "_worktree_files_touched": lambda p: ["src/fixed.py"],
    }.get(name, getattr(sl, name, default)))

    # Simpler: only override what we need via module attributes used by _reconcile
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)

    def fake_pkg(name, default=None):
        if name == "_get_db":
            return sl._get_db
        if name == "extract_tokens":
            def _tok(log_text, agent=""):
                class TC(tuple):
                    basis = "none"
                return TC((10, 5))
            return _tok
        if name == "extract_model_version":
            return lambda *a, **k: "m"
        if name == "update_costs":
            return lambda *a, **k: None
        if name == "_write_job_summary":
            return sl._write_job_summary
        if name == "_release_reservation":
            return None
        if name == "_inspect_worktree_git_state":
            return lambda *a, **k: {
                "has_activity": True,
                "remote_has_activity": False,
                "changed_files": ["src/fixed.py"],
                "commits_ahead": 1,
                "dirty": False,
            }
        if name == "_worktree_files_touched":
            return lambda p: ["src/fixed.py"]
        return getattr(sl, name, default)

    monkeypatch.setattr(jobs_mod, "_pkg", fake_pkg)
    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    conn.close()
    assert row[0] == "failed_unverified"
    assert row[1] is None

    summary = (project_dir / ".synlynk" / "logs" / f"{job_id}.summary").read_text()
    assert "FAILED_UNVERIFIED" in summary or "failed_unverified" in summary.lower() or "exit unknown" in summary
    assert "src/fixed.py" in summary or "1 touched" in summary


# --- Epic A2: cost completeness (#752) ---------------------------------------

def test_ensure_daemon_job_cost_entry_writes_when_missing(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-cost-a2"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, enqueued_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (job_id, "claude", "t", "done", 5, "[]", "2026-08-09T12:00:00"),
    )
    conn.commit()

    wrote = []

    def fake_update(*a, **kw):
        wrote.append(kw.get("job_id") or (a[0] if a else None))
        from synlynk.db import _insert_cost_row
        _insert_cost_row(
            session_date="2026-08-09",
            agent="claude",
            model="test",
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cost_source="estimated_tshirt",
            total_cost_usd=0.01,
            job_id=job_id,
        )

    monkeypatch.setattr(jobs_mod, "_pkg", lambda name, default=None: {
        "_get_db": sl._get_db,
        "update_costs": fake_update,
        "extract_tokens": lambda *a, **k: (0, 0),
        "extract_model_version": lambda *a, **k: "m",
    }.get(name, getattr(sl, name, default)))

    assert jobs_mod._ensure_daemon_job_cost_entry(job_id, "claude", None, "", conn=conn) is True
    assert wrote
    # second call no-ops
    assert jobs_mod._ensure_daemon_job_cost_entry(job_id, "claude", None, "", conn=conn) is False
    n = conn.execute("SELECT COUNT(*) FROM cost_entries WHERE job_id=?", (job_id,)).fetchone()[0]
    conn.close()
    assert n == 1


def test_ensure_daemon_job_cost_entry_skips_when_present(project_dir):
    import synlynk as sl
    from synlynk.db import _insert_cost_row
    import synlynk.jobs as jobs_mod

    job_id = "job-cost-a2b"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, priority, depends_on, enqueued_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (job_id, "claude", "t", "done", 5, "[]", "2026-08-09T12:00:00"),
    )
    conn.commit()
    conn.close()
    _insert_cost_row(
        session_date="2026-08-09", agent="claude", model="t",
        input_tokens=5, output_tokens=1, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.1, job_id=job_id,
    )
    conn = sl._get_db()
    assert jobs_mod._ensure_daemon_job_cost_entry(job_id, "claude", None, "", conn=conn) is False
    conn.close()


def test_reconcile_daemon_jobs_emits_job_terminal_cost_recorded_true(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.events import pending_events

    job_id = "job-terminal-true"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'codex','t','running',999999,'2026-08-12T00:00:00','2026-08-12T00:00:00','headless')",
        (job_id,),
    )
    conn.commit()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["status"] in ("done", "failed_unverified", "timed_out", "failed")
    assert payload["cost_recorded"] is True
    assert payload["dispatch_context"] == "headless"


def test_reconcile_daemon_jobs_emits_job_terminal_cost_recorded_false_when_row_exists(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.db import _insert_cost_row
    from synlynk.events import pending_events

    job_id = "job-terminal-false"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'codex','t','running',999999,'2026-08-12T00:00:00','2026-08-12T00:00:00','home')",
        (job_id,),
    )
    conn.commit()
    _insert_cost_row(
        session_date="2026-08-12", agent="codex", model="t",
        input_tokens=1, output_tokens=1, cache_read_tokens=0,
        cost_source="actual", total_cost_usd=0.01, job_id=job_id,
    )

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(sl, "extract_tokens", lambda log_text, agent=None: (0, 0))
    monkeypatch.setattr(sl, "extract_model_version", lambda log_text, agent=None: "unknown")
    monkeypatch.setattr(sl, "update_costs", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_write_job_summary", lambda *a, **k: None)

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer2", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["cost_recorded"] is False
    assert payload["dispatch_context"] == "home"


def test_reconcile_daemon_jobs_emits_job_terminal_on_preferred_summary_path(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.jobs as jobs_mod
    from synlynk.events import pending_events

    job_id = "job-terminal-preferred"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at, dispatch_context) "
        "VALUES (?,'agy','t','running',NULL,'2026-08-12T00:00:00','2026-08-12T00:00:00','headless')",
        (job_id,),
    )
    conn.commit()

    monkeypatch.setattr(
        jobs_mod, "_existing_terminal_summary_truth",
        lambda job_id: ("done", 0),
    )

    sl._reconcile_daemon_jobs()

    events = pending_events("test-observer3", "job_terminal")
    matching = [e for e in events if e["payload"]["job_id"] == job_id]
    assert len(matching) == 1
    payload = matching[0]["payload"]
    assert payload["status"] == "done"
    assert payload["cost_recorded"] is True
