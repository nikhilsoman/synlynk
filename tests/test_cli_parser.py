import pytest
import os
import json
import sqlite3
import subprocess
import sys

import synlynk.cli as cli_mod


def test_build_parser_exposes_dispatch_tree_without_running_main():
    parser = cli_mod.build_parser()

    args = parser.parse_args(["dispatch", "codex", "--task", "build"])
    assert args.command == "dispatch"
    assert args.agent == "codex"
    assert args.task == "build"

    with pytest.raises(SystemExit):
        parser.parse_args(["dispatch", "not-a-real-agent", "--task", "build"])


def test_dispatch_parser_accepts_issue_flag():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["dispatch", "claude", "--task", "fix it", "--issue", "395"])

    assert args.issue == 395


def test_dispatch_parser_issue_defaults_to_none():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["dispatch", "claude", "--task", "fix it"])

    assert args.issue is None


def test_dispatch_parser_effort_defaults_to_none_and_accepts_low_or_high():
    parser = cli_mod.build_parser()

    assert parser.parse_args(["dispatch", "agy", "--task", "fix it"]).effort is None
    assert parser.parse_args(["dispatch", "agy", "--task", "fix it", "--effort", "low"]).effort == "low"
    assert parser.parse_args(["dispatch", "agy", "--task", "fix it", "--effort", "high"]).effort == "high"

    with pytest.raises(SystemExit):
        parser.parse_args(["dispatch", "agy", "--task", "fix it", "--effort", "medium"])


def test_backfill_capability_ratings_parser_registered():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["backfill-capability-ratings"])

    assert args.command == "backfill-capability-ratings"


def test_doctor_fix_parser_accepts_agy():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["doctor", "--fix", "agy", "--yes"])

    assert args.command == "doctor"
    assert args.fix == "agy"
    assert args.yes is True


def test_start_command_parses():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["start"])

    assert args.command == "start"


def test_type_seed_and_identity_pack_parse():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["type", "seed", "--pack", "studio"])
    assert (args.command, args.type_action, args.pack) == ("type", "seed", "studio")
    args = parser.parse_args(["identity", "init", "--type", "director", "--pack", "studio"])
    assert (args.role, args.pack) == ("director", "studio")


def test_w8_connector_and_relabel_parsers():
    parser = cli_mod.build_parser()
    args = parser.parse_args([
        "connector", "add", "figma", "--home-repo", "synlynk",
        "--reach", "home_repo", "--allow", "api.figma.com", "--protocol", "oauth",
    ])
    assert (args.command, args.connector_action, args.type_id) == ("connector", "add", "figma")
    args = parser.parse_args(["type", "relabel", "director", "Showrunner"])
    assert (args.command, args.type_action, args.type_id, args.label) == (
        "type", "relabel", "director", "Showrunner"
    )


def test_audit_docs_parser_accepts_json_and_fix_flags():
    from synlynk.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["audit-docs", "--json", "--fix"])
    assert args.command == "audit-docs"
    assert args.json is True
    assert args.fix is True


def test_probe_agent_flag_deprecated_alias():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["probe", "--agent", "codex"])
    assert args.harness == "codex"


def test_probe_harness_flag_new():
    parser = cli_mod.build_parser()
    args = parser.parse_args(["probe", "--harness", "codex"])
    assert args.harness == "codex"


def test_milestone_runs_unattended_by_default(monkeypatch):
    calls = []

    import synlynk.launch_dag as launch_dag

    monkeypatch.setattr(
        launch_dag,
        "cmd_run_dag",
        lambda **kwargs: calls.append(kwargs),
    )

    cli_mod.main(["run", "--milestone", "v0.20.0"])

    assert calls == [
        {
            "milestone": "v0.20.0",
            "unattended": True,
            "dag_view": False,
            "dry_run": False,
            "max_parallel": 4,
        }
    ]


def test_run_and_launch_help_describe_unattended_default():
    parser = cli_mod.build_parser()
    run_help = parser.parse_args(["run"])  # parser construction remains valid
    assert run_help.command == "run"
    subparser_action = parser._subparsers._group_actions[0]
    run_help_text = " ".join(subparser_action.choices["run"].format_help().split())
    command_help = {
        action.dest: action.help for action in subparser_action._choices_actions
    }
    assert "approved plans unattended via `synlynk run --milestone`" in command_help["run"]
    assert "approved-plan execution is unattended" in run_help_text
    assert "by default" in run_help_text
    assert "approved plans run unattended via `synlynk run --milestone`" in command_help["launch"]


def test_fast_cli_import_defers_command_graph():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import synlynk.cli; "
            "print('synlynk.db' in sys.modules); synlynk.cli.build_parser()",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "SYNLYNK_CLI_ENTRYPOINT": "1"},
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_fast_cli_preserves_help_and_invalid_command_paths():
    help_result = subprocess.run(
        [sys.executable, "-m", "synlynk", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    invalid_result = subprocess.run(
        [sys.executable, "-m", "synlynk", "not-a-real-command"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_result.returncode == 0
    assert "sentinel" in help_result.stdout
    assert invalid_result.returncode == 2
    assert "invalid choice" in invalid_result.stderr


def test_state_restore_cli_prints_json_result(tmp_path, monkeypatch, capsys):
    source = tmp_path / "snapshot.db"
    sqlite3.connect(source).close()
    destination = tmp_path / "workspace" / "state.db"
    monkeypatch.setenv("SYNLYNK_REGISTRY_PATH", str(tmp_path / "registry.json"))

    cli_mod.main([
        "state",
        "restore",
        str(source),
        str(destination),
        "--slug",
        "demo",
        "--product-id",
        "product-demo",
    ])

    output = json.loads(capsys.readouterr().out)
    assert output["disposition"] == "planned"
    assert output["destination"] == str(destination)
