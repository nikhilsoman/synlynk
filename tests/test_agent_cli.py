import sqlite3
import subprocess

import pytest

from synlynk.agent_cli import SEED_CHARTERS


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

    assert flags == ["-c", "approval_policy=untrusted"]
    assert "--ask-for-approval" not in flags
    assert "sandbox_workspace_write.network_access=true" not in flags


def test_codex_dispatch_fails_askforapproval_rejected_flag_is_not_emitted():
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("codex", ["read:*"])

    assert flags == ["-c", "approval_policy=untrusted"]
    assert "--ask-for-approval" not in flags


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
