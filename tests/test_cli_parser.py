import pytest

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
