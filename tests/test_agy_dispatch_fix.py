import hashlib
import os
import subprocess
import tempfile

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


def _fake_completed_process(stdout="", stderr="", returncode=0):
    class Result:
        pass

    result = Result()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def test_extract_build_parser_from_clipy_main_for_cli_introspection():
    import synlynk.cli as cli_mod

    parser = cli_mod.build_parser()
    args = parser.parse_args(["dispatch", "codex", "--task", "build"])

    assert args.command == "dispatch"
    assert args.agent == "codex"
    assert args.task == "build"


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

    captured_run = []
    captured_popen = {}

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        captured_run.append((cmd, kwargs))
        if cmd == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return _fake_completed_process(stdout=os.path.abspath(os.path.join(os.getcwd(), ".git")))
        if isinstance(cmd, list) and ("merge-base" in cmd or (len(cmd) > 3 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "rev-parse")):
            return _fake_completed_process(stdout="abc123")
        return _fake_completed_process()

    def fake_popen(cmd, **kwargs):
        captured_popen["kwargs"] = kwargs
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

    assert ["git", "fetch", "origin", "main"] in [cmd for cmd, _ in captured_run]
    assert [
        "git",
        "worktree",
        "add",
        expected_worktree,
        "-b",
        expected_branch,
        "origin/main",
    ] in [cmd for cmd, _ in captured_run]
    worktree_run_kwargs = next(kwargs for cmd, kwargs in captured_run if cmd[:3] == ["git", "worktree", "add"])
    assert worktree_run_kwargs["cwd"] == os.getcwd()
    assert job["worktree_path"] == expected_worktree
    assert job["worktree_branch"] == expected_branch
    assert captured_popen["kwargs"]["cwd"] == expected_worktree
    assert job["log_file"].startswith(os.path.abspath(expected_worktree))


def test_dispatch_perjob_git_worktree_isolation_prefers_fresh_origin_main_over_stale_local_main(
    git_worktree_repo,
):
    """Local main can lag origin/main when many worktrees share one repo.

    Prefer origin/main so files_touched excludes unrelated mainline commits
    that landed on origin after the local main ref stopped moving.
    """
    import synlynk as sl

    def git(cmd, cwd=git_worktree_repo):
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

    # Stabilize on main; capture the pre-advance tip used as a stale local main.
    git(["git", "branch", "-M", "main"])
    stale_main_tip = git(["git", "rev-parse", "HEAD"])

    # Keep bare remote + upstream *outside* the fixture worktree so they do not
    # appear in files_touched as untracked paths. Use a unique temp dir (not the
    # shared pytest basetemp parent, which collides across tests).
    temp_root = tempfile.mkdtemp(prefix="synlynk-issue-395-")
    remote_dir = os.path.join(temp_root, "origin.git")
    subprocess.run(["git", "init", "--bare", remote_dir], capture_output=True, check=True)
    # Bare repos default HEAD to master on some hosts; force main so clone checks out main.
    subprocess.run(
        ["git", "-C", remote_dir, "symbolic-ref", "HEAD", "refs/heads/main"],
        capture_output=True,
        check=True,
    )
    git(["git", "remote", "add", "origin", remote_dir])
    git(["git", "push", "-u", "origin", "main"])

    upstream_dir = os.path.join(temp_root, "upstream")
    subprocess.run(["git", "clone", remote_dir, upstream_dir], capture_output=True, check=True)

    git(["git", "config", "user.email", "codex@example.com"], cwd=upstream_dir)
    git(["git", "config", "user.name", "Codex"], cwd=upstream_dir)
    with open(os.path.join(upstream_dir, "origin-mainline.txt"), "w") as f:
        f.write("origin mainline\n")
    git(["git", "add", "origin-mainline.txt"], cwd=upstream_dir)
    git(["git", "commit", "-m", "advance origin main"], cwd=upstream_dir)
    # HEAD:main is robust if the clone's local branch name differs across git versions.
    git(["git", "push", "origin", "HEAD:main"], cwd=upstream_dir)

    git(["git", "fetch", "origin", "main"])
    origin_tip = git(["git", "rev-parse", "origin/main"])
    assert origin_tip != stale_main_tip

    # Move off main before force-updating it (git refuses -f on the checked-out branch).
    git(["git", "checkout", "-B", "feature/job-395", "origin/main"])
    git(["git", "branch", "-f", "main", stale_main_tip])

    with open(os.path.join(git_worktree_repo, "feature-only.txt"), "w") as f:
        f.write("feature work\n")
    git(["git", "add", "feature-only.txt"])
    git(["git", "commit", "-m", "feature work"])

    base_info = sl._resolve_worktree_base_commit(git_worktree_repo)
    touched = sl._worktree_files_touched(git_worktree_repo)

    assert base_info == {"base_commit": origin_tip, "base_ref": "origin/main"}
    assert touched == ["feature-only.txt"]

    # Guard: preferring the stale local main would include origin-mainline.txt as well.
    merge_base_local = git(["git", "merge-base", "HEAD", "main"])
    assert merge_base_local == stale_main_tip
    stale_diff = git(["git", "diff", "--name-only", merge_base_local, "HEAD"]).splitlines()
    assert "origin-mainline.txt" in stale_diff
    assert "feature-only.txt" in stale_diff


def test_dispatch_perjob_git_worktree_isolation_uses_distinct_worktrees(git_worktree_repo, monkeypatch):
    import synlynk as sl

    created = []
    spawned = []

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

    def fake_run(cmd, **kwargs):
        created.append((cmd, kwargs))
        if cmd == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return _fake_completed_process(stdout=os.path.abspath(os.path.join(os.getcwd(), ".git")))
        if isinstance(cmd, list) and ("merge-base" in cmd or (len(cmd) > 3 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "rev-parse")):
            return _fake_completed_process(stdout="abc123")
        return _fake_completed_process()

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
    assert len(created) == 10


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


def test_dispatch_perjob_git_worktree_isolation_branches_from_fresh_origin_tip(git_worktree_repo, monkeypatch):
    import synlynk as sl

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=git_worktree_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    initial_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_worktree_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    remote_dir = os.path.join(git_worktree_repo, "origin.git")
    subprocess.run(["git", "init", "--bare", remote_dir], capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", remote_dir],
        cwd=git_worktree_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", current_branch],
        cwd=git_worktree_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "--detach", initial_commit],
        cwd=git_worktree_repo,
        capture_output=True,
        check=True,
    )

    upstream_dir = os.path.join(git_worktree_repo, "upstream")
    subprocess.run(
        ["git", "clone", remote_dir, upstream_dir],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "codex@example.com"],
        cwd=upstream_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Codex"],
        cwd=upstream_dir,
        capture_output=True,
        check=True,
    )
    with open(os.path.join(upstream_dir, "remote-only.txt"), "w") as f:
        f.write("remote tip\n")
    subprocess.run(
        ["git", "add", "remote-only.txt"],
        cwd=upstream_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "advance remote tip"],
        cwd=upstream_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "push", "origin", current_branch],
        cwd=upstream_dir,
        capture_output=True,
        check=True,
    )

    captured = {}
    real_popen = sl.subprocess.Popen

    class FakeProc:
        pid = 4242

    def fake_popen(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[:2] == ["sh", "-c"]:
            captured["popen_cmd"] = cmd
            captured["popen_kwargs"] = kwargs
            return FakeProc()
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(sl.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None})
    monkeypatch.setattr(sl, "_probe_model_version", lambda *a, **kw: "unknown")
    monkeypatch.setattr(sl, "generate_context", lambda scope="full", out_path=None: "")
    monkeypatch.setattr(sl, "_relevant_files_for_story", lambda _story_id: [])
    monkeypatch.setattr(sl, "_verify_contract_for_story", lambda _story_id, _task: "")
    monkeypatch.setattr(sl, "_count_dispatch_rework", lambda _story_id: 0)
    monkeypatch.setattr(sl.time, "time", lambda: 1_725_000_000.123)

    job = sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    worktree_commit = subprocess.run(
        ["git", "-C", job["worktree_path"], "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    origin_commit = subprocess.run(
        ["git", "-C", upstream_dir, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert worktree_commit == origin_commit
    assert captured["popen_kwargs"]["cwd"] == job["worktree_path"]


def test_dispatch_codex_adds_git_common_dir_as_writable(git_worktree_repo, monkeypatch):
    import synlynk as sl

    captured = {}
    git_common_dir = os.path.abspath(os.path.join(os.getcwd(), ".git"))

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        captured.setdefault("runs", []).append((cmd, kwargs))
        if cmd == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return _fake_completed_process(stdout=git_common_dir, returncode=0)
        if isinstance(cmd, list) and ("merge-base" in cmd or (len(cmd) > 3 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "rev-parse")):
            return _fake_completed_process(stdout="abc123")
        return _fake_completed_process()

    def fake_popen(cmd, **kwargs):
        captured["popen_cmd"] = cmd
        captured["popen_kwargs"] = kwargs
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

    sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    shell_cmd = captured["popen_cmd"][2]
    assert "--add-dir" in shell_cmd
    assert f"--add-dir {git_common_dir}" in shell_cmd


def test_dispatch_codex_skips_git_common_dir_when_git_rev_parse_fails(git_worktree_repo, monkeypatch):
    import synlynk as sl

    captured = {}

    class FakeProc:
        pid = 4242

    def fake_run(cmd, **kwargs):
        captured.setdefault("runs", []).append((cmd, kwargs))
        if cmd == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return _fake_completed_process(stdout="", returncode=1)
        if isinstance(cmd, list) and ("merge-base" in cmd or (len(cmd) > 3 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "rev-parse")):
            return _fake_completed_process(stdout="abc123")
        return _fake_completed_process()

    def fake_popen(cmd, **kwargs):
        captured["popen_cmd"] = cmd
        captured["popen_kwargs"] = kwargs
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

    sl.dispatch_agent("codex", "fix bug", skip_preflight=True)

    shell_cmd = captured["popen_cmd"][2]
    assert "--add-dir" not in shell_cmd


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


def test_dispatch_gitstateverified_job_reconciliation_rechecks_failed_job_with_late_git_activity(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    with open(os.path.join(job["worktree_path"], "late-write.txt"), "w") as f:
        f.write("late write\n")

    inspect_calls = {"count": 0}

    def fake_inspect(worktree_path, worktree_branch=None, started_at=None):
        inspect_calls["count"] += 1
        if inspect_calls["count"] == 1:
            return {
                "worktree_path": worktree_path,
                "dirty": False,
                "commits_ahead": 0,
                "base_ref": None,
                "base_commit": None,
                "has_activity": False,
                "remote_ref": None,
                "remote_commit_count": 0,
                "remote_files_touched": [],
                "remote_has_activity": False,
            }
        return {
            "worktree_path": worktree_path,
            "dirty": True,
            "commits_ahead": 0,
            "base_ref": None,
            "base_commit": None,
            "has_activity": True,
            "remote_ref": None,
            "remote_commit_count": 0,
            "remote_files_touched": [],
            "remote_has_activity": False,
        }

    monkeypatch.setattr(sl, "_inspect_worktree_git_state", fake_inspect)
    monkeypatch.setattr(sl.os, "kill", lambda *_args, **_kwargs: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])
    summary_path = os.path.join(".synlynk", "logs", f"{job['id']}.summary")

    assert inspect_calls["count"] >= 2
    assert reconciled["status"] == "failed_unverified"
    assert reconciled["exit_code"] is None
    assert "FAILED_UNVERIFIED (exit unknown)" in out

    with open(summary_path) as f:
        summary = f.read()

    assert "status:   FAILED_UNVERIFIED (exit unknown)" in summary
    assert "files:    1 touched" in summary
    assert "late-write.txt" in summary
    assert "git-state recheck recovered" in summary


def test_dispatch_gitstateverified_job_reconciliation_missing_exit_clean_worktree_is_unknown(git_worktree_repo, monkeypatch, capsys):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)

    sl._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "unknown"
    assert reconciled["exit_code"] is None
    assert "UNKNOWN (exit unknown)" in out
    assert "FAILED_UNVERIFIED" not in out
    assert "worktree:" in out


def test_dispatch_gitstateverified_job_reconciliation_uses_waitpid_without_exit_file(
    git_worktree_repo, monkeypatch, capsys
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job = _dispatch_git_worktree_job(monkeypatch)

    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (job["pid"], 0))
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *a, **kw: {"has_activity": False, "remote_has_activity": False})
    monkeypatch.setattr(sl, "_worktree_files_touched", lambda *a, **kw: [])
    monkeypatch.setattr(jobs_mod, "_finalize_completed_worktree_job", lambda *a, **kw: None)

    sl._reconcile_jobs()
    out = capsys.readouterr().out
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "completed"
    assert reconciled["exit_code"] == 0
    assert "status:   OK (exit 0)" in out


def test_dispatch_gitstateverified_job_stall_git_activity_defers_kill(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(job["worktree_path"], {"git-stall-proof.txt": "stall proof\n"}, "stall proof")

    log_file = tmp_path / f"{job['id']}.log"
    with open(log_file, "wb"):
        pass
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time

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
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is True
    assert job["status"] == "failed"
    assert killed == [(job["pid"], signal.SIGKILL)]


def test_dispatch_gitstateverified_job_reconciliation_tags_harness_internal_timeout(git_worktree_repo, monkeypatch):
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    os.makedirs(os.path.dirname(job["log_file"]), exist_ok=True)
    with open(job["log_file"], "a") as f:
        f.write("some output\nError: timeout waiting for response\n")

    def fake_kill(pid, sig):
        if sig == 0:
            raise ProcessLookupError()

    monkeypatch.setattr(sl.os, "kill", fake_kill)
    monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *_args, **_kwargs: None)

    sl._reconcile_jobs()
    jobs = sl._load_jobs()
    reconciled = next(j for j in jobs if j["id"] == job["id"])

    assert reconciled["status"] == "unknown"
    assert reconciled["exit_code"] is None
    sentinel_content = open(".synlynk/sentinel.md").read()
    assert "HARNESS_INTERNAL_TIMEOUT" in sentinel_content
    assert job["id"] in sentinel_content
    assert "timeout waiting for response" in sentinel_content


def test_dispatch_gitstateverified_job_stall_stale_nonempty_log_still_kills(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import signal
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    log_file = tmp_path / f"{job['id']}.log"
    log_file.write_text("some output\n")
    old_time = time.time() - 7200
    os.utime(log_file, (old_time, old_time))
    job["log_file"] = str(log_file)
    job["started_at"] = old_time

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(sl.os, "kill", fake_kill)

    result = sl._check_job_stall(job, {"stall_timeout_minutes": 30}, ".synlynk/sentinel.md")

    assert result is True
    assert job["status"] == "failed"
    assert killed == [(job["pid"], signal.SIGKILL)]


def test_dispatch_gitstateverified_job_stall_fresh_nonempty_log_not_killed(git_worktree_repo, monkeypatch, tmp_path):
    import time
    import synlynk as sl

    job = _dispatch_git_worktree_job(monkeypatch)
    log_file = tmp_path / f"{job['id']}.log"
    log_file.write_text("some output\n")
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


def test_followup_fix_for_open_pr_147_branch_disp_unknown_agent_warning_and_continues(tmp_path, monkeypatch, capsys):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/logs", exist_ok=True)

    unknown_story = sl.cmd_story_create("Unknown agent story", engg_domain="backend")
    known_story = sl.cmd_story_create("Known agent story", engg_domain="backend")

    unknown_log = os.path.join(".synlynk", "logs", "job-unknown.log")
    known_log = os.path.join(".synlynk", "logs", "job-known.log")
    for path in (unknown_log, known_log):
        with open(path, "w") as fh:
            fh.write("# synlynk-meta\nmodel_version=claude-opus-4-8\n47 passed in 3.2s\n")
        with open(path + ".exit", "w") as fh:
            fh.write("0")

    sl._save_jobs([
        {
            "id": "job-unknown",
            "agent": "gemini",
            "story_id": unknown_story,
            "pid": 1,
            "status": "running",
            "log_file": unknown_log,
            "prompt_file": None,
            "worktree_path": None,
            "worktree_branch": None,
            "started_at": "2026-07-07T10:00:00",
            "ended_at": None,
            "exit_code": None,
            "dispatch_mode": "agent",
            "dispatch_rework": 0,
            "micro_rework": 0,
            "model_at_dispatch": "unknown",
        },
        {
            "id": "job-known",
            "agent": "claude",
            "story_id": known_story,
            "pid": 1,
            "status": "running",
            "log_file": known_log,
            "prompt_file": None,
            "worktree_path": None,
            "worktree_branch": None,
            "started_at": "2026-07-07T10:00:00",
            "ended_at": None,
            "exit_code": None,
            "dispatch_mode": "agent",
            "dispatch_rework": 0,
            "micro_rework": 0,
            "model_at_dispatch": "unknown",
        },
    ])
    original_write = sl._write_capability_rating
    call_count = {"count": 0}

    def fake_write_capability_rating(job, log_text):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise ValueError("boom")
        return original_write(job, log_text)

    monkeypatch.setattr(sl, "_write_capability_rating", fake_write_capability_rating)
    monkeypatch.setattr(sl.os, "kill", lambda *_args, **_kwargs: (_ for _ in ()).throw(ProcessLookupError()))

    sl._reconcile_jobs()
    out = capsys.readouterr().out

    assert "capability rating skipped for job job-unknown: boom" in out

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT story_id, agent FROM capability_ratings ORDER BY story_id"
    ).fetchall()
    conn.close()
    assert rows == [(known_story, "claude")]


def test_followup_fix_for_open_pr_147_branch_disp_stack_tags_auto_detected_and_persisted(
    tmp_path, monkeypatch
):
    import json
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    monkeypatch.setattr(sl, "fingerprint_stack", lambda _root: ["Python", "Docker", "Python"])
    monkeypatch.setattr(sl, "_sign_capability_rating", lambda data: "")

    story_id = sl.cmd_story_create("Stack tags story", engg_domain="backend")

    conn = sl._get_db()
    story_row = conn.execute(
        "SELECT stack_tags FROM stories WHERE story_id=?",
        (story_id,),
    ).fetchone()

    job = {
        "story_id": story_id,
        "agent": "claude",
        "model_at_dispatch": "claude-3",
        "started_at": "2026-07-07T10:00:00",
        "ended_at": "2026-07-07T10:05:00",
        "exit_code": 0,
        "dispatch_rework": 0,
        "micro_rework": 0,
    }
    sl._write_capability_rating(job, "# synlynk-meta\nmodel_version=claude-opus-4-8\n47 passed in 3.2s\n")

    rating_row = conn.execute(
        "SELECT stack_tags FROM capability_ratings WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()

    assert json.loads(story_row[0]) == ["Python", "Docker"]
    assert json.loads(rating_row[0]) == ["Python", "Docker"]


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


def test_wire_the_2_dead_auto_signals_and_add_the_pr_review_cycles_from_pr_review_api(tmp_path, monkeypatch):
    import json
    import synlynk as sl
    import synlynk.sentinel as sentinel_mod

    monkeypatch.chdir(tmp_path)
    story_id = sl.cmd_story_create("Review cycles story", engg_domain="backend", org_domain="platform")
    payload = {
        "reviews": [
            {"state": "CHANGES_REQUESTED", "submittedAt": "2026-07-11T10:00:00Z"},
            {"state": "APPROVED", "submittedAt": "2026-07-11T11:00:00Z"},
            {"state": "CHANGES_REQUESTED", "submittedAt": "2026-07-11T12:00:00Z"},
            {"state": "APPROVED", "submittedAt": "2026-07-11T13:00:00Z"},
        ]
    }

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["gh", "pr", "view"]:
            return _fake_completed_process(stdout=json.dumps(payload))
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _fake_completed_process(stdout="no checks reported", returncode=1)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(sentinel_mod.subprocess, "run", fake_run)

    job = {
        "story_id": story_id,
        "agent": "claude",
        "model_at_dispatch": "claude-3",
        "started_at": "2026-07-11T10:00:00",
        "ended_at": "2026-07-11T10:30:00",
        "exit_code": 0,
        "dispatch_rework": 0,
        "micro_rework": 0,
        "worktree_path": str(tmp_path),
        "worktree_branch": "feature/review-cycles",
    }

    sl._write_capability_rating(job, "Build complete.")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT pr_review_cycles, verified_by_ci, dispatch_rework, micro_rework "
        "FROM capability_ratings WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()

    assert row[0] == 2
    assert row[1] is None
    assert row[2] == 0
    assert row[3] == 0


@pytest.mark.parametrize(
    "ci_stdout, ci_returncode, expected",
    [
        ("no checks reported", 1, None),
        ("✓ build passed", 0, 1),
        ("✗ build failed", 1, 0),
    ],
)
def test_wire_the_2_dead_auto_signals_and_add_the_verified_by_ci_can_be_null_true_false(
    tmp_path,
    monkeypatch,
    ci_stdout,
    ci_returncode,
    expected,
):
    import json
    import synlynk as sl
    import synlynk.sentinel as sentinel_mod

    monkeypatch.chdir(tmp_path)
    story_id = sl.cmd_story_create("CI signal story", engg_domain="backend", org_domain="platform")

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["gh", "pr", "view"]:
            return _fake_completed_process(stdout=json.dumps({"reviews": []}))
        if cmd[:3] == ["gh", "pr", "checks"]:
            return _fake_completed_process(stdout=ci_stdout, returncode=ci_returncode)
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(sentinel_mod.subprocess, "run", fake_run)

    job = {
        "story_id": story_id,
        "agent": "claude",
        "model_at_dispatch": "claude-3",
        "started_at": "2026-07-11T10:00:00",
        "ended_at": "2026-07-11T10:05:00",
        "exit_code": 0,
        "dispatch_rework": 0,
        "micro_rework": 0,
        "worktree_path": str(tmp_path),
        "worktree_branch": "feature/ci-signal",
    }

    sl._write_capability_rating(job, "Build complete.")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT verified_by_ci FROM capability_ratings WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()

    assert row[0] == expected


def test_wire_the_2_dead_auto_signals_and_add_the_verifier_tier_weight_blends_with_auto_quality(
    tmp_path,
    monkeypatch,
):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    story_id = sl.cmd_story_create("Verifier weight story", engg_domain="backend", org_domain="platform")
    job = {
        "story_id": story_id,
        "agent": "claude",
        "model_at_dispatch": "claude-3",
        "started_at": "2026-07-11T10:00:00",
        "ended_at": "2026-07-11T10:05:00",
        "exit_code": None,
        "dispatch_rework": 0,
        "micro_rework": 0,
    }

    sl._write_capability_rating(
        job,
        "# synlynk-meta\nquality=7\ncorrect=true\nrework_needed=false\nverifier_model=gemini-2.5-pro\n",
    )

    conn = sl._get_db()
    row = conn.execute(
        "SELECT signal_source, quality_auto, quality FROM capability_ratings WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()

    assert row[0] == "verifier"
    assert row[1] == pytest.approx(10.0, abs=0.01)
    assert row[2] == pytest.approx(7.45, abs=0.01)


def test_wire_the_2_dead_auto_signals_and_add_the_dispatch_rework_and_micro_rework_stay_distinct(
    tmp_path,
    monkeypatch,
):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    story_id = sl.cmd_story_create("Rework signal story", engg_domain="backend", org_domain="platform")
    job = {
        "story_id": story_id,
        "agent": "claude",
        "model_at_dispatch": "claude-3",
        "started_at": "2026-07-11T10:00:00",
        "ended_at": "2026-07-11T10:05:00",
        "exit_code": None,
        "dispatch_rework": 3,
        "micro_rework": 7,
    }

    sl._write_capability_rating(job, "Build complete.")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT dispatch_rework, micro_rework, quality_auto FROM capability_ratings WHERE story_id=?",
        (story_id,),
    ).fetchone()
    conn.close()

    assert row[0] == 3
    assert row[1] == 7
    assert row[2] == pytest.approx(4.0, abs=0.01)
def test_extend_tokencost_extraction_with_cache_b_sample_transcript():
    import synlynk as sl

    text = (
        '{"model":"claude-sonnet-4-6","usage":{'
        '"input_tokens":4821,"output_tokens":312,"cached_tokens":128},'
        '"content":"done"}'
    )

    tokens = sl.extract_tokens(text)

    assert tuple(tokens) == (4821, 312)
    assert tokens.cache_read_tokens == 128


def test_extend_tokencost_extraction_parses_multiline_total_tokens():
    import synlynk as sl

    text = "codex finished\n\ntokens used\n259,718\n"

    tokens = sl.extract_tokens(text)

    assert sum(tokens) == 259718
    assert tokens.cache_read_tokens == 0


def test_extend_tokencost_extraction_with_cache_b_rate_table_lookup():
    import synlynk as sl

    known = sl._model_rate_for_version("claude-opus-4-8")
    fallback = sl._model_rate_for_version("unrecognized-model")
    gemini = sl._model_rate_for_version("gemini-2.5-pro")

    assert known["input"] == 0.015
    assert known["output"] == 0.075
    assert fallback["input"] == 0.003
    assert fallback["output"] == 0.015
    assert gemini["input"] == 0.00125
    assert gemini["output"] == 0.01
    assert gemini["cache_read"] == 0.000125


def test_extend_tokencost_extraction_with_cache_b_unknown_model_on_local_agent_is_zero():
    import synlynk as sl

    zero_rate = sl._model_rate_for_version("unrecognized-model", agent="/usr/local/bin/local")

    assert zero_rate["input"] == 0.0
    assert zero_rate["output"] == 0.0
    assert zero_rate["cache_read"] == 0.0


def test_extend_tokencost_extraction_with_cache_b_update_costs_inserts_fk_columns(tmp_path, monkeypatch):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk" / "project-docs").mkdir(parents=True)

    captured = {}

    class FakeConn(object):
        def execute(self, query, params=None):
            captured["query"] = query
            captured["params"] = params
            return self

        def commit(self):
            captured["committed"] = True

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(sl, "_is_migrated", lambda: True)
    monkeypatch.setattr(sl, "_get_db", lambda: FakeConn())
    monkeypatch.setattr(sl, "_dr_sync", lambda _path: None)

    sl.update_costs(
        "claude --print hello",
        1000,
        200,
        30.0,
        cache_read_tokens=128,
        model_version="claude-sonnet-4-6",
        story_id="story-1",
        epic_id=7,
        phase_id=11,
    )

    assert "story_id" in captured["query"]
    assert "epic_id" in captured["query"]
    assert "phase_id" in captured["query"]
    assert captured["params"][2] == "claude-sonnet-4-6"
    assert captured["params"][5] == 128
    assert captured["params"][13] == "story-1"
    assert captured["params"][14] == 7
    assert captured["params"][15] == 11


def test_extend_tokencost_extraction_with_cache_b_update_costs_backwards_compatible_default_args(tmp_path, monkeypatch):
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk" / "project-docs").mkdir(parents=True)

    calls = []

    class FakeConn(object):
        def execute(self, query, params=None):
            calls.append((query, params))
            return self

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(sl, "_is_migrated", lambda: True)
    monkeypatch.setattr(sl, "_get_db", lambda: FakeConn())
    monkeypatch.setattr(sl, "_dr_sync", lambda _path: None)

    sl.update_costs("claude", 100, 50, 5.0)

    assert calls
    assert "cost_entries" in calls[0][0]


def test_fix_a_nameerror_regression_in_your_own_prior_work_exec_command_does_not_raise(
    tmp_path, monkeypatch
):
    import synlynk as sl
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(sl, "generate_context", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_budgets", lambda: None)
    monkeypatch.setattr(sl, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(sl, "set_state", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(sl, "log_telemetry_event", lambda *a, **kw: None)
    monkeypatch.setattr(sl, "check_sentinel_patterns", lambda **kw: None)
    monkeypatch.setattr(sl, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(sl, "WatchDaemon", None)
    monkeypatch.setattr(sl, "update_costs", lambda *a, **kw: None)

    exit_code = exec_command(["echo", "--print", "Input tokens: 10 Output tokens: 5"])

    assert exit_code == 0


# --- #141: agent_quotas base table + stage-2 quota gate -------------------

def _seed_capability(conn, story_id, agent, quality, model="unknown",
                     engg="backend", org="platform", industry="ott", phase="build"):
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (story_id, agent, model, engg, org, industry, phase, "auto", quality, quality),
    )


def test_build_the_base_agent_quotas_table_and_wi_table_exists_with_quota_types_and_unit(
    tmp_path, monkeypatch
):
    """agent_quotas exists with 5h/daily/weekly/monthly (+hourly) and unit column."""
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    conn = sl._get_db()
    cols = {row[1]: row[2] for row in conn.execute("PRAGMA table_info(agent_quotas)")}
    conn.close()

    for required in (
        "agent", "model", "quota_type", "unit",
        "limit_tokens", "used_tokens", "reset_at", "updated_at",
    ):
        assert required in cols, f"missing column {required}"

    # Insert every plan-driven window + both units
    for qtype in ("5h", "hourly", "daily", "weekly", "monthly"):
        sl._upsert_agent_quota("claude", qtype, limit_tokens=100_000, used_tokens=10,
                               model="claude-sonnet-4-6", unit="tokens")
    sl._upsert_agent_quota(
        "claude", "daily", limit_tokens=50, used_tokens=5,
        model="claude-sonnet-4-6", unit="requests",
    )

    conn = sl._get_db()
    types = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT quota_type FROM agent_quotas WHERE agent='claude'"
        )
    }
    units = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT unit FROM agent_quotas WHERE agent='claude'"
        )
    }
    row = conn.execute(
        "SELECT limit_tokens, used_tokens, unit FROM agent_quotas "
        "WHERE agent='claude' AND quota_type='5h' AND unit='tokens'"
    ).fetchone()
    conn.close()

    assert types == {"5h", "hourly", "daily", "weekly", "monthly"}
    assert units == {"tokens", "requests"}
    assert row == (100_000, 10, "tokens")
    assert sl._quota_headroom(100_000, 10) == 99_990


def test_build_the_base_agent_quotas_table_and_wi_unit_requests_unifies_config_limit_requests(
    tmp_path, monkeypatch
):
    """unit=requests and config budget.limit_requests share one headroom model."""
    import json
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 10},
    }))
    # 8 prior exec events → 2 request headroom left at project level
    (tmp_path / ".synlynk" / "telemetry.json").write_text(json.dumps(
        [{"type": "exec"} for _ in range(8)]
    ))

    project_q = sl._project_request_quota_from_config()
    assert project_q is not None
    assert project_q["unit"] == "requests"
    assert project_q["limit_tokens"] == 10
    assert project_q["used_tokens"] == 8
    assert project_q["headroom"] == 2

    conn = sl._get_db()
    # Agent-level request quota is the precise gate when present
    sl._upsert_agent_quota(
        "codex", "daily", limit_tokens=5, used_tokens=5,
        unit="requests", conn=conn,
    )
    conn.commit()
    exhausted = sl._quota_status_for_agent(conn, "codex", estimated_requests=1)
    ok_agent = sl._quota_status_for_agent(conn, "agy", estimated_requests=1)
    conn.close()

    assert exhausted["status"] == "exhausted"
    assert exhausted["unit"] == "requests"
    # No agent rows for agy → falls back to project limit_requests (headroom 2)
    assert ok_agent["status"] == "ok"
    assert ok_agent["unit"] == "requests"
    assert ok_agent["headroom"] == 2


def test_build_the_base_agent_quotas_table_and_wi_routing_filters_exhausted_quota(
    tmp_path, monkeypatch
):
    """Stage 2 is a real gate: highest capability loses when quota is exhausted."""
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    # Disable project request floor so only agent_quotas rows decide
    monkeypatch.setattr(
        sl, "_project_request_quota_from_config", lambda: None
    )

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-quota-1", "Quota gate", "backend", "platform", "ott", "build", 40_000),
    )
    _seed_capability(conn, "story-quota-1", "gemini", 9.0, model="gemini-2.5-pro")
    _seed_capability(conn, "story-quota-1", "claude", 6.0, model="claude-sonnet-4-6")
    # gemini has more capability but only 12K headroom; story needs 40K
    sl._upsert_agent_quota(
        "gemini", "hourly", limit_tokens=50_000, used_tokens=38_000,
        model="gemini-2.5-pro", unit="tokens", conn=conn,
    )
    sl._upsert_agent_quota(
        "claude", "5h", limit_tokens=200_000, used_tokens=10_000,
        model="claude-sonnet-4-6", unit="tokens", conn=conn,
    )
    conn.commit()
    conn.close()

    assert sl._best_agent_for_story("story-quota-1") == "claude"


def test_build_the_base_agent_quotas_table_and_wi_routing_degraded_mode_does_not_hard_block(
    tmp_path, monkeypatch
):
    """When quota can't be read / has no rows, route conservatively — do not hard-block."""
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-quota-2", "Degraded", "backend", "platform", "ott", "build", 10_000),
    )
    _seed_capability(conn, "story-quota-2", "gemini", 9.0, model="gemini-2.5-pro")
    _seed_capability(conn, "story-quota-2", "claude", 6.0, model="claude-sonnet-4-6")
    # Only claude has a readable quota row; gemini has none → degraded/unknown
    sl._upsert_agent_quota(
        "claude", "daily", limit_tokens=100_000, used_tokens=0,
        unit="tokens", conn=conn,
    )
    conn.commit()

    status_gemini = sl._quota_status_for_agent(conn, "gemini", estimated_tokens=10_000)
    status_claude = sl._quota_status_for_agent(conn, "claude", estimated_tokens=10_000)
    conn.close()

    assert status_gemini["status"] == "unknown"
    assert status_gemini["degraded"] is True
    assert status_claude["status"] == "ok"
    assert status_claude["degraded"] is False

    # Conservative: prefer known-headroom claude over higher-scoring unknown gemini
    assert sl._best_agent_for_story("story-quota-2") == "claude"

    # Unreadable table path: still must not hard-block (return a candidate)
    monkeypatch.setattr(sl, "_read_agent_quota_rows", lambda conn, agent: None)
    # With both unknown/degraded, fall back to capability ranking → gemini
    assert sl._best_agent_for_story("story-quota-2") == "gemini"


def test_build_the_base_agent_quotas_table_and_wi_cost_tiebreak_when_capability_close(
    tmp_path, monkeypatch
):
    """Stage 3: when capability gap <= 0.15, pick the cheaper model."""
    import synlynk as sl

    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-quota-3", "Cost tie", "backend", "platform", "ott", "build", 20_000),
    )
    # opus is slightly higher score but much more expensive than sonnet
    _seed_capability(conn, "story-quota-3", "claude-opus", 8.10, model="claude-opus-4-8")
    _seed_capability(conn, "story-quota-3", "claude", 8.00, model="claude-sonnet-4-6")
    for agent, model in (
        ("claude-opus", "claude-opus-4-8"),
        ("claude", "claude-sonnet-4-6"),
    ):
        sl._upsert_agent_quota(
            agent, "daily", limit_tokens=500_000, used_tokens=0,
            model=model, unit="tokens", conn=conn,
        )
    conn.commit()
    conn.close()

    assert sl._best_agent_for_story("story-quota-3") == "claude"
