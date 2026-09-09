import pytest
import os
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
