import sqlite3
import subprocess
import re
import os
import stat
import copy
import time

import pytest

from synlynk.agent_cli import SEED_CHARTERS


def test_fixdispatch_deduplicate_boolean_cli_flag():
    from synlynk.dispatch import _deduplicate_boolean_cli_flags

    flags = _deduplicate_boolean_cli_flags(
        ["--always-approve", "--always-approve", "--allow", "Read", "--allow", "Write"]
    )

    assert flags.count("--always-approve") == 1
    assert flags[-4:] == ["--allow", "Read", "--allow", "Write"]


def test_config_add_grok_to_agent_slots_in_synlynk_and_default_config_templates(tmp_path, monkeypatch):
    import json
    import synlynk
    from synlynk.instructions import _build_templates
    from synlynk.doctor import _hc_agent_profiles

    monkeypatch.chdir(tmp_path)
    # 1. Verify load_config defaults contain all 4 Core Fleet agent slots
    cfg = synlynk.load_config()
    assert "agent_slots" in cfg
    assert cfg["agent_slots"] == {
        "claude": "claude",
        "agy": "agy",
        "codex": "codex",
        "grok": "grok",
    }

    # 2. Verify _build_templates() config.json contains all 4 Core Fleet agent slots
    templates = _build_templates()
    assert "config.json" in templates
    tpl_cfg = json.loads(templates["config.json"])
    assert "agent_slots" in tpl_cfg
    assert tpl_cfg["agent_slots"] == {
        "claude": "claude",
        "agy": "agy",
        "codex": "codex",
        "grok": "grok",
    }

    # 3. Verify doctor agent_profiles check recognizes grok in agent_slots
    (tmp_path / ".agents").mkdir(parents=True, exist_ok=True)
    for agent in ["claude", "agy", "codex", "grok"]:
        (tmp_path / ".agents" / f"{agent}.json").write_text("{}")
    res = _hc_agent_profiles()
    assert res.status == "ok"
    assert "grok" in res.message


def test_codex_harness_baseline_includes_verifier_role_and_can_gh_write():
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    codex = HARNESS_CAPABILITY_BASELINES["codex"]
    assert "verifier" in codex["roles"]
    assert codex["can_gh_write"] is True


def test_cli_detect_and_warn_on_stale_pipxinstall(tmp_path, monkeypatch, capsys):
    from synlynk import cli

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "synlynk"\n')
    (tmp_path / "VERSION").write_text("0.19.0\n")
    monkeypatch.chdir(tmp_path)

    cli._warn_stale_repo_version("0.18.0")

    warning = capsys.readouterr().err
    assert "installed synlynk 0.18.0 is behind this repository's VERSION 0.19.0" in warning
    assert "pipx install --force" in warning


def test_cli_does_not_warn_when_repo_version_is_not_newer(tmp_path, monkeypatch, capsys):
    from synlynk import cli

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "synlynk"\n')
    (tmp_path / "VERSION").write_text("0.18.0\n")
    monkeypatch.chdir(tmp_path)

    cli._warn_stale_repo_version("0.18.0")

    assert capsys.readouterr().err == ""


def test_claude_harness_alignment_update_baseline():
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    claude = HARNESS_CAPABILITY_BASELINES["claude"]
    assert claude["roles"] == ["architect", "pm"]
    assert "builder" not in claude["roles"]


def test_harden_harness_instructions_to_prohibit_direct_todo_edits():
    from synlynk.instructions import (
        _build_templates,
        _build_cursor_mdc,
        _build_copilot_instructions,
        _build_windsurf_rules,
    )

    templates_dict = _build_templates()
    templates = [
        templates_dict["CLAUDE.md"],
        templates_dict["GEMINI.md"],
        templates_dict["AGENTS.md"],
        templates_dict["GROK.md"],
        templates_dict["AI_INSTRUCTIONS.md"],
        _build_cursor_mdc(),
        _build_copilot_instructions(),
        _build_windsurf_rules(),
    ]

    for tmpl in templates:
        assert "[ ] active" not in tmpl
        assert "Update task status in project-docs/todo.md" not in tmpl
        assert "Update task status in `project-docs/todo.md`" not in tmpl
        if "todo.md" in tmpl:
            assert "state.db" in tmpl
            assert "synlynk story done" in tmpl or "synlynk checkpoint" in tmpl


def test_wire_charter_content_into_dispatchexecut(project_dir, tmp_path, monkeypatch):
    import synlynk
    from synlynk import agent_store
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(os.path, "expanduser", lambda path: path.replace("~", str(tmp_path / "fake_home")))
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary",
        "---\nschema_version: 1\nrole: pm\ndescription: test\n"
        "durability: dispatch-only\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nCharter injection regression.\n\n"
        "## Authority & Escalation\n\nEscalates per policy.\n\n"
        "## Workflow Ownership\n\nOwns this test.\n",
        actor="test", parent_revision=0,
    )
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None)
    monkeypatch.setattr(synlynk, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(synlynk, "set_state", lambda *a, **kw: None)
    monkeypatch.setattr(synlynk, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda *a, **kw: None)
    monkeypatch.setattr(synlynk, "check_sentinel_patterns", lambda **kw: None)
    monkeypatch.setattr(synlynk, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(synlynk, "WatchDaemon", None)
    monkeypatch.setattr(synlynk, "update_costs", lambda *a, **kw: None)
    monkeypatch.setattr(synlynk, "load_config", lambda: {"fenced_commands": []})

    exec_command(["echo", "hi"])
    context_text = (project_dir / ".synlynk" / "context.md").read_text()
    assert "## Role Charter" in context_text
    assert "Charter injection regression." in context_text


def _quiet_checkpoint(monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "_check_upstream_divergence", lambda: None)
    monkeypatch.setattr(synlynk, "_archive_old_devlog_entries", lambda *args: None)
    monkeypatch.setattr(synlynk, "generate_context", lambda: None)
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda event: None)
    monkeypatch.setattr(synlynk.WatchDaemon, "_is_running", lambda self: False)
    monkeypatch.setattr(synlynk, "parse_costs_md", lambda: (0.0, 0))


def test_fix_checkpoint_todomd_handling_it_bypass_migrated_archives_and_regenerates(
    project_dir, monkeypatch
):
    import synlynk

    db_path = project_dir / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    (project_dir / ".synlynk" / ".synlynk_migrated").touch()
    generated_todo = project_dir / ".synlynk" / "project-docs" / "todo.md"
    generated_todo.parent.mkdir(parents=True)
    generated_todo.write_text("# generated\n")
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [x] legacy wrong path <!-- id: story-wrong -->\n"
    )
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES (?, ?, ?)",
        ("story-done", "Finished work", "done"),
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, status) VALUES (?, ?, ?)",
        ("story-open", "Still active", "open"),
    )
    conn.commit()
    conn.close()
    _quiet_checkpoint(monkeypatch)

    synlynk.checkpoint()

    conn = synlynk._get_db()
    rows = conn.execute(
        "SELECT story_id, archived_at FROM stories ORDER BY story_id"
    ).fetchall()
    conn.close()
    assert rows[0][1] is not None
    assert rows[1][1] is None
    assert "Finished work" not in generated_todo.read_text()
    assert "Still active" in generated_todo.read_text()
    assert "legacy wrong path" in (project_dir / "project-docs" / "todo.md").read_text()


def test_fix_checkpoint_todomd_handling_it_bypass_pre_migration_backfill_is_idempotent(
    project_dir, monkeypatch
):
    import synlynk

    db_path = project_dir / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(db_path))
    (project_dir / "project-docs" / "todo.md").write_text(
        "- [x] Finished legacy work <!-- id: story-legacy -->\n"
        "- [ ] Current legacy work <!-- id: story-current -->\n"
    )
    _quiet_checkpoint(monkeypatch)

    synlynk.checkpoint()
    synlynk.checkpoint()

    conn = synlynk._get_db()
    rows = conn.execute(
        "SELECT story_id, status, archived_at FROM stories ORDER BY story_id"
    ).fetchall()
    conn.close()
    assert rows[0][:2] == ("story-current", "open")
    assert rows[0][2] is None
    assert rows[1][:2] == ("story-legacy", "done")
    assert rows[1][2] is not None


def test_fix_checkpoint_todomd_handling_it_bypass_has_no_literal_todo_path():
    import inspect
    import synlynk

    source = inspect.getsource(synlynk.checkpoint)
    assert not re.search(r"todo_path\\s*=", source)


def test_macos_launchd_daemon_service_has_keepalive_successful_exit_dict(
    project_dir, monkeypatch
):
    import synlynk
    import plistlib

    monkeypatch.setenv("HOME", str(project_dir))
    monkeypatch.setattr(synlynk.sys, "platform", "darwin")
    monkeypatch.setattr(
        synlynk.shutil,
        "which",
        lambda name: "/usr/local/bin/synlynk" if name == "synlynk" else None,
    )
    monkeypatch.setattr(synlynk.os, "makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        synlynk.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
    )

    launchagents_dir = project_dir / "Library" / "LaunchAgents"
    launchagents_dir.mkdir(parents=True, exist_ok=True)

    synlynk._daemon_install_service(object())

    plist = (launchagents_dir / "com.synlynk.daemon.plist").read_text()
    assert plistlib.loads(plist.encode())["KeepAlive"] == {"SuccessfulExit": False}
    assert "<key>KeepAlive</key>\n    <false/>" not in plist


def test_jobs_all_crashes_typeerror_comparing_offset_naive_and_aware(monkeypatch):
    from synlynk.gh_verify import gh_write_verified

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout='{"reviews":[{"submittedAt":"2026-08-18T11:00:00Z"}]}',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh_write_verified(
        "pr:1038", expect="review_posted", since="2026-08-18T10:00:00"
    ) is True


def test_job_status_daemon_jobs_sqlite_and_jobsjs(project_dir, capsys):
    """A terminal jobs.json event repairs a stale daemon_jobs running row."""
    import synlynk as sl

    job_id = "job-split-brain-1383"
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, status, pid, enqueued_at, started_at) "
        "VALUES (?, ?, ?, 'running', ?, ?, ?)",
        (job_id, "codex", "finish the GitHub write", 999999,
         "2026-09-04T10:00:00", "2026-09-04T10:00:00"),
    )
    conn.commit()
    conn.close()
    sl._save_jobs([{
        "id": job_id,
        "agent": "codex",
        "task": "finish the GitHub write",
        "status": "completed",
        "exit_code": 0,
        "started_at": "2026-09-04T10:00:00",
        "ended_at": "2026-09-04T10:01:00",
    }])

    sl.cmd_jobs(all_jobs=True)
    out = capsys.readouterr().out

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code, completed_at FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("done", 0, "2026-09-04T10:01:00")
    assert job_id in out
    assert "done" in out


test_fix_reconcile_terminal_jobs_across_sqlite = test_job_status_daemon_jobs_sqlite_and_jobsjs


@pytest.mark.skipif(
    not os.environ.get("SYNLYNK_LIVE_GH_WRITE_ISSUE"),
    reason="set SYNLYNK_LIVE_GH_WRITE_ISSUE to run the live GitHub-write integration test",
)
def test_job_status_daemon_jobs_sqlite_and_jobsjs_live_gh_write(project_dir, monkeypatch):
    """A real child gh write is reflected by ``synlynk jobs --all``."""
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.gh_verify import gh_write_verified

    target = int(os.environ["SYNLYNK_LIVE_GH_WRITE_ISSUE"])
    repo = os.environ.get("SYNLYNK_LIVE_GH_WRITE_REPO", "")
    script = project_dir / "live-gh-write"
    repo_arg = f" --repo {repo!r}" if repo else ""
    script.write_text(
        "#!/bin/sh\n"
        f"exec gh issue close {target}{repo_arg} --reason completed --yes\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    baseline = copy.deepcopy(dispatch_mod.HARNESS_CAPABILITY_BASELINES["codex"])
    baseline.update({"cli": str(script), "non_interactive_flags": [], "prompt_file_flag": None,
                     "prompt_via_arg": False, "prompt_flag": None})
    monkeypatch.setitem(dispatch_mod.HARNESS_CAPABILITY_BASELINES, "codex", baseline)
    job = dispatch_mod.dispatch_agent(
        "codex", f"close issue #{target}", force_agent=True,
        requires_gh_write=True, issue=target, role="dev", skip_preflight=True,
        context_mode="none",
    )
    os.waitpid(job["pid"], 0)
    sl._reconcile_jobs()
    sl.cmd_jobs(all_jobs=True)

    assert gh_write_verified(f"issue:{target}", expect="closed") is True
    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, gh_write_verified FROM daemon_jobs WHERE job_id=?",
        (job["id"],),
    ).fetchone()
    conn.close()
    assert row == ("done", "true")


@pytest.mark.parametrize(
    "scenario",
    ["pr_open", "killed_zombie", "timed_out", "review_posted"],
)
def test_job_status_add_realghwrite_endtoend_regr(project_dir, monkeypatch, capsys, scenario):
    """A real child gh write has one truth in every terminalization path (#1414).

    The fake gh binary is an in-process CI substitute for GitHub: writes update a
    durable state file and reads return that state.  The harness and gh commands
    still run as real child processes, so this covers dispatch, child exit, GTV,
    verification, daemon_jobs, jobs.json, and the jobs CLI together.
    """
    import datetime
    import json
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    import synlynk.jobs as jobs_mod

    state_path = project_dir / "fake-github.json"
    state_path.write_text(json.dumps({"written": False, "state": "OPEN", "reviews": []}))
    fake_bin = project_dir / "fake-bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\n"
        "import datetime, json, os, sys\n"
        "path = os.environ['SYNLYNK_FAKE_GH_STATE']\n"
        "with open(path) as f: state = json.load(f)\n"
        "args = sys.argv[1:]\n"
        "if len(args) >= 2 and args[1] in ('close', 'create', 'review'):\n"
        "    state['written'] = True\n"
        "    state['action'] = args[1]\n"
        "    if args[1] == 'close': state['state'] = 'CLOSED'\n"
        "    elif args[1] == 'create': state['state'] = 'OPEN'\n"
        "    else: state['reviews'] = [{'submittedAt': (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat(), 'author': {'login': 'test-bot'}}]\n"
        "    with open(path, 'w') as f: json.dump(state, f)\n"
        "    raise SystemExit(0)\n"
        "if len(args) >= 4 and args[1] == 'view':\n"
        "    field = args[4]\n"
        "    print(json.dumps({field: state.get(field, state.get('state'))}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit('unsupported fake gh command: ' + repr(args))\n"
    )
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)

    commands = {
        "pr_open": ["pr", "create", "--title", "#1414 regression"],
        "killed_zombie": ["issue", "close", "1414", "--yes"],
        "timed_out": ["issue", "close", "1414", "--yes"],
        "review_posted": ["pr", "review", "1414", "--approve"],
    }
    harness = project_dir / "fake-harness"
    harness.write_text(
        "#!/usr/bin/env python3\n"
        "import os, subprocess\n"
        f"raise SystemExit(subprocess.run(['gh'] + {commands[scenario]!r}).returncode)\n"
    )
    harness.chmod(harness.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("SYNLYNK_FAKE_GH_STATE", str(state_path))
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ["PATH"])

    baseline = copy.deepcopy(dispatch_mod.HARNESS_CAPABILITY_BASELINES["codex"])
    baseline.update({
        "cli": str(harness), "non_interactive_flags": [],
        "prompt_file_flag": None, "prompt_via_arg": False, "prompt_flag": None,
        "env_passthrough": ["SYNLYNK_FAKE_GH_STATE"],
    })
    monkeypatch.setitem(dispatch_mod.HARNESS_CAPABILITY_BASELINES, "codex", baseline)
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_bot_login", lambda role: "test-bot")

    target_kind = "pr" if scenario in ("pr_open", "review_posted") else "issue"
    task = "open PR #1414" if scenario == "pr_open" else (
        "post a review on PR #1414" if scenario == "review_posted" else "close issue #1414"
    )
    job = dispatch_mod.dispatch_agent(
        "codex", task, force_agent=True, requires_gh_write=True, issue=1414,
        gh_write_target_kind=target_kind, role="dev", skip_preflight=True,
        context_mode="none",
    )

    # The dispatch return only means the child was started.  Reap the actual child
    # without relying on Python 3.9's os.waitstatus_to_exitcode or an unbounded
    # blocking wait on a loaded CI runner.
    wait_deadline = time.monotonic() + 30
    while True:
        waited_pid, wait_status = os.waitpid(job["pid"], os.WNOHANG)
        if waited_pid == job["pid"]:
            break
        remaining = wait_deadline - time.monotonic()
        if remaining <= 0:
            pytest.fail(f"child process {job['pid']} did not exit within 30 seconds")
        time.sleep(min(0.05, remaining))
    assert os.WIFEXITED(wait_status), f"child process {job['pid']} did not exit cleanly"
    assert os.WEXITSTATUS(wait_status) == 0
    truth = json.loads(state_path.read_text())
    assert truth["written"] is True, f"fake GitHub ground truth did not record {scenario}"
    if scenario == "pr_open":
        assert truth["state"] == "OPEN"
    elif scenario in ("killed_zombie", "timed_out"):
        assert truth["state"] == "CLOSED"
    else:
        assert truth["reviews"] and truth["reviews"][0]["author"]["login"] == "test-bot"

    conn = sl._get_db()
    if scenario == "killed_zombie":
        worktree = project_dir / "leaked-worktree"
        (worktree / ".git").mkdir(parents=True)
        monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
        monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *args: str(worktree))
        monkeypatch.setattr(jobs_mod, "_reap_zombie_worktree", lambda *args: True)
        monkeypatch.setattr(sl, "_inspect_worktree_git_state", lambda *args, **kwargs: {
            "has_activity": False, "remote_has_activity": False,
            "changed_files": [], "remote_files_touched": [],
        })
        conn.execute("UPDATE daemon_jobs SET status='running', pid=? WHERE job_id=?", (999999, job["id"]))
    elif scenario == "timed_out":
        conn.execute("UPDATE daemon_jobs SET status='running', pid=NULL WHERE job_id=?", (job["id"],))
        exit_marker = str(job["log_file"]) + ".exit"
        if os.path.exists(exit_marker):
            os.unlink(exit_marker)
    conn.commit()
    conn.close()

    # This is the product surface under test: it reconciles before rendering.
    sl.cmd_jobs(all_jobs=True)
    output = capsys.readouterr().out
    assert job["id"] in output
    assert "done" in output

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code, gh_write_verified FROM daemon_jobs WHERE job_id=?",
        (job["id"],),
    ).fetchone()
    conn.close()
    assert row == ("done", 0, "true"), f"daemon_jobs disagrees with GitHub for {scenario}: {row}"
    projection = next(item for item in sl._load_jobs() if item["id"] == job["id"])
    assert projection["status"] == "running"

    # Exercise the #1388 convergence event after each terminal path.  A terminal
    # jobs.json event must repair a deliberately stale SQLite row and remain done.
    projection.update({"status": "completed", "exit_code": 0,
                       "ended_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")})
    sl._save_jobs([projection])
    conn = sl._get_db()
    conn.execute("UPDATE daemon_jobs SET status='running' WHERE job_id=?", (job["id"],))
    conn.commit()
    conn.close()
    sl.cmd_jobs(all_jobs=True)
    conn = sl._get_db()
    assert conn.execute("SELECT status FROM daemon_jobs WHERE job_id=?", (job["id"],)).fetchone()[0] == "done"
    conn.close()
    assert next(item for item in sl._load_jobs() if item["id"] == job["id"])["status"] == "completed"


def test_codex_dispatch_workspacewrite_sandbox_bl_network_permission_adds_override():
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("codex", ["read:*", "run:install"])

    assert flags[-2:] == ["-c", "sandbox_workspace_write.network_access=true"]


def test_codex_dispatch_workspacewrite_sandbox_bl_without_network_permission_is_safe():
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("codex", ["read:*"])

    assert flags == ["-s", "read-only"]
    assert "--ask-for-approval" not in flags
    assert "sandbox_workspace_write.network_access=true" not in flags


def test_codex_dispatch_fails_hardcoded_approval_flag_is_not_emitted():
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("codex", ["read:*"])

    assert flags == ["-s", "read-only"]
    assert "--ask-for-approval" not in flags


def test_codex_dispatch_with_network_permission_does_not_emit_read_only_sandbox():
    from synlynk._constants import _CODEX_NETWORK_PERMISSION
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("codex", ["read:*", _CODEX_NETWORK_PERMISSION])
    assert "-s" not in flags
    assert "read-only" not in flags
    assert flags == ["-c", "sandbox_workspace_write.network_access=true"]


def test_codex_dispatch_effective_grants_includes_network_permission_on_gh_write():
    from synlynk._constants import _CODEX_NETWORK_PERMISSION
    from synlynk.dispatch import _permissions_to_flags, _resolve_dispatch_permissions

    agent = "codex"
    requires_gh_write = True
    effective_grants = []
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)

    perms = _resolve_dispatch_permissions(agent, role_list=["builder"], grants=effective_grants)
    assert _CODEX_NETWORK_PERMISSION in perms

    flags = _permissions_to_flags(agent, perms)
    assert flags[-2:] == ["-c", "sandbox_workspace_write.network_access=true"]


def test_codex_dispatch_effective_grants_omits_network_permission_when_gh_write_false():
    from synlynk._constants import _CODEX_NETWORK_PERMISSION
    from synlynk.dispatch import _permissions_to_flags, _resolve_dispatch_permissions

    agent = "codex"
    requires_gh_write = False
    effective_grants = []
    if requires_gh_write:
        if "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
            effective_grants.append(_CODEX_NETWORK_PERMISSION)

    perms = _resolve_dispatch_permissions(agent, role_list=["builder"], grants=effective_grants)
    assert _CODEX_NETWORK_PERMISSION not in perms

    flags = _permissions_to_flags(agent, perms)
    assert "sandbox_workspace_write.network_access=true" not in flags


def test_execute_the_implementation_plan_at_docssuperpowersplans_codex_requires_gh_write_appends_network_access_flag(
    project_dir, monkeypatch
):
    import synlynk.dispatch as dispatch_mod

    recorded_shell = []

    def fake_popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == "sh":
            recorded_shell.append(cmd[2])
        return type("DummyProc", (), {"pid": 9999})()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "fake-token")
    monkeypatch.setattr(dispatch_mod, "_gh_write_allow_host_auth", lambda: True)

    dispatch_mod.dispatch_agent(
        agent="codex",
        task="gh pr review 123 --comment -b test",
        requires_gh_write=True,
        role="qa",
        force_agent=True,
        skip_preflight=True,
        context_mode="none",
    )

    assert len(recorded_shell) == 1
    assert "-c sandbox_workspace_write.network_access=true" in recorded_shell[0]


def test_pm_charter_includes_competitive_sweep_responsibility():
    assert "competitive-intelligence sweep" in SEED_CHARTERS["pm"]
    assert "capability/marketing-gap comparison doc" in SEED_CHARTERS["pm"]


def test_prevent_global_state_db_corruption_from_worktree(tmp_path, monkeypatch):
    import synlynk

    shared = tmp_path / "home" / ".synlynk" / "projects" / "shared" / "state.db"
    isolated = tmp_path / "isolated" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(shared))
    monkeypatch.setattr(synlynk, "_INITIAL_GIT_WORKTREE", True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(synlynk, "_resolve_db_path", lambda: str(shared))
    monkeypatch.setattr(synlynk, "_test_isolation_db_path", lambda: str(isolated))

    conn = synlynk._get_db()
    conn.close()
    assert isolated.exists()
    assert not shared.exists()


def test_prevent_global_state_db_corruption_from_non_worktree_keeps_shared_path(tmp_path, monkeypatch):
    import synlynk

    shared = tmp_path / "shared" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(shared))
    monkeypatch.setattr(synlynk, "_resolve_db_path", lambda: str(shared))
    monkeypatch.setattr(synlynk, "_INITIAL_GIT_WORKTREE", False)

    conn = synlynk._get_db()
    conn.close()
    assert shared.exists()


def test_prevent_global_state_db_corruption_from_migration_snapshot(tmp_path):
    from synlynk.db import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE legacy (payload TEXT)")
    conn.execute("INSERT INTO legacy VALUES (?)", ("x" * 8192,))
    conn.commit()

    _migrate_db(conn)
    conn.close()

    snapshots = list(tmp_path.glob("state.db.pre-migration-*.bak"))
    assert len(snapshots) == 1
    assert snapshots[0].stat().st_size >= 4096


def test_live5__migrate_db_copies_the_entire_state_db_only_once(tmp_path):
    from synlynk.db import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE legacy (payload TEXT)")
    conn.execute("INSERT INTO legacy VALUES (?)", ("x" * 8192,))
    conn.commit()

    _migrate_db(conn)
    before = len(list(tmp_path.glob("state.db.pre-migration-*.bak")))
    _migrate_db(conn)
    after = len(list(tmp_path.glob("state.db.pre-migration-*.bak")))

    assert before == 1
    assert after == before


def test_live5__migrate_db_skips_work_on_already_migrated_connection(tmp_path, monkeypatch):
    from synlynk import db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE legacy (payload TEXT)")
    conn.execute("INSERT INTO legacy VALUES (?)", ("x" * 8192,))
    conn.commit()

    db._migrate_db(conn)
    conn.close()

    def fail_if_called(_conn):
        raise AssertionError("migration work ran for an already-migrated database")

    monkeypatch.setattr(db, "_run_harness_rename_migration", fail_if_called)
    second_conn = sqlite3.connect(db_path)
    db._migrate_db(second_conn)
    second_conn.close()


def test_live5__harness_rename_is_safe_when_both_reservation_tables_exist():
    from synlynk.db import _run_harness_rename_migration

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE agent_reservations (id INTEGER PRIMARY KEY, harness TEXT, status TEXT);
        CREATE TABLE harness_reservations (id INTEGER PRIMARY KEY, harness TEXT, status TEXT);
        """
    )

    _run_harness_rename_migration(conn)


def test_live5__harness_quotas_rename_is_safe_when_target_table_exists():
    from synlynk.db import _run_harness_rename_migration

    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE agent_quotas (agent TEXT PRIMARY KEY, quota INTEGER);
        CREATE TABLE harness_quotas (harness TEXT PRIMARY KEY, quota INTEGER);
        INSERT INTO agent_quotas VALUES ('legacy', 1);
        INSERT INTO harness_quotas VALUES ('current', 2);
        """
    )

    _run_harness_rename_migration(conn)

    assert conn.execute("SELECT * FROM agent_quotas").fetchone() == ("legacy", 1)
    assert conn.execute("SELECT * FROM harness_quotas").fetchone() == ("current", 2)


def test_fixevents_subscriptions_table_missing_harness_name_migration(project_dir):
    import synlynk
    from synlynk.db import _run_harness_rename_migration
    from synlynk.events import scan_local_events
    from unittest.mock import MagicMock, patch

    conn = sqlite3.connect(synlynk.DB_PATH)
    conn.execute(
        """
        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            last_seen_event_id INTEGER NOT NULL DEFAULT 0,
            UNIQUE(agent_name, event_type)
        )
        """
    )
    conn.execute(
        "INSERT INTO subscriptions (agent_name, event_type, last_seen_event_id) VALUES (?, ?, ?)",
        ("some-harness-name", "cron_heartbeat", 0),
    )
    conn.commit()
    _run_harness_rename_migration(conn)
    conn.commit()
    conn.close()

    with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="[]")):
        scan_local_events("some-harness-name")


def test_live5__migrate_db_older_schema_creates_one_backup(tmp_path):
    from synlynk.db import _migrate_db

    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE old_state (payload TEXT)")
    conn.execute("INSERT INTO old_state VALUES (?)", ("x" * 8192,))
    conn.commit()

    _migrate_db(conn)

    assert len(list(tmp_path.glob("state.db.pre-migration-*.bak"))) == 1


SEED_ROLES = ["dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot"]


def test_cmd_agent_init_creates_registry_entry_and_charter(project_dir):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")

    agents = agent_store.list_agents()
    assert len(agents) == 1
    assert agents[0]["agent_id"] == agent_id
    assert {"kind": "role_slug", "value": "dev"} in agents[0]["aliases"]

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 1
    assert content == agent_cli.SEED_CHARTERS["dev"]


def test_cmd_agent_init_rejects_duplicate_role(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_init("dev")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "already has an agent" in captured.err or "already has an agent" in captured.out


def test_cmd_agent_list_empty(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "No agents registered" in captured.out


def test_cmd_agent_list_shows_all_agents(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    agent_cli.cmd_agent_init("qa")
    capsys.readouterr()

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "dev" in captured.out
    assert "qa" in captured.out
    assert "active" in captured.out


def test_cmd_agent_show_resolves_by_full_id(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show(agent_id)
    captured = capsys.readouterr()
    assert agent_id in captured.out
    assert "dev" in captured.out


def test_cmd_agent_show_resolves_by_alias(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show("dev")
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cmd_agent_show_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_show("nonexistent")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No agent found matching" in captured.err or "No agent found matching" in captured.out


def test_cmd_agent_edit_updates_charter(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    new_content = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "Implementation — writes the code, reviews own PRs."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\nUpdated instructions.\n\n"
        "## Authority & Escalation\n\nUpdated escalation.\n\n"
        "## Workflow Ownership\n\nUpdated ownership.\n"
    )
    charter_file = tmp_path / "new_charter.md"
    charter_file.write_text(new_content)

    agent_cli.cmd_agent_edit(agent_id, str(charter_file))

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert content == new_content


def test_cmd_agent_edit_stdin(project_dir, monkeypatch, capsys):
    import io
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    new_content = (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        'description: "New charter from stdin."\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n\n"
        "## Instructions\n\nFrom stdin.\n\n"
        "## Authority & Escalation\n\nFrom stdin.\n\n"
        "## Workflow Ownership\n\nFrom stdin.\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(new_content))
    agent_cli.cmd_agent_edit(agent_id, "-")

    content, revision = agent_store.read_charter(agent_id)
    assert content == new_content
    assert revision == 2


def test_cmd_agent_edit_stale_revision_exits_1(project_dir, tmp_path, monkeypatch, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    # cmd_agent_edit reads parent_revision fresh from read_charter() immediately
    # before writing, so it never observes a stale cached revision itself. The
    # only way to exercise its RevisionConflictError handling path is to force
    # the underlying store call to raise it directly, simulating a concurrent
    # writer winning the race between our read and our write.
    def _raise_conflict(*args, **kwargs):
        raise agent_store.RevisionConflictError("concurrent edit detected")

    monkeypatch.setattr(agent_store, "propose_charter_revision", _raise_conflict)

    charter_file = tmp_path / "stale.md"
    charter_file.write_text("stale content")

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_edit(agent_id, str(charter_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "updated by someone else" in captured.err or "updated by someone else" in captured.out


def test_cmd_agent_edit_rejects_invalid_charter_exits_1(project_dir, tmp_path, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    charter_file = tmp_path / "invalid.md"
    charter_file.write_text("not a valid charter, no frontmatter")

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_edit(agent_id, str(charter_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "failed validation" in captured.err


def test_cmd_agent_sync_routing_populates_dispatch_routing_for_dev(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_sync_routing(agent_id)

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert "dispatch_routing:" in content
    captured = capsys.readouterr()
    assert "Synced dispatch_routing" in captured.out


def test_cmd_agent_sync_routing_reports_noop_for_role_without_task_allocation(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("qa")
    capsys.readouterr()

    agent_cli.cmd_agent_sync_routing(agent_id)

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 1
    captured = capsys.readouterr()
    assert "nothing to sync" in captured.out


def test_cmd_agent_disable_sets_flag(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)

    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    assert entry["disabled"] is True


def test_cmd_agent_disable_idempotent(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)
    capsys.readouterr()
    agent_cli.cmd_agent_disable(agent_id)
    captured = capsys.readouterr()
    assert "already disabled" in captured.out


def test_cmd_agent_disable_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_disable("nonexistent")
    assert exc_info.value.code == 1


def test_cli_agent_init_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    captured = capsys.readouterr()
    assert "Created agent" in captured.out


def test_cli_agent_init_rejects_unknown_role(project_dir):
    from synlynk.cli import main

    with pytest.raises(SystemExit):
        main(["agent", "init", "not-a-real-role"])


def test_cli_agent_list_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "list"])
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cli_agent_show_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "show", "dev"])
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cli_agent_disable_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "disable", "dev"])
    captured = capsys.readouterr()
    assert "Disabled agent" in captured.out


def test_cli_agent_edit_requires_charter_flag(project_dir):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    with pytest.raises(SystemExit):
        main(["agent", "edit", "dev"])


def test_cli_dispatch_as_agent_resolves_alias(project_dir, monkeypatch, capsys):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    main(["agent", "init", "dev"])
    capsys.readouterr()

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["agent"] = agent
        captured["agent_id"] = kwargs.get("agent_id")
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.dispatch_agent", fake_dispatch_agent)

    main(["dispatch", "codex", "--task", "do work", "--as-agent", "dev"])

    assert captured["agent"] == "codex"
    assert captured["agent_id"] is not None


def test_cli_dispatch_as_agent_unresolvable_exits_1(project_dir):
    from synlynk.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["dispatch", "codex", "--task", "do work", "--as-agent", "nonexistent"])
    assert exc_info.value.code == 1


def test_cli_dispatch_as_agent_without_explicit_harness(project_dir, monkeypatch, capsys):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    main(["agent", "init", "dev"])
    capsys.readouterr()

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["agent"] = agent
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.dispatch_agent", fake_dispatch_agent)

    main(["dispatch", "--task", "do work", "--as-agent", "dev"])

    assert "agent" in captured


def test_cli_dispatch_infers_review_task_type_for_gh_write(project_dir, monkeypatch, capsys):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured.update(kwargs)
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.dispatch_agent", fake_dispatch_agent)

    main([
        "dispatch", "codex", "--task", "Post a GitHub PR review for PR #1164",
    ])
    captured_output = capsys.readouterr()

    assert captured["task_type"] == "review"
    assert captured["gh_write_target_kind"] == "pr"
    assert "inferred task_type=review" in captured_output.out


def test_cli_dispatch_explicit_task_type_and_non_review_gh_write_remain_unchanged(
    project_dir, monkeypatch, capsys
):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    calls = []

    def fake_dispatch_agent(agent, task, **kwargs):
        calls.append(kwargs)
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.dispatch_agent", fake_dispatch_agent)

    main([
        "dispatch", "codex", "--task", "review PR #1164", "--task-type", "review",
        "--requires-gh-write",
    ])
    capsys.readouterr()
    main([
        "dispatch", "codex", "--task", "Close issue #99 as duplicate",
        "--requires-gh-write",
    ])
    capsys.readouterr()

    assert calls[0]["task_type"] == "review"
    assert calls[0]["gh_write_target_kind"] == "pr"
    assert calls[1]["task_type"] is None
    assert calls[1]["gh_write_target_kind"] == "issue"


def test_job_status_propen_ghwrite_jobs_hardcode_pr_open_expectation(project_dir, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 1379

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "test-gh-token")
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_bot_login", lambda role: "test-bot")
    real_pkg = dispatch_mod._pkg
    monkeypatch.setattr(dispatch_mod, "_pkg", lambda name, default=None: (
        (lambda *a, **kw: "story-test")
        if name == "resolve_or_create_story_id" else real_pkg(name, default)
    ))

    job = dispatch_mod.dispatch_agent(
        "codex", "open a GitHub PR for the completed fix", force_agent=True,
        requires_gh_write=True, role="dev", issue=1375, gh_write_target_kind="pr",
        skip_preflight=True,
    )

    assert job["gh_write_target"] == "pr:1375"
    assert job["gh_write_expect"] == "pr_open"


def test_job_status_killed_zombie_hardcodes_failure_only_when_gh_write_unverified(
    project_dir, monkeypatch, tmp_path
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-killed-zombie-ghw"
    worktree = tmp_path / "worktree"
    (worktree / ".git").mkdir(parents=True)
    log_path = str(tmp_path / "job.log")
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target, gh_write_expect) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id, "codex", "open PR", "story-zombie", "running", 999999,
            "2026-09-04T00:00:00", "2026-09-04T00:00:01", log_path, 1,
            "pr:1384", "pr_open",
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "_daemon_job_worktree_path", lambda *a: str(worktree))
    monkeypatch.setattr(jobs_mod, "_reap_zombie_worktree", lambda *a: True)
    monkeypatch.setattr(
        sl,
        "_inspect_worktree_git_state",
        lambda *a, **kw: {
            "has_activity": False,
            "remote_has_activity": True,
            "remote_ref": "origin/dispatch/codex/" + job_id,
            "changed_files": [],
            "remote_files_touched": ["synlynk/jobs.py"],
        },
    )
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda target, expect, **kw: True)

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code, gh_write_verified FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("done", 0, "true")


def test_job_status_timed_out_is_finalized_before_exit_marker_gh_write_succeeds(
    project_dir, monkeypatch, tmp_path
):
    """A dead PID must not hide a successful GH write during the exit-file race (#1381)."""
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    job_id = "job-timed-out-ghw"
    log_path = str(tmp_path / "job.log")
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, pid, enqueued_at, "
        "started_at, log_path, requires_gh_write, gh_write_target, gh_write_expect) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id, "codex", "open PR", "story-timeout", "running", 999999,
            "2026-09-04T00:00:00", "2026-09-04T00:00:01", log_path, 1,
            "pr:1381", "pr_open",
        ),
    )
    conn.commit()
    conn.close()

    # The harness has died, but its shell wrapper has not written job.log.exit yet.
    monkeypatch.setattr(jobs_mod, "_pid_is_alive", lambda pid: False)
    monkeypatch.setattr(jobs_mod, "gh_write_verified", lambda target, expect, **kw: True)

    jobs_mod._reconcile_daemon_jobs()

    conn = sl._get_db()
    row = conn.execute(
        "SELECT status, exit_code, gh_write_verified FROM daemon_jobs WHERE job_id=?",
        (job_id,),
    ).fetchone()
    conn.close()
    assert row == ("done", 0, "true")


def test_cli_dispatch_dry_run_as_agent_without_explicit_harness_shows_resolved_agent(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "qa"])  # qa -> "verifier" -> agy (see _ORG_ROLE_TO_BASELINE_ROLE)
    capsys.readouterr()

    main(["dispatch", "--task", "run the test suite", "--as-agent", "qa", "--dry-run"])
    captured = capsys.readouterr()
    assert "agent:        agy" in captured.out


def _docs_keep_readme_synchronized_readme(
    root,
    version,
    test_count=None,
    extra="",
    stale_commands=False,
    test_wording="collected",
):
    from scripts.generate_command_docs import render_readme_section

    commands_md = root / "docs" / "reference" / "commands.md"
    commands_md.parent.mkdir(parents=True, exist_ok=True)
    commands_md.write_text("# Command Reference\n")
    section = (
        "<!-- commands:start -->\n\n- `synlynk init`\n\n<!-- commands:end -->"
        if stale_commands
        else render_readme_section()
    )
    test_badge = ""
    test_prose = ""
    if test_count is not None:
        test_badge = (
            f'  <a href="https://github.com/nikhilsoman/synlynk">'
            f'<img src="https://img.shields.io/badge/tests-{test_count}%20{test_wording}-brightgreen" '
            f'alt="Tests"></a>\n'
        )
        test_prose = f" {test_count} tests {test_wording}."
    (root / "README.md").write_text(
        f"""<p align="center">
{test_badge}  <a href="https://github.com/nikhilsoman/synlynk"><img src="https://img.shields.io/badge/version-{version}-blue" alt="Version"></a>
</p>

**v{version}:** Named release summary covering the README consistency gate.{test_prose}

## Install

```bash
pipx install git+https://github.com/nikhilsoman/synlynk
python3 bin/synlynk.py --help
```

## Commands

{section}

{extra}
"""
    )


def test_docs_keep_readme_synchronized_during_named_releases_flags_stale_version_and_test_count(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(tmp_path, "0.12.0", test_count=1140)
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=2316
    )
    by_check = {item.check: item.message for item in findings}
    test_count_blob = " ".join(
        item.message for item in findings if item.check == "test_count"
    )
    assert "version" in by_check
    assert "0.12.0" in by_check["version"]
    assert "0.18.0" in by_check["version"]
    assert "test_count" in by_check
    assert "1140" in test_count_blob
    assert "2316" in test_count_blob
    assert "not pass/fail" in test_count_blob or "collect-only" in test_count_blob


def test_docs_keep_readme_synchronized_during_named_releases_handles_planned_vs_shipped_commands(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path,
        "0.18.0",
        extra=(
            "Coming soon: `synlynk teleport` will ship in a later release.\n"
            "Use `synlynk teleport` today for faster clones.\n"
        ),
    )
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=0
    )
    command_findings = [item for item in findings if item.check == "commands"]
    assert command_findings, findings
    assert any("teleport" in item.message for item in command_findings)
    # The planned line must not be the only/extra failure — unmarked shipped claim is.
    assert all("coming soon" not in item.message.lower() for item in command_findings)


def test_docs_keep_readme_synchronized_during_named_releases_ignores_ordinary_prose(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path,
        "0.18.0",
        extra=(
            "synlynk is a Python CLI that turns your terminal into a hybrid workgroup.\n"
            "1. **Install synlynk globally:**\n"
            "If you installed synlynk before 2026-07, here's what's new.\n"
        ),
    )
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=0
    )
    command_findings = [item for item in findings if item.check == "commands"]
    assert command_findings == []
    joined = " ".join(item.message for item in findings)
    assert "is a Python CLI" not in joined
    assert "globally" not in joined
    assert "before" not in joined


def test_docs_keep_readme_synchronized_during_named_releases_normalizes_relative_root(
    tmp_path, monkeypatch
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path,
        "0.18.0",
        extra="See [CONTRIBUTING.md](CONTRIBUTING.md).\n",
    )
    (tmp_path / "CONTRIBUTING.md").write_text("# Contribute\n")
    monkeypatch.chdir(tmp_path)
    findings = validate_readme_for_release(".", "0.18.0", collected_test_count=0)
    assert not any("escapes repo" in item.message for item in findings)
    assert not any("missing path: CONTRIBUTING.md" in item.message for item in findings)


def test_docs_keep_readme_synchronized_during_named_releases_allows_github_relative_routes(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path,
        "0.18.0",
        extra=(
            "See the [Discussions](../../discussions) tab.\n"
            "Do not follow [escaped](../outside.md).\n"
        ),
    )
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=0
    )
    link_messages = [item.message for item in findings if item.check == "links"]
    assert not any("../../discussions" in msg for msg in link_messages)
    assert any("escapes repo root: ../outside.md" in msg for msg in link_messages)


def test_docs_keep_readme_synchronized_during_named_releases_rejects_passing_without_verified_run(
    tmp_path,
):
    from synlynk.release_readme import (
        format_readme_check_report,
        validate_readme_for_release,
    )

    _docs_keep_readme_synchronized_readme(
        tmp_path, "0.18.0", test_count=12, test_wording="passing"
    )
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=12
    )
    test_count_findings = [item for item in findings if item.check == "test_count"]
    assert test_count_findings, findings
    assert len(test_count_findings) == 1
    blob = " ".join(item.message for item in test_count_findings)
    assert "12" in blob
    assert "passing" in blob.lower()
    assert "collect-only" in blob
    report = format_readme_check_report(findings, "0.18.0")
    assert "pytest --collect-only" in report
    assert "passing" in report.lower()
    assert "[x] collected test count" not in report


def test_docs_keep_readme_synchronized_during_named_releases_accepts_collected_wording(
    tmp_path,
):
    from synlynk.release_readme import (
        format_readme_check_report,
        validate_readme_for_release,
    )

    _docs_keep_readme_synchronized_readme(
        tmp_path, "0.18.0", test_count=12, test_wording="collected"
    )
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=12
    )
    assert findings == []
    report = format_readme_check_report(findings, "0.18.0")
    assert "pytest --collect-only" in report
    assert "[x] collected test count" in report


def test_docs_keep_readme_synchronized_during_named_releases_accepts_verified_passing(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path, "0.18.0", test_count=12, test_wording="passing"
    )
    findings = validate_readme_for_release(
        str(tmp_path),
        "0.18.0",
        collected_test_count=12,
        verified_passing_count=12,
    )
    assert not any(item.check == "test_count" for item in findings), findings


def test_docs_keep_readme_synchronized_during_named_releases_rejects_stale_verified_passing(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path, "0.18.0", test_count=12, test_wording="passing"
    )
    findings = validate_readme_for_release(
        str(tmp_path),
        "0.18.0",
        collected_test_count=12,
        verified_passing_count=11,
    )
    blob = " ".join(item.message for item in findings if item.check == "test_count")
    assert "12" in blob
    assert "11" in blob
    assert "passing" in blob.lower()


def test_docs_keep_readme_synchronized_during_named_releases_records_waiver_not_version(
    tmp_path,
):
    from synlynk.release_readme import (
        format_readme_check_report,
        parse_waivers,
        validate_readme_for_release,
    )

    _docs_keep_readme_synchronized_readme(tmp_path, "0.12.0", test_count=1140)
    waivers = parse_waivers(
        ["test_count=collect unavailable in this environment", "version=leave badge"]
    )
    findings = validate_readme_for_release(
        str(tmp_path),
        "0.18.0",
        collected_test_count=2316,
        waivers=waivers,
    )
    assert any(item.check == "version" for item in findings)
    assert not any(item.check == "test_count" for item in findings)
    report = format_readme_check_report(findings, "0.18.0", waivers=waivers)
    assert "collect unavailable in this environment" in report
    assert "[waived]" in report
    assert "version cannot be waived" in report


def test_docs_keep_readme_synchronized_during_named_releases_blocks_release_cut(
    tmp_path, monkeypatch
):
    from synlynk import cmd_release

    (tmp_path / "VERSION").write_text("0.10.0\n")
    monkeypatch.chdir(tmp_path)
    _docs_keep_readme_synchronized_readme(tmp_path, "0.12.0", test_count=1140)
    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: b"")
    with pytest.raises(RuntimeError, match="README is not synchronized"):
        cmd_release(dry_run=False, role="pm")
    assert (tmp_path / "VERSION").read_text().strip() == "0.10.0"


def test_docs_keep_readme_synchronized_during_named_releases_check_docs_flag(
    tmp_path, monkeypatch
):
    from synlynk.cli import build_parser, main

    parser = build_parser()
    args = parser.parse_args(
        ["release", "--check-docs", "--waive", "test_count=manual recount pending"]
    )
    assert args.check_docs is True
    assert args.waive == ["test_count=manual recount pending"]

    (tmp_path / "VERSION").write_text("0.18.0\n")
    monkeypatch.chdir(tmp_path)
    _docs_keep_readme_synchronized_readme(tmp_path, "0.12.0")
    with pytest.raises(SystemExit) as exc:
        main(["release", "--check-docs"])
    assert exc.value.code == 1
    assert (tmp_path / "VERSION").read_text().strip() == "0.18.0"


def test_docs_keep_readme_synchronized_during_named_releases_passes_when_in_sync(
    tmp_path,
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(tmp_path, "0.18.0", test_count=12)
    findings = validate_readme_for_release(
        str(tmp_path), "0.18.0", collected_test_count=12
    )
    assert findings == []


def test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns(
    tmp_path, monkeypatch
):
    from synlynk.release_readme import validate_readme_for_release

    _docs_keep_readme_synchronized_readme(
        tmp_path,
        "0.18.0",
        test_count=2346,
        extra=(
            "synlynk is a Python CLI that turns your terminal into a hybrid workgroup.\n"
            "1. **Install synlynk globally:**\n"
            "See the [Discussions](../../discussions) tab.\n"
        ),
    )
    monkeypatch.chdir(tmp_path)
    findings = validate_readme_for_release(
        ".", "0.18.0", collected_test_count=9999
    )
    by_check = {}
    for item in findings:
        by_check.setdefault(item.check, []).append(item.message)
    assert by_check.get("version", []) == []
    test_count_blob = " ".join(by_check.get("test_count", []))
    assert "2346" in test_count_blob
    assert "9999" in test_count_blob
    assert "collect-only" in test_count_blob or "collected" in test_count_blob.lower()
    command_blob = " ".join(by_check.get("commands", []))
    assert "is a Python CLI" not in command_blob
    assert "globally" not in command_blob
    link_blob = " ".join(by_check.get("links", []))
    assert "escapes repo" not in link_blob
    assert "../../discussions" not in link_blob


def test_fix_1250_dispatch_job_summaries_silently_report_zero_files_touched(
    git_worktree_repo, monkeypatch, tmp_path
):
    import synlynk as sl
    from synlynk.dispatch import _job_worktree_details, _worktree_files_touched
    from tests.test_agy_dispatch_fix import _dispatch_git_worktree_job, _commit_worktree_files

    path, branch = _job_worktree_details("job-test1250", "codex")
    assert os.path.isabs(path)

    job = _dispatch_git_worktree_job(monkeypatch)
    _commit_worktree_files(job["worktree_path"], {"touched.txt": "content\n"}, "touch file")

    monkeypatch.chdir(tmp_path)
    assert os.path.isabs(job["worktree_path"])
    assert _worktree_files_touched(job["worktree_path"]) == ["touched.txt"]


def test_agy_headless_parity_pass_printtimeout_30(project_dir, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    recorded_shell = []

    def fake_popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == "sh":
            recorded_shell.append(cmd[2])
        return type("DummyProc", (), {"pid": 9999})()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)

    dispatch_mod.dispatch_agent(
        agent="agy",
        task="Audit codebase without write access",
        task_type="review",
        skip_preflight=True,
        context_mode="none",
    )

    assert len(recorded_shell) == 1
    assert "--print-timeout 30m0s" in recorded_shell[0]
    assert "--mode plan" in recorded_shell[0]


def test_dispatch_cli_force_harness_and_deprecated_force_agent():
    from synlynk.cli import build_parser

    parser = build_parser()
    args1 = parser.parse_args(["dispatch", "codex", "--task", "test", "--force-harness"])
    assert args1.force_agent is True

    args2 = parser.parse_args(["dispatch", "codex", "--task", "test", "--force-agent"])
    assert args2.force_agent is True


def test_jobs_handoff_cli_to_harness():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["jobs", "handoff", "job-12345", "--to-harness", "codex"])
    assert args.to_agent == "codex"


def test_warn_deprecated_harness_flags(capsys):
    from synlynk.cli import _warn_deprecated_harness_flag

    _warn_deprecated_harness_flag(["synlynk", "quota", "--agent", "codex"])
    captured = capsys.readouterr()
    assert "warning: --agent is deprecated, use --harness instead" in captured.err

    _warn_deprecated_harness_flag(["synlynk", "dispatch", "codex", "--task", "t", "--force-agent"])
    captured = capsys.readouterr()
    assert "warning: --force-agent is deprecated, use --force-harness instead" in captured.err

    _warn_deprecated_harness_flag(["synlynk", "jobs", "handoff", "j1", "--to-agent", "codex"])
    captured = capsys.readouterr()
    assert "warning: --to-agent is deprecated, use --to-harness instead" in captured.err


def test_dispatch_and_jobs_handoff_cli_warn_deprecated_flags(monkeypatch, capsys):
    import synlynk
    import synlynk.cli as cli

    monkeypatch.setattr(synlynk, "dispatch_agent", lambda *a, **k: {"id": "j1", "pid": 1234})
    monkeypatch.setattr(synlynk, "_reconcile_jobs", lambda: None)
    cli.main(["dispatch", "codex", "--task", "t", "--force-agent", "--skip-preflight"])
    captured = capsys.readouterr()
    assert "warning: --force-agent is deprecated, use --force-harness instead" in captured.err

    monkeypatch.setattr(synlynk, "cmd_jobs_handoff", lambda *a, **k: None)
    cli.main(["jobs", "handoff", "job-123", "--to-agent", "codex"])
    captured = capsys.readouterr()
    assert "warning: --to-agent is deprecated, use --to-harness instead" in captured.err


def test_harness_config_and_listing_with_harnesses_dir(tmp_path, monkeypatch, capsys):
    import json
    import synlynk
    from synlynk.support_engineer import cmd_harness_list, cmd_agent_list

    monkeypatch.chdir(tmp_path)
    harnesses_dir = tmp_path / ".harnesses"
    harnesses_dir.mkdir()
    (harnesses_dir / "codex.json").write_text(json.dumps({"harness": "codex", "model": "codex-test"}))

    cfg = synlynk._load_agent_config("codex")
    assert cfg["harness"] == "codex"
    assert cfg["model"] == "codex-test"

    dummy_cursor = type("DummyCursor", (), {"fetchone": lambda self: None})()
    dummy_db = type("DummyDB", (), {"execute": lambda self, *a, **k: dummy_cursor, "close": lambda self: None})()
    monkeypatch.setattr(synlynk.support_engineer, "_pkg", lambda name: lambda: dummy_db)
    cmd_harness_list()
    captured = capsys.readouterr()
    assert "codex" in captured.out

    assert cmd_agent_list is cmd_harness_list
    assert synlynk.cmd_harness_add is synlynk.cmd_agent_add
    assert synlynk.cmd_harness_configure is synlynk.cmd_agent_configure


def test_featdoctor_add_tc9_insandbox_ghwrite_cap(monkeypatch):
    import synlynk
    monkeypatch.setattr("shutil.which", lambda bin_name: "/usr/local/bin/claude")
    monkeypatch.setattr(synlynk.probe, "_run_tc6", lambda *a, **k: {"passed": True, "error": "", "output": "ok"})
    res = synlynk._run_tc9("claude")
    assert res["passed"] is True
    assert res["can_gh_write"] is True


def test_manifest_auth_prevent_dropped_oauth_codes_in_manifest_callback_server():
    """gh:#906 — two callback requests landing before wait_for_code() is
    called must both be queued, not have the second one silently dropped."""
    import threading
    from urllib.request import urlopen

    import synlynk.team as team_mod

    port, wait_for_code, shutdown = team_mod._run_manifest_callback_server(
        timeout_seconds=5
    )
    try:
        barrier = threading.Barrier(2)
        results = {}

        def fire(code, key):
            barrier.wait(timeout=5)
            with urlopen(
                f"http://127.0.0.1:{port}/callback?code={code}", timeout=5
            ) as resp:
                results[key] = resp.status

        t1 = threading.Thread(target=fire, args=("code-one", "t1"))
        t2 = threading.Thread(target=fire, args=("code-two", "t2"))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert results.get("t1") == 200
        assert results.get("t2") == 200

        first = wait_for_code()
        second = wait_for_code()
        assert {first, second} == {"code-one", "code-two"}
    finally:
        shutdown()


def test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073(tmp_path):
    """Investigate issue #1073: Root-cause anomalous cost and token bloat on job-cf837848
    ($5.26 / 7.6M input tokens on issue #1068).
    Verifies Sentinel pattern detection for anomalous token-per-file ratio and cost inflation.
    """
    import synlynk
    from synlynk.sentinel import check_token_bloat, _read_sentinel_alerts

    sentinel_file = tmp_path / "sentinel.md"

    # 1. Verify direct invocation of sentinel check with job-cf837848 metrics
    alerts = synlynk.check_token_bloat(
        in_tokens=7_600_000,
        out_tokens=50_000,
        cost_usd=5.26,
        files_touched=0,
        job_id="job-cf837848",
        agent="codex",
        sentinel_path=str(sentinel_file),
    )

    assert len(alerts) == 2
    alert_codes = [a["code"] for a in alerts]
    assert "TOKEN_BLOAT" in alert_codes
    assert "COST_INFLATION" in alert_codes

    # 2. Verify alert content in sentinel.md
    raw_alerts = sentinel_file.read_text()
    assert "TOKEN_BLOAT" in raw_alerts
    assert "COST_INFLATION" in raw_alerts
    assert "job-cf837848" in raw_alerts
    assert "7,650,000 tokens" in raw_alerts
    assert "0 files touched" in raw_alerts
    assert "$5.26" in raw_alerts

    # 3. Verify ratio check with files touched > 0
    alerts_ratio = check_token_bloat(
        in_tokens=1_200_000,
        out_tokens=10_000,
        cost_usd=1.50,
        files_touched=1,
        job_id="job-ratio-test",
        agent="agy",
        sentinel_path=str(sentinel_file),
    )
    assert any(a["code"] == "TOKEN_BLOAT" and "1,210,000 tok/file" in a["message"] for a in alerts_ratio)


def test_featmarketing_implement_living_docs_sync(tmp_path, monkeypatch):
    from synlynk.marketing import (
        validate_blog_post_frontmatter,
        extract_social_changelog_snippets,
        update_blog_index,
    )
    from synlynk.media import cmd_media_generate, generate_svg_diagram, generate_og_card
    from synlynk.taxonomy import COMMAND_TAXONOMY

    # 1. Frontmatter validation
    blog_file = tmp_path / "164-pr1347-autonomous-growth-engine.md"
    blog_file.write_text("""---
title: "PR #1347 — Autonomous Growth & Marketing Engine"
author: "Agy (Gemini)"
date: "2026-09-02"
pr: "#1347"
version: "0.19.0"
tags: ["growth", "marketing", "automation"]
---

## What This PR Shipped
- Implemented YAML schema validation for blog post frontmatter.
- Integrated automated command docs generation into instructions update.
- Added SVG diagram and OpenGraph preview card generator.
""", encoding="utf-8")

    meta = validate_blog_post_frontmatter(blog_file)
    assert meta["title"] == "PR #1347 — Autonomous Growth & Marketing Engine"
    assert meta["author"] == "Agy (Gemini)"
    assert meta["version"] == "0.19.0"
    assert meta["tags"] == ["growth", "marketing", "automation"]

    # 2. Social snippet extraction
    draft_path = tmp_path / ".synlynk" / "social_drafts.json"
    draft = extract_social_changelog_snippets(blog_file, output_path=draft_path)
    assert draft["pr"] == "#1347"
    assert "#growth" in draft["tweet"]
    assert "### v0.19.0" in draft["changelog"]
    assert draft_path.exists()

    # 3. Media asset generation
    media_dir = tmp_path / "media"
    results = cmd_media_generate(media_type="all", title="Marketing Engine", output=str(media_dir))
    assert "diagram" in results
    assert "og_card" in results

    # 4. Taxonomy & Command Surface verification
    media_entries = [e for e in COMMAND_TAXONOMY if e["command"] == "media generate"]
    assert len(media_entries) == 1
    assert media_entries[0]["governs_stage"] == "sustain"


def test_feat_pm_autonomous_backlog_triaging__story_c70350f9(tmp_path, monkeypatch, capsys):
    from unittest.mock import patch, MagicMock
    import synlynk
    from synlynk.backlog import (
        fetch_open_github_issues,
        is_duplicate_issue,
        synthesize_story_from_issue,
        ingest_backlog,
        triage_backlog,
        auto_promote_backlog,
    )
    from synlynk.db import _migrate_db
    from synlynk.taxonomy import COMMAND_TAXONOMY
    from synlynk.cli import main

    # 1. Verify schema migration creates backlog_items table
    db_file = tmp_path / "test_state.db"
    conn = sqlite3.connect(str(db_file))
    _migrate_db(conn)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backlog_items'")
    assert cursor.fetchone() is not None

    monkeypatch.setattr("synlynk.backlog._get_connection", lambda db_conn=None: conn)

    # 2. Verify issue synthesis (role, tier, criteria, goal mapping)
    issue_mock = {
        "number": 1340,
        "title": "PM Autonomous Backlog Triaging & Story Formation Engine",
        "body": "Operationalize PM backlog triage.\n\n- [ ] Ingest open issues\n- [ ] Synthesize acceptance criteria\n- [ ] Auto-promote to ready stories",
        "labels": [{"name": "role:pm"}],
        "author": {"login": "nikhilsoman"},
    }
    story = synthesize_story_from_issue(issue_mock, db_conn=conn)
    assert story["role"] == "pm"
    assert story["complexity_tier"] in (2, 3)
    assert story["goal_id"] == "goal-6733bbf1"
    assert len(story["acceptance_criteria"]) >= 3
    assert "Ingest open issues" in story["acceptance_criteria"][0]

    # 3. Verify deduplication against state.db and closed PRs
    mock_issues = [
        issue_mock,
        {
            "number": 1341,
            "title": "Ephemeral Swarm Execution Infrastructure Drivers",
            "body": "Fly.io and Kubernetes ephemeral job pods",
            "labels": [{"name": "role:dev"}],
            "author": {"login": "nikhilsoman"},
        },
    ]

    with patch("synlynk.backlog.fetch_open_github_issues", return_value=mock_issues):
        with patch("synlynk.backlog.is_duplicate_issue", return_value=(False, "")):
            # Ingest
            res = ingest_backlog(db_conn=conn)
            assert res["fetched"] == 2
            assert res["ingested"] == 2

            # Duplicate check
            is_dup, _ = is_duplicate_issue(issue_mock, db_conn=conn, check_closed_prs=False)
            assert is_dup is True

    # 4. Verify triage and auto-promotion to state.db stories and goal_contributions
    triaged = triage_backlog(auto_promote=False, db_conn=conn)
    assert len(triaged) == 2
    assert all(t["status"] == "triaged" for t in triaged)

    promoted = auto_promote_backlog(db_conn=conn, min_tier=1)
    assert len(promoted) == 2
    for p in promoted:
        assert p["story_id"].startswith("story-")
        story_in_db = conn.execute(
            "SELECT story_id, title, role, readiness, status FROM stories WHERE story_id = ?",
            (p["story_id"],),
        ).fetchone()
        assert story_in_db is not None
        assert story_in_db[3] == "ready"
        assert story_in_db[4] == "open"

    # 5. Verify CLI subcommands (ingest, triage, auto-promote)
    with patch("synlynk.backlog.fetch_open_github_issues", return_value=[]):
        main(["backlog", "ingest"])
        out = capsys.readouterr().out
        assert "Ingested 0 backlog items" in out

        main(["backlog", "triage"])
        out = capsys.readouterr().out
        assert "No pending backlog items to triage" in out

        main(["backlog", "auto-promote"])
        out = capsys.readouterr().out
        assert "No backlog items eligible for auto-promotion" in out

    # 6. Verify taxonomy registration
    cmds = {e["command"] for e in COMMAND_TAXONOMY}
    assert "backlog ingest" in cmds
    assert "backlog triage" in cmds
    assert "backlog auto-promote" in cmds


def test_featonboarding_implement_zerorisk_dirty_worktree_and_first_win__story_7a81f33f(tmp_path, monkeypatch, capsys):
    """Verify zero-risk onboarding dirty-tree safety guard, streamlined wizard init, and first-win PR remediation."""
    import time
    from unittest.mock import MagicMock
    from synlynk.wizard import guard_dirty_worktree, cmd_wizard_init
    from synlynk.launch import find_top_scan_finding, dispatch_first_win_remediation, prompt_first_win_remediation

    # 1. Verify dirty-tree safety guard creates backup tar.gz and git stash
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    base_file = tmp_path / "README.md"
    base_file.write_text("# Project\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True, capture_output=True)

    # Introduce dirty and untracked changes
    base_file.write_text("# Project - dirty state\n")
    (tmp_path / "dirty.py").write_text("print('dirty')\n")

    guard_res = guard_dirty_worktree(repo_dir=str(tmp_path))
    assert guard_res is not None
    assert guard_res.dirty is True
    assert guard_res.stash_created is True
    assert os.path.exists(guard_res.backup_path)
    assert ".synlynk/backups/init-" in guard_res.backup_path

    # 2. Verify streamlined cmd_wizard_init (<5s, 8 charters, probes, backlog ingest)
    monkeypatch.setattr(
        "synlynk.scan._detect_harnesses_on_path",
        lambda *a, **kw: [{"name": "claude", "cli": "claude", "version": "1.0", "path": "/bin/claude"}]
    )
    monkeypatch.setattr(
        "synlynk.backlog.ingest_backlog",
        lambda *a, **kw: {"ingested": 4, "fetched": 4, "duplicates": 0}
    )

    t0 = time.time()
    init_res = cmd_wizard_init(
        repo_dir=str(tmp_path),
        dry_run=False,
        sync_github=True,
        prompt_remediation=False,
    )
    t_elapsed = time.time() - t0

    assert t_elapsed < 5.0
    assert init_res["elapsed_seconds"] < 5.0
    assert len(init_res["charters_provisioned"]) == 8
    assert "dev" in init_res["charters_provisioned"]
    assert "qa" in init_res["charters_provisioned"]
    assert "pm" in init_res["charters_provisioned"]

    # Verify standard charters minted in .synlynk/agents/
    agents_dir = tmp_path / ".synlynk" / "agents"
    assert agents_dir.exists()
    for role in ["dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot"]:
        cf = agents_dir / f"{role}.md"
        assert cf.exists()
        assert f"role: {role}" in cf.read_text()

    # Verify backlog ingest auto-invoked
    assert init_res["backlog_ingest"]["ingested"] == 4

    # 3. Verify First-Win top finding discovery and PR dispatch
    finding = find_top_scan_finding(repo_dir=str(tmp_path))
    assert finding is not None
    assert "title" in finding
    assert "description" in finding

    mock_dispatch = MagicMock(return_value={"job_id": "job-fw-test"})
    monkeypatch.setattr("synlynk.dispatch.dispatch_agent", mock_dispatch)

    remed_res = dispatch_first_win_remediation(finding=finding, repo_dir=str(tmp_path))
    assert remed_res["status"] == "dispatched"
    assert remed_res["job_id"] == "job-fw-test"
    mock_dispatch.assert_called_once()
    _, kw = mock_dispatch.call_args
    assert kw.get("requires_gh_write") is True
