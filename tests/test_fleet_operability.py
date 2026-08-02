"""Fleet operability: core fleet constants and open allowlist."""

import pytest

from synlynk._constants import (
    CORE_FLEET,
    EXPERIMENTAL_FLEET,
    PROVEN_FRESHNESS_DAYS,
    MATRIX_LIVE_BUDGET_USD,
    AGENT_BUILDER_ONLY,
)


def test_core_fleet_is_four():
    assert CORE_FLEET == frozenset({"claude", "agy", "codex", "grok"})
    assert "local" in EXPERIMENTAL_FLEET
    assert "local" not in CORE_FLEET


def test_proven_and_budget_defaults():
    assert PROVEN_FRESHNESS_DAYS == 7
    assert MATRIX_LIVE_BUDGET_USD == 10.0


def test_codex_builder_only_flag():
    assert "codex" in AGENT_BUILDER_ONLY


def test_open_parser_rejects_local():
    from synlynk.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["open", "local"])


def test_open_parser_accepts_core_fleet():
    from synlynk.cli import build_parser

    parser = build_parser()
    for agent in sorted(CORE_FLEET):
        args = parser.parse_args(["open", agent])
        assert args.command == "open"
        assert args.agent == agent
