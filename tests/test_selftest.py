import argparse
from pathlib import Path
from unittest.mock import patch

from synlynk.taxonomy import COMMAND_TAXONOMY


EXPECTED_LIVE_SCENARIOS = [
    "init",
    "migrate",
    "scan",
    "join",
    "goal create",
    "goal list",
    "goal link",
    "goal status",
    "story create",
    "story list",
    "decide",
    "jobs",
    "status",
    "instructions status",
    "upgrade",
]


def test_selftest_core_exports():
    from synlynk.selftest import (
        SELFTEST_SCENARIOS,
        ScenarioContext,
        ScenarioResult,
        cmd_selftest,
        run_selftest,
    )

    assert isinstance(SELFTEST_SCENARIOS, dict)
    assert callable(run_selftest)
    assert callable(cmd_selftest)

    ctx = ScenarioContext(repo_path="/tmp/selftest", live=False)
    assert ctx.repo_path == "/tmp/selftest"
    assert ctx.live is False
    assert ctx.budget_cap_usd == 2.0
    assert ctx.spent_usd == 0.0
    assert ctx.state == {}

    result = ScenarioResult(command="init", status="pass", detail="ok")
    assert result.cost_usd == 0.0


def test_selftest_registry_covers_core_lifecycle_commands():
    from synlynk.selftest import SELFTEST_SCENARIOS

    assert set(EXPECTED_LIVE_SCENARIOS) <= set(SELFTEST_SCENARIOS)


def test_run_selftest_uses_generic_help_for_all_taxonomy_commands(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod

    monkeypatch.chdir(tmp_path)

    results = selftest_mod.run_selftest(live=False)

    assert len(results) == len(COMMAND_TAXONOMY)
    assert all(result.status == "pass" for result in results)

    ordered_commands = [result.command for result in results]
    expected_commands = [
        entry["command"]
        for entry in sorted(
            COMMAND_TAXONOMY,
            key=selftest_mod._selftest_sort_key,
        )
    ]
    assert ordered_commands == expected_commands

    tiers = [next(item for item in COMMAND_TAXONOMY if item["command"] == command)["maturity_tier"]
             for command in ordered_commands]
    assert tiers[-12:] == ["latent"] * 12


def test_run_selftest_sorts_latent_tier_last(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod

    monkeypatch.chdir(tmp_path)

    results = selftest_mod.run_selftest(live=False)

    commands = [result.command for result in results]
    assert commands.index("status") < commands.index("relay start")
    assert commands.index("watch") < commands.index("relay start")
    assert commands.index("viz") < commands.index("relay start")


def test_live_selftest_bespoke_lifecycle_scenarios_pass(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)

    for command in EXPECTED_LIVE_SCENARIOS:
        entry = next(item for item in COMMAND_TAXONOMY if item["command"] == command)
        result = selftest_mod.SELFTEST_SCENARIOS[command](entry, ctx)
        assert result.status == "pass", f"{command}: {result.detail}"


def test_live_selftest_init_preserves_existing_files(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)
    entry = next(item for item in COMMAND_TAXONOMY if item["command"] == "init")

    result = selftest_mod.SELFTEST_SCENARIOS["init"](entry, ctx)

    assert result.status == "pass"
    assert "without clobbering existing files" in result.detail


def test_live_selftest_migrate_imports_real_rows(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)
    entry = next(item for item in COMMAND_TAXONOMY if item["command"] == "migrate")

    result = selftest_mod.SELFTEST_SCENARIOS["migrate"](entry, ctx)

    assert result.status == "pass"
    assert "state.db" in result.detail


def test_live_selftest_upgrade_respects_install_location(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)
    entry = next(item for item in COMMAND_TAXONOMY if item["command"] == "upgrade")

    result = selftest_mod.SELFTEST_SCENARIOS["upgrade"](entry, ctx)

    assert result.status == "pass"
    assert "pipx install path" in result.detail


def test_gh_write_scenario_records_capability_per_harness_and_mode(tmp_path):
    import sqlite3
    from synlynk.selftest import ScenarioContext, _scenario_gh_write_actions

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    ctx.state["workspace_dir"] = tmp_path
    db_path = tmp_path / ".synlynk" / "state.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    import synlynk as synlynk_pkg

    with patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        conn = synlynk_pkg._get_db()
        conn.close()

    discovered = [{"name": "codex"}]

    def fake_gh_write(agent_name, mode, action):
        return "pass" if action == "gh pr review" else "fail"

    with patch("synlynk.selftest.discover_agents", return_value=discovered), patch(
        "synlynk.selftest._attempt_gh_write_action", side_effect=fake_gh_write
    ), patch.object(synlynk_pkg, "DB_PATH", str(db_path)):
        results = _scenario_gh_write_actions({"command": "gh-write-check"}, ctx)

    statuses = {r.command: r.status for r in results}
    assert any("gh pr review" in cmd for cmd in statuses)
    assert any("gh pr merge" in cmd and statuses[cmd] == "fail" for cmd in statuses)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT harness, mode, action, status FROM gh_write_capability"
    ).fetchall()
    conn.close()
    assert ("codex", "home", "gh pr review", "pass") in rows
    assert ("codex", "home", "gh pr merge", "fail") in rows


def test_selftest_subcommand_is_registered():
    from synlynk.cli import build_parser

    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)

    args = parser.parse_args(["selftest"])
    assert args.command == "selftest"
    assert args.live is False

    args_live = parser.parse_args(["selftest", "--live"])
    assert args_live.live is True


def test_dispatch_scenario_skips_when_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=1.0, spent_usd=1.0)
    with patch("synlynk.discover_agents", return_value=[{"name": "codex"}]), patch(
        "synlynk.selftest.dispatch_agent"
    ) as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_not_called()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].status == "skipped"
    assert "budget" in result[0].detail.lower()


def test_dispatch_scenario_uses_fence_estimate_as_cost(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.fencing import FenceData
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    fake_job = {
        "id": "job-selftest",
        "pid": 12345,
        "fence": FenceData(
            command="dispatch",
            kind="estimate",
            in_tokens=100,
            out_tokens=50,
            cost_usd=0.03,
            basis="prompt_estimate",
        ),
    }
    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=2.0)
    with patch("synlynk.discover_agents", return_value=[{"name": "codex"}]), patch(
        "synlynk.selftest.dispatch_agent", return_value=fake_job
    ) as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_called_once()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].status == "pass"
    assert result[0].cost_usd == 0.03


def test_exec_scenario_skips_when_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=1.0, spent_usd=1.0)
    with patch("synlynk.discover_agents", return_value=[{"name": "claude"}]), patch(
        "synlynk.selftest.exec_command"
    ) as mock_exec:
        result = SELFTEST_SCENARIOS["exec"]({"command": "exec"}, ctx)
    mock_exec.assert_not_called()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].status == "skipped"


def test_dispatch_scenario_patches_db_path_to_scratch_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk as synlynk_pkg
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    scratch_workspace = tmp_path / "scratch"
    scratch_workspace.mkdir()

    host_db_path = synlynk_pkg.DB_PATH
    seen_db_path = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        seen_db_path["value"] = synlynk_pkg.DB_PATH
        return {"id": "job-fake", "pid": 1, "fence": None}

    ctx = ScenarioContext(repo_path=str(scratch_workspace), live=True, budget_cap_usd=2.0)
    with patch("synlynk.discover_agents", return_value=[{"name": "codex"}]), patch(
        "synlynk.selftest.dispatch_agent", side_effect=fake_dispatch_agent
    ):
        results = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)

    assert seen_db_path.get("value") == str(scratch_workspace / ".synlynk" / "state.db")
    assert synlynk_pkg.DB_PATH == host_db_path
    assert isinstance(results, list)
    assert results[0].status == "pass"


def test_scenario_context_has_mode_and_harness_fields():
    from synlynk.selftest import ScenarioContext

    ctx = ScenarioContext(repo_path="", live=True)
    assert ctx.mode == "home"
    assert ctx.harness is None


def test_dispatch_scenario_loops_over_discovered_harnesses(tmp_path):
    from synlynk.selftest import ScenarioContext, _dispatch_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}, {"name": "grok"}]
    with patch("synlynk.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent",
        return_value={"id": "job-1", "pid": 123, "fence": None},
    ) as mock_dispatch:
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert isinstance(results, list)
    assert len(results) == 2
    called_agents = {call.args[0] for call in mock_dispatch.call_args_list}
    assert called_agents == {"codex", "grok"}


def test_dispatch_scenario_asserts_pr_base_branch(tmp_path):
    from synlynk.selftest import ScenarioContext, _dispatch_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}]
    fake_job = {
        "id": "job-1",
        "pid": 123,
        "fence": None,
        "base_branch": "dispatch/claude/job-parent",
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-1",
    }
    with patch("synlynk.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent", return_value=fake_job
    ), patch(
        "synlynk.selftest._wait_for_worktree_finalization", return_value=fake_job
    ), patch(
        "synlynk.selftest._resolve_worktree_pr_base_branch",
        return_value="dispatch/claude/job-parent",
    ) as mock_resolve:
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert results[0].status == "pass"
    mock_resolve.assert_called_once()


def test_dispatch_scenario_fails_on_pr_base_branch_mismatch(tmp_path):
    from synlynk.selftest import ScenarioContext, _dispatch_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "codex"}]
    fake_job = {
        "id": "job-1",
        "pid": 123,
        "fence": None,
        "base_branch": "dispatch/claude/job-parent",
        "worktree_path": str(tmp_path / "worktree"),
        "worktree_branch": "dispatch/codex/job-1",
    }
    with patch("synlynk.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.dispatch_agent", return_value=fake_job
    ), patch(
        "synlynk.selftest._wait_for_worktree_finalization", return_value=fake_job
    ), patch(
        "synlynk.selftest._resolve_worktree_pr_base_branch", return_value="main"
    ):
        results = _dispatch_scenario({"command": "dispatch"}, ctx)
    assert results[0].status == "fail"
    assert "base branch" in results[0].detail


def test_exec_scenario_loops_over_discovered_harnesses(tmp_path):
    from synlynk.selftest import ScenarioContext, _exec_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    discovered = [{"name": "claude"}, {"name": "agy"}]
    with patch("synlynk.discover_agents", return_value=discovered), patch(
        "synlynk.selftest.exec_command", return_value=0
    ) as mock_exec:
        results = _exec_scenario({"command": "exec"}, ctx)
    assert len(results) == 2
    assert mock_exec.call_count == 2


def test_exec_scenario_marks_zero_exit_as_pass(tmp_path):
    from synlynk.selftest import ScenarioContext, _exec_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    with patch("synlynk.discover_agents", return_value=[{"name": "claude"}]), patch(
        "synlynk.selftest.exec_command", return_value=0
    ):
        results = _exec_scenario({"command": "exec"}, ctx)
    assert results[0].status == "pass"


def test_exec_scenario_marks_nonzero_exit_as_skipped(tmp_path):
    from synlynk.selftest import ScenarioContext, _exec_scenario

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True)
    with patch("synlynk.discover_agents", return_value=[{"name": "claude"}]), patch(
        "synlynk.selftest.exec_command", return_value=1
    ):
        results = _exec_scenario({"command": "exec"}, ctx)
    assert results[0].status == "skipped"


def test_live_paid_selftest_scenarios_use_scratch_workspace(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod
    import synlynk.scheduler as scheduler_mod

    host_cwd = Path.cwd()
    scratch_workspace = tmp_path / "scratch"
    recorded = []

    class FakeTemporaryDirectory:
        def __init__(self, *args, **kwargs):
            scratch_workspace.mkdir(parents=True, exist_ok=True)

        def __enter__(self):
            return str(scratch_workspace)

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(selftest_mod.tempfile, "TemporaryDirectory", FakeTemporaryDirectory)
    monkeypatch.setattr(
        selftest_mod,
        "COMMAND_TAXONOMY",
        [entry for entry in selftest_mod.COMMAND_TAXONOMY if entry["command"] in {"dispatch", "exec", "schedule"}],
    )
    monkeypatch.setattr(
        selftest_mod,
        "dispatch_agent",
        lambda *args, **kwargs: {"id": "job-selftest", "pid": 1, "fence": None},
    )
    monkeypatch.setattr(selftest_mod, "exec_command", lambda argv: 0)
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda execute=True, max_stories=1: None)

    def fake_chdir(path):
        recorded.append(Path(path))

    monkeypatch.setattr(selftest_mod.os, "chdir", fake_chdir)

    results = selftest_mod.run_selftest(live=True)

    assert all(result.status == "pass" for result in results)
    assert host_cwd != scratch_workspace
    assert recorded[0] == scratch_workspace
    assert recorded[-1] == host_cwd
    assert set(recorded) <= {scratch_workspace, host_cwd}


def test_live_status_scenario_initializes_full_schema(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod

    scratch_workspace = tmp_path / "scratch"
    monkeypatch.setattr(selftest_mod.tempfile, "mkdtemp", lambda prefix="": str(scratch_workspace))

    entry = {"command": "status"}
    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)

    result = selftest_mod.SELFTEST_SCENARIOS["status"](entry, ctx)

    assert result.status == "pass"
    assert "status rendered" in result.detail


def test_all_paid_commands_have_registered_scenarios():
    from synlynk.selftest import SELFTEST_SCENARIOS

    for cmd in ["dispatch", "exec", "schedule", "release"]:
        assert cmd in SELFTEST_SCENARIOS, f"missing scenario for {cmd!r}"


def test_scenario_migrate_failure_injection_triggers_rollback():
    from synlynk.selftest import (
        ScenarioContext, _scenario_migrate_failure_injection,
    )

    ctx = ScenarioContext(repo_path="", live=True)
    result = _scenario_migrate_failure_injection({"command": "migrate"}, ctx)
    assert result.status == "pass", result.detail


def test_scenario_upgrade_failure_injection_triggers_rollback():
    from synlynk.selftest import (
        ScenarioContext, _scenario_upgrade_failure_injection,
    )

    ctx = ScenarioContext(repo_path="", live=True)
    result = _scenario_upgrade_failure_injection({"command": "upgrade"}, ctx)
    assert result.status == "pass", result.detail


def test_synlynk_rollback_last_via_cli(tmp_path, monkeypatch):
    import subprocess as sp
    from synlynk import rollback

    monkeypatch.chdir(tmp_path)
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1\n")
    sp.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-m", "seed", "-q"], cwd=tmp_path, check=True)

    with rollback.rollback_checkpoint("init", untracked_paths=[]):
        tracked.write_text("v2\n")
        sp.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
        sp.run(["git", "commit", "-m", "unwanted", "-q"], cwd=tmp_path, check=True)

    from synlynk.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["rollback", "--last"])
    assert args.command == "rollback"
    assert args.last is True

    rollback.cmd_rollback(last=True)
    assert tracked.read_text() == "v1\n"
