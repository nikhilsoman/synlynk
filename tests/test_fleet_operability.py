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


def test_no_unknown_terminal_label():
    from synlynk.fleet import terminal_status_for_unknown_exit

    assert "UNKNOWN" not in terminal_status_for_unknown_exit()
    assert terminal_status_for_unknown_exit().startswith("FAILED_UNVERIFIED")


def test_fleet_matrix_runs_table(project_dir):
    from synlynk import _get_db

    conn = _get_db()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fleet_matrix_runs)").fetchall()}
    assert {"run_id", "tier", "home", "cell", "status", "detail", "cost_usd", "ts"} <= cols
    conn.close()


def test_run_matrix_dry_marks_missing_instruction_red(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("CLAUDE.md", "GEMINI.md", "GROK.md"):
        (tmp_path / name).write_text("ok")
    # no AGENTS.md
    from synlynk.fleet import run_matrix_dry

    results = run_matrix_dry(str(tmp_path))
    codex_instr = [r for r in results if r.home == "codex" and r.cell == "instruction"]
    assert codex_instr and codex_instr[0].status == "red"


def test_run_matrix_dry_codex_gh_write_na(tmp_path):
    from synlynk.fleet import run_matrix_dry

    for name in ("CLAUDE.md", "GEMINI.md", "GROK.md", "AGENTS.md"):
        (tmp_path / name).write_text("ok")
    results = run_matrix_dry(str(tmp_path))
    codex_gh = [r for r in results if r.home == "codex" and r.cell == "gh_write"]
    assert codex_gh and codex_gh[0].status == "na"
    other_gh = [r for r in results if r.home != "codex" and r.cell == "gh_write"]
    assert other_gh == []


def test_record_matrix_run(project_dir):
    from synlynk import _get_db
    from synlynk.fleet import MatrixCellResult, new_run_id, record_matrix_run

    conn = _get_db()
    run_id = new_run_id()
    results = [
        MatrixCellResult(home="codex", cell="instruction", tier=1, status="red", detail="missing"),
    ]
    record_matrix_run(conn, run_id, results)
    row = conn.execute(
        "SELECT home, cell, status FROM fleet_matrix_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    conn.close()
    assert row == ("codex", "instruction", "red")


def test_selftest_matrix_flag_parsed():
    from synlynk.cli import build_parser

    args = build_parser().parse_args(["selftest", "--matrix"])
    assert args.matrix is True
    assert args.budget is None


def test_selftest_matrix_budget_flag_parsed():
    from synlynk.cli import build_parser

    args = build_parser().parse_args(["selftest", "--matrix", "--live", "--budget", "5.5"])
    assert args.matrix is True
    assert args.live is True
    assert args.budget == 5.5


def test_preflight_blocks_dispatch_helper(tmp_path):
    from synlynk.fleet import preflight_blocks_dispatch

    # Bare sandbox (no instruction files): do not block — unit-test friendly
    assert not preflight_blocks_dispatch(
        "codex",
        missing_instructions=["codex"],
        force_agent=False,
        root=tmp_path,
    )
    # Real project shape: at least one instruction file present
    (tmp_path / "CLAUDE.md").write_text("ok")
    assert preflight_blocks_dispatch(
        "codex",
        missing_instructions=["codex"],
        force_agent=False,
        root=tmp_path,
    )
    assert not preflight_blocks_dispatch(
        "codex",
        missing_instructions=["codex"],
        force_agent=True,
        root=tmp_path,
    )
    assert not preflight_blocks_dispatch(
        "codex",
        missing_instructions=[],
        force_agent=False,
        root=tmp_path,
    )
    assert not preflight_blocks_dispatch(
        "local",
        missing_instructions=["local"],
        force_agent=False,
        root=tmp_path,
    )


def test_tier_for_agent_experimental_and_supported(project_dir):
    from synlynk import _get_db
    from synlynk.fleet import MatrixCellResult, new_run_id, record_matrix_run, tier_for_agent

    assert tier_for_agent(None, "local") == "experimental"
    assert tier_for_agent(None, "unknown-agent") == "unsupported"

    conn = _get_db()
    run_id = new_run_id()
    # all green dry for claude → supported (no live yet)
    record_matrix_run(
        conn,
        run_id,
        [
            MatrixCellResult(home="claude", cell="instruction", tier=1, status="green"),
            MatrixCellResult(home="claude", cell="nested_state", tier=1, status="green"),
        ],
    )
    assert tier_for_agent(conn, "claude") == "supported"

    # red dry → unsupported
    run2 = new_run_id()
    record_matrix_run(
        conn,
        run2,
        [MatrixCellResult(home="agy", cell="instruction", tier=1, status="red")],
    )
    assert tier_for_agent(conn, "agy") == "unsupported"

    # live green within window → proven
    run3 = new_run_id()
    record_matrix_run(
        conn,
        run3,
        [
            MatrixCellResult(home="grok", cell="instruction", tier=1, status="green"),
            MatrixCellResult(
                home="grok", cell="live_self:grok", tier=2, status="green", cost_usd=0.0
            ),
        ],
    )
    assert tier_for_agent(conn, "grok") == "proven"
    conn.close()


def test_live_matrix_budget_abort():
    from synlynk.fleet import MatrixCellResult, run_matrix_live

    calls = {"n": 0}

    def fake_dispatch(home):
        calls["n"] += 1
        return MatrixCellResult(
            home=home,
            cell=f"live_self:{home}",
            tier=2,
            status="green",
            cost_usd=6.0,
            detail="mock",
        )

    results = run_matrix_live(".", budget_usd=10.0, dispatch_fn=fake_dispatch)
    assert any(r.status == "incomplete" for r in results)
    # first cell 6, second would be 12 > 10
    greens = [r for r in results if r.status == "green"]
    assert len(greens) == 1
    assert calls["n"] >= 1


def test_live_matrix_default_zero_cost_mock():
    from synlynk.fleet import run_matrix_live

    results = run_matrix_live(".", budget_usd=10.0)
    assert len(results) == len(CORE_FLEET)
    assert all(r.status == "green" for r in results)
    assert all(r.cost_usd == 0.0 for r in results)
