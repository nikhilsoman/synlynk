"""Fleet operability: core fleet constants and open allowlist."""

from pathlib import Path

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


def test_check_core_instruction_files_missing_codex(tmp_path):
    from synlynk.fleet import check_core_instruction_files

    (tmp_path / "CLAUDE.md").write_text("x")
    (tmp_path / "GEMINI.md").write_text("x")
    (tmp_path / "GROK.md").write_text("x")
    # AGENTS.md intentionally absent
    missing = check_core_instruction_files(tmp_path, agents=["codex", "claude"])
    assert "codex" in missing
    assert "claude" not in missing


def test_find_nested_product_state_dbs(tmp_path):
    from synlynk.fleet import find_nested_product_state_dbs

    nested = tmp_path / "worktrees" / "feat-x" / ".synlynk"
    nested.mkdir(parents=True)
    (nested / "state.db").write_bytes(b"")
    # non-product state.db should not match
    other = tmp_path / "worktrees" / "feat-y" / "data"
    other.mkdir(parents=True)
    (other / "state.db").write_bytes(b"")
    hits = find_nested_product_state_dbs(tmp_path)
    assert any(Path(h).name == "state.db" and ".synlynk" in Path(h).parts for h in hits)
    assert not any("feat-y" in h for h in hits)


def test_doctor_hard_fail_ignores_tc5():
    from synlynk.fleet import doctor_hard_fail

    assert doctor_hard_fail(
        tc_results={"tc2": True, "tc3": True, "tc5": False},
        missing_instructions=[],
        nested_state_dbs=[],
    ) is False
    assert doctor_hard_fail(
        tc_results={"tc2": False, "tc3": True, "tc5": True},
        missing_instructions=[],
        nested_state_dbs=[],
    ) is True
    assert doctor_hard_fail(
        tc_results={"tc2": True, "tc3": True, "tc5": True},
        missing_instructions=["codex"],
        nested_state_dbs=[],
    ) is True


def test_assert_not_nested_product_ledger_raises(tmp_path):
    from synlynk.fleet import assert_not_nested_product_ledger

    nested = str(tmp_path / "worktrees" / "job-x" / ".synlynk" / "state.db")
    with pytest.raises(RuntimeError, match="nested product state"):
        assert_not_nested_product_ledger(nested, home_writable=True)
    # home not writable: no raise
    assert_not_nested_product_ledger(nested, home_writable=False)


def test_is_nested_worktree_state_path():
    from synlynk.fleet import is_nested_worktree_state_path

    assert is_nested_worktree_state_path("/repo/worktrees/job-1/.synlynk/state.db")
    assert is_nested_worktree_state_path("/repo/.worktrees/feat/.synlynk/state.db")
    assert is_nested_worktree_state_path("/repo/.claude/worktrees/x/.synlynk/state.db")
    assert not is_nested_worktree_state_path(
        "/Users/me/.synlynk/projects/abc12345/state.db"
    )


def test_get_db_refuses_nested_primary_path(tmp_path, monkeypatch):
    """Primary DB_PATH under worktrees must raise before connect (#330 / S2a)."""
    import synlynk

    nested = tmp_path / "worktrees" / "job-x" / ".synlynk" / "state.db"
    nested.parent.mkdir(parents=True)
    monkeypatch.setattr(synlynk, "DB_PATH", str(nested))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="nested product state"):
        synlynk._get_db()
