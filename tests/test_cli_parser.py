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
