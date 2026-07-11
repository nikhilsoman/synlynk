import hashlib
import os
import subprocess

import pytest


def _job_id(agent: str, task: str, timestamp: float) -> str:
    return "job-" + hashlib.md5(f"{agent}{task}{timestamp}".encode()).hexdigest()[:8]


def _dispatch_git_worktree_job(monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    job_id = _job_id("codex", "fix bug", 1_725_000_000.123)
    worktree_path, worktree_branch = dispatch_mod._job_worktree_details(job_id, "codex")
    dispatch_mod._create_job_worktree(job_id, "codex")

    log_file = os.path.abspath(os.path.join(worktree_path, ".synlynk", "logs", f"{job_id}.log"))
    job = {
        "id": job_id,
        "agent": "codex",
        "story_id": "",
        "task": "fix bug",
        "pid": 4242,
        "log_file": log_file,
        "prompt_file": os.path.abspath(os.path.join(worktree_path, ".synlynk", "prompts", f"{job_id}.md")),
        "context_file": os.path.abspath(os.path.join(worktree_path, ".synlynk", "contexts", f"{job_id}.md")),
        "worktree_path": worktree_path,
        "worktree_branch": worktree_branch,
        "started_at": "2026-07-07T10:00:00",
        "ended_at": None,
        "status": "running",
        "exit_code": None,
        "dispatch_mode": "agent",
        "dispatch_rework": 0,
        "micro_rework": 0,
        "model_at_dispatch": "unknown",
    }
    sl._save_jobs([job])
    return job


def _commit_worktree_files(worktree_path: str, files: dict, message: str) -> None:
    for rel_path, content in files.items():
        abs_path = os.path.join(worktree_path, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(content)
    subprocess.run([
        "git",
        "-C",
        worktree_path,
        "add",
        *sorted(files),
    ], capture_output=True, check=True)
    subprocess.run([
        "git",
        "-C",
        worktree_path,
        "commit",
        "-m",
        message,
    ], capture_output=True, check=True)


def test_dispatch_real_files_touched_via_git_diff_lists_committed_and_dirty_files(git_worktree_repo, monkeypatch):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(
        job["worktree_path"],
        {"alpha.txt": "alpha\n", "beta.txt": "beta\n"},
        "touch two files",
    )
    with open(os.path.join(job["worktree_path"], "dirty.txt"), "w") as f:
        f.write("dirty\n")

    touched = sl._worktree_files_touched(job["worktree_path"])

    assert touched == ["alpha.txt", "beta.txt", "dirty.txt"]


def test_dispatch_real_files_touched_via_git_diff_clean_worktree_returns_empty(git_worktree_repo, monkeypatch):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)

    assert sl._worktree_files_touched(job["worktree_path"]) == []


def test_dispatch_real_files_touched_via_git_diff_missing_worktree_path_returns_empty():
    import synlynk as sl

    assert sl._worktree_files_touched(None) == []


def test_dispatch_real_files_touched_via_git_diff_summary_lists_and_truncates_files():
    import synlynk as sl

    files = [f"src/file-{idx:02d}.py" for idx in range(23)]
    text = sl._format_job_summary(
        "job-123",
        "codex",
        "story-9",
        0,
        12.4,
        100,
        20,
        0.14,
        files,
        worktree_path="worktrees/job-123",
        worktree_branch="dispatch/codex/job-123",
    )

    assert "files:    23 touched" in text
    assert "          src/file-00.py" in text
    assert "          src/file-19.py" in text
    assert "          src/file-20.py" not in text
    assert "          +3 more" in text


def test_dispatch_perjob_git_worktree_isolation_creates_branch_and_worktree(git_worktree_repo, monkeypatch):
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


def test_dispatch_perjob_git_worktree_isolation_uses_distinct_worktrees(git_worktree_repo, monkeypatch):
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


def test_dispatch_perjob_git_worktree_isolation_fails_loudly_on_worktree_error(git_worktree_repo, monkeypatch):
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


def test_migrate_transparency__failloud_on_0row_import_reports_all_failed_sources(tmp_path, monkeypatch, capsys):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk").mkdir()
    docs_dir = tmp_path / "project-docs"
    docs_dir.mkdir()
    (docs_dir / "memory.md").write_text(
        "# synlynk Memory\n\n## First\n\nBody [@alice].\n\n## Second\n\nMore body.\n"
    )
    (docs_dir / "roadmap.md").write_text(
        "# Roadmap\n\n## v0.9.0 — Shipped ✅\n\n- feat: core [P0]\n\n## v0.10.0\n\n- wizard [P0]\n"
    )
    (docs_dir / "todo.md").write_text(
        "- [ ] priority-only <!-- id:story-priority --> <!-- priority:next -->\n"
    )

    class FakeConn:
        def execute(self, sql, params=()):
            if sql.lstrip().upper().startswith(("INSERT", "UPDATE")):
                raise RuntimeError("forced write failure")

            class Cursor:
                rowcount = 0

            return Cursor()

        def commit(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(sl, "_get_db", lambda: FakeConn())
    monkeypatch.setattr(sl.subprocess, "run", lambda *a, **kw: None)

    raised = False
    try:
        sl.cmd_migrate()
    except SystemExit as exc:
        raised = True
        assert exc.code == 1

    assert raised is True
    out = capsys.readouterr().out
    assert "DB path:" in out
    assert "memory_entries" in out
    assert "roadmap_arcs" in out
    assert "roadmap_phases" in out
    assert "todo_metadata (" not in out
    assert "git rm --cached" not in out


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


def test_dispatch_real_files_touched_via_git_diff_reconciliation_writes_summary(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(
        job["worktree_path"],
        {"gamma.txt": "gamma\n", "delta.txt": "delta\n"},
        "touch two more files",
    )

    sl._reconcile_jobs()
    out = capsys.readouterr().out

    assert job["worktree_path"] in out
    assert "files:    2 touched" in out
    assert "          delta.txt" in out
    assert "          gamma.txt" in out
    assert "FAILED_UNVERIFIED" in out


def test_dispatch_gitstateverified_job_reconciliation_marks_ambiguous_exit_with_git_activity_unverified(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(job["worktree_path"], {"git-state-proof.txt": "proof\n"}, "proof")

    sl._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "failed_unverified"
    assert reconciled["exit_code"] is None
    assert job["worktree_path"] in out
    assert "FAILED_UNVERIFIED (exit unknown)" in out
    assert "job exited ambiguously but the worktree contains 1 commit(s)" in out
    assert "inspect before discarding" in out


def test_dispatch_gitstateverified_job_reconciliation_missing_exit_clean_worktree_remains_failed(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)

    sl._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "failed"
    assert reconciled["exit_code"] == -1
    assert "FAILED_UNVERIFIED" not in out
    assert "worktree:" in out


def test_dispatch_gitstateverified_job_stall_git_activity_defers_kill(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(job["worktree_path"], {"git-stall-proof.txt": "stall proof\n"}, "stall proof")

    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    job["log_file"] = str(log_file)
    job["started_at"] = time.time() - 7200

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is False
    assert job["status"] == "running"
    assert killed == []


def test_dispatch_gitstateverified_job_stall_clean_worktree_still_kills(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import signal
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    job["log_file"] = str(log_file)
    job["started_at"] = time.time() - 7200

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is True
    assert job["status"] == "failed"
    assert killed == [(job["pid"], signal.SIGKILL)]


def test_implement_the_schemavalidation_half_of_g_story_create_rejects_invalid_tags(tmp_path, monkeypatch):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / "project-docs").mkdir()
    (tmp_path / "project-docs" / "todo.md").write_text("# Project Todo List\n## Active Tasks\n")

    valid = dict(title="Story", engg_domain="backend", org_domain="platform", role="dev", stage="open")
    with pytest.raises(ValueError, match="org_domain"):
        sl.cmd_story_create(**{**valid, "org_domain": "engineering"})
    with pytest.raises(ValueError, match="discipline"):
        sl.cmd_story_create(**{**valid, "discipline": "cli"})
    with pytest.raises(ValueError, match="role"):
        sl.cmd_story_create(**{**valid, "role": "lead"})
    with pytest.raises(ValueError, match="stage"):
        sl.cmd_story_create(**{**valid, "stage": "design"})


def test_implement_the_schemavalidation_half_of_g_migration_remaps_org_domain_and_warns(tmp_path, monkeypatch, capsys):
    import synlynk as sl
    from synlynk.db import _migrate_db as migrate_db

    monkeypatch.chdir(tmp_path)
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, phase) VALUES (?,?,?,?,?)",
        ("story-platform", "Platform story", "backend", "developer_experience", "build"),
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, phase) VALUES (?,?,?,?,?)",
        ("story-unknown", "Unknown story", "frontend", "sales_ops", "build"),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-platform", "claude", "claude-opus-4-8", "backend", "marketing", "ott", "build", "auto", 8.0, 8.0),
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-unknown", "claude", "claude-opus-4-8", "frontend", "proto", "ott", "build", "auto", 6.0, 6.0),
    )
    conn.commit()

    migrate_db(conn)
    out = capsys.readouterr().out

    story_rows = conn.execute(
        "SELECT story_id, org_domain FROM stories ORDER BY story_id"
    ).fetchall()
    rating_rows = conn.execute(
        "SELECT story_id, org_domain FROM capability_ratings ORDER BY story_id"
    ).fetchall()
    conn.close()

    assert story_rows == [("story-platform", "platform"), ("story-unknown", "unknown")]
    assert rating_rows == [("story-platform", "growth"), ("story-unknown", "unknown")]
    assert "sales_ops" in out
    assert "remapped to unknown" in out


@pytest.mark.parametrize("agent_name", ["gemini", "unknown"])
def test_implement_the_schemavalidation_half_of_g_write_rejects_unregistered_agent(tmp_path, monkeypatch, agent_name):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    story_id = sl.cmd_story_create("Agent gate story", engg_domain="backend", org_domain="platform")
    job = {
        "story_id": story_id,
        "agent": agent_name,
        "model_at_dispatch": "unknown",
        "started_at": "2026-07-11T10:00:00",
        "ended_at": "2026-07-11T10:01:00",
        "exit_code": 0,
        "dispatch_rework": 0,
        "micro_rework": 0,
    }

    with pytest.raises(ValueError, match="unregistered agent"):
        sl._write_capability_rating(job, "Build complete.")
