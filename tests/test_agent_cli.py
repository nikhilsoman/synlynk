import sqlite3
import subprocess
import re
import os

import pytest

from synlynk.agent_cli import SEED_CHARTERS


def test_codex_harness_baseline_includes_verifier_role_and_can_gh_write():
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    codex = HARNESS_CAPABILITY_BASELINES["codex"]
    assert "verifier" in codex["roles"]
    assert codex["can_gh_write"] is True


def test_claude_harness_alignment_update_baseline():
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    claude = HARNESS_CAPABILITY_BASELINES["claude"]
    assert claude["roles"] == ["architect", "pm"]
    assert "builder" not in claude["roles"]


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
    monkeypatch,
):
    from synlynk.release_readme import validate_readme_for_release

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.chdir(repo_root)
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




