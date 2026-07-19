import argparse
from unittest.mock import patch

from synlynk.taxonomy import COMMAND_TAXONOMY


EXPECTED_LIVE_SCENARIOS = [
    "init",
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
    with patch("synlynk.selftest.dispatch_agent") as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_not_called()
    assert result.status == "skipped"
    assert "budget" in result.detail.lower()


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
    with patch("synlynk.selftest.dispatch_agent", return_value=fake_job) as mock_dispatch:
        result = SELFTEST_SCENARIOS["dispatch"]({"command": "dispatch"}, ctx)
    mock_dispatch.assert_called_once()
    assert result.status == "pass"
    assert result.cost_usd == 0.03


def test_exec_scenario_skips_when_budget_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.selftest import ScenarioContext, SELFTEST_SCENARIOS

    ctx = ScenarioContext(repo_path=str(tmp_path), live=True, budget_cap_usd=1.0, spent_usd=1.0)
    with patch("synlynk.selftest.exec_command") as mock_exec:
        result = SELFTEST_SCENARIOS["exec"]({"command": "exec"}, ctx)
    mock_exec.assert_not_called()
    assert result.status == "skipped"


def test_all_paid_commands_have_registered_scenarios():
    from synlynk.selftest import SELFTEST_SCENARIOS

    for cmd in ["dispatch", "exec", "schedule", "release"]:
        assert cmd in SELFTEST_SCENARIOS, f"missing scenario for {cmd!r}"
