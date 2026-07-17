import argparse

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
