import json
import os
import sqlite3

import pytest

from synlynk.costs import _estimate_tshirt_tokens
from synlynk.costs import check_budgets
from synlynk.costs import parse_costs_md as costs_parse_costs_md
from synlynk.db import _parse_costs_md as db_parse_costs_md


def test_cost_entries_has_provenance_columns(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    conn.close()
    assert "cost_source" in cols
    assert "estimate_basis" in cols
    assert "job_id" in cols


def test_cost_source_not_null_no_default(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens) "
            "VALUES ('2026-07-13', 'claude', 'claude-sonnet-4-6', 100, 50)"
        )
    conn.close()


def test_migration_backfills_existing_rows_as_legacy_unknown(project_dir, monkeypatch):
    """A DB created before this migration (no provenance columns, has rows) must
    backfill cost_source='legacy_unknown' on rebuild, never 'actual'.
    """

    import synlynk

    db_path = os.path.join(project_dir, "state.db")
    monkeypatch.setattr(synlynk, "DB_PATH", db_path)

    pre_conn = sqlite3.connect(db_path)
    pre_conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            story_id TEXT,
            epic_id INTEGER,
            phase_id INTEGER,
            total_cost_usd REAL,
            notes TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    pre_conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, total_cost_usd) "
        "VALUES ('2026-01-01', 'claude', 'claude-sonnet-4-6', 1000, 500, 0.01)"
    )
    pre_conn.commit()
    pre_conn.close()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, estimate_basis FROM cost_entries WHERE session_date='2026-01-01'"
    ).fetchone()
    conn.close()
    assert row == ("legacy_unknown", None)


def test_insert_cost_row_rejects_invalid_cost_source(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        _insert_cost_row(
            session_date="2026-07-13",
            agent="claude",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            cost_source="made_up_tier",
            total_cost_usd=0.01,
        )


def test_insert_cost_row_writes_a_row(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cost_source="actual",
        total_cost_usd=0.01,
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent, cost_source FROM cost_entries").fetchone()
    conn.close()
    assert row == ("claude", "actual")


def test_insert_cost_row_idempotent_on_job_id(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cost_source="estimated_tshirt",
        total_cost_usd=0.01,
        job_id="job-abc123",
    )
    _insert_cost_row(
        session_date="2026-07-13",
        agent="claude",
        model="claude-sonnet-4-6",
        input_tokens=200,
        output_tokens=80,
        cache_read_tokens=0,
        cost_source="actual",
        total_cost_usd=0.02,
        job_id="job-abc123",
    )
    conn = synlynk._get_db()
    rows = conn.execute(
        "SELECT input_tokens, cost_source FROM cost_entries WHERE job_id='job-abc123'"
    ).fetchall()
    conn.close()
    assert rows == [(200, "actual")]


def test_extract_tokens_basis_regex_pair():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Input tokens: 1,200\nOutput tokens: 340\n")
    assert (result.input_tokens, result.output_tokens) == (1200, 340)
    assert result.basis == "regex_pair"


def test_extract_tokens_basis_total_split():
    from synlynk.costs import extract_tokens

    result = extract_tokens("Total tokens: 1000")
    assert result.basis == "total_split"


def test_extract_tokens_basis_none():
    from synlynk.costs import extract_tokens

    result = extract_tokens("no token info in this output at all")
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.basis == "none"


def test_extract_tokens_still_unpacks_as_pair():
    from synlynk.costs import extract_tokens

    in_tokens, out_tokens = extract_tokens("Input tokens: 10\nOutput tokens: 5\n")
    assert (in_tokens, out_tokens) == (10, 5)


def test_load_model_rates_valid_file(project_dir):
    from synlynk.costs import _load_model_rates

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "rates_updated_at": "2026-07-13",
                "unit": "usd_per_1k_tokens",
                "models": {"claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003},
                "billing_mode": {"default": "subscription", "local": "actual"},
            },
            f,
        )
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["models"]["claude-sonnet-4-6"]["input"] == 0.003
    assert rates["billing_mode"]["default"] == "subscription"


def test_load_model_rates_missing_unit_falls_back(project_dir, capsys):
    from synlynk.costs import _load_model_rates

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {"models": {}, "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}},
            f,
        )
    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"] == {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}
    captured = capsys.readouterr()
    assert "unit" in captured.out.lower() or "unit" in captured.err.lower()


def test_init_writes_model_rates_json(tmp_path, monkeypatch):
    import synlynk

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    synlynk.init()
    rates_path = tmp_path / ".synlynk" / "model_rates.json"
    assert rates_path.exists()
    data = json.loads(rates_path.read_text())
    assert data["unit"] == "usd_per_1k_tokens"
    assert data["billing_mode"]["local"] == "actual"


from synlynk.costs import _resolve_cost_tier, update_costs


def test_resolve_cost_tier_regex_pair_subscription():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="regex_pair")
    assert (cost_source, basis) == ("estimated_token_rate", "regex_pair")


def test_resolve_cost_tier_regex_pair_local_is_actual():
    cost_source, basis = _resolve_cost_tier(agent="local", basis="regex_pair")
    assert cost_source == "actual"
    assert basis is None


def test_resolve_cost_tier_total_split_always_tshirt():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="total_split")
    assert (cost_source, basis) == ("estimated_tshirt", "total_split")


def test_resolve_cost_tier_none_returns_none():
    cost_source, basis = _resolve_cost_tier(agent="claude", basis="none")
    assert cost_source is None


def test_check_budgets_reports_failed_job_placeholders_separately(project_dir, monkeypatch, capsys):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "load_config", lambda: {
        "budget": {"limit_usd": 1000.0, "limit_requests": 1000}
    })
    monkeypatch.setattr(synlynk.costs, "parse_costs_md", lambda: (0.5, 3))

    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, model, input_tokens, output_tokens, "
        "total_cost_usd, cost_source, estimate_basis, notes) VALUES "
        "('2026-07-13', 'claude', 'claude-sonnet-4-6', 5000, 2000, 0.1, 'estimated_tshirt', "
        "'fixed_default', 'exec: failed job, exit 1')"
    )
    conn.commit()
    conn.close()

    check_budgets()
    captured = capsys.readouterr()
    assert "failed-job placeholder" in captured.out.lower()


def test_update_costs_writes_agent_name_not_username(project_dir, monkeypatch):
    """Regression test for the cost_entries agent-stores-username bug (Grok's review)."""
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    update_costs(
        "claude -p 'do the thing'", 1000, 500, 12.3,
        model_version="claude-sonnet-4-6", agent="claude",
    )
    conn = synlynk._get_db()
    row = conn.execute("SELECT agent FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "claude"


def test_costs_py_parse_costs_md_handles_est_prefix(project_dir, monkeypatch):
    import synlynk

    docs_dir = os.path.join(project_dir, "project-docs")
    os.makedirs(docs_dir, exist_ok=True)
    monkeypatch.setattr(synlynk, "_docs_dir", lambda: docs_dir)
    with open(os.path.join(docs_dir, "costs.md"), "w") as f:
        f.write("| 2026-07-13 10:00 | claude | 1 | 1000/500 | [est] $0.0270 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:05 | claude | 1 | 800/400 | [legacy] $0.0100 | exec: claude -p |\n")
        f.write("| 2026-07-13 10:10 | claude | 1 | 200/100 | $0.0050 | exec: claude -p |\n")
    total_usd, total_requests = costs_parse_costs_md()
    assert total_requests == 3
    assert round(total_usd, 4) == round(0.0270 + 0.0100 + 0.0050, 4)


def test_db_parse_costs_md_handles_prefixed_cost_column():
    content = "| 2026-07-13 | claude | claude-sonnet-4-6 | 1000 | 500 | 0 | [est] $0.0270 | note |\n"
    rows = db_parse_costs_md(content)
    assert len(rows) == 1
    assert rows[0]["total_cost_usd"] == 0.0270


from synlynk.db import cmd_cost_log


def test_cmd_cost_log_writes_estimated_manual_row(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    cmd_cost_log(agent="claude", tokens_in=2000, tokens_out=800, story_id=None, note="brainstorm session")
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, estimate_basis, input_tokens, output_tokens, phase_id, notes FROM cost_entries"
    ).fetchone()
    conn.close()
    assert row[0] == "estimated_manual"
    assert row[1] == "cli_manual_entry"
    assert (row[2], row[3]) == (2000, 800)
    assert row[5] == "brainstorm session"


def test_cmd_cost_log_with_story_id(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    conn = synlynk._get_db()
    conn.execute("INSERT INTO stories (story_id, title, discipline, phase) VALUES ('story-9', 'T', 'backend', 'build')")
    conn.commit()
    conn.close()
    cmd_cost_log(agent="claude", tokens_in=500, tokens_out=200, story_id="story-9", note=None)
    conn = synlynk._get_db()
    row = conn.execute("SELECT story_id FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "story-9"


def test_cmd_cost_log_rejects_negative_tokens(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    with pytest.raises(ValueError):
        cmd_cost_log(agent="claude", tokens_in=-1, tokens_out=200, story_id=None, note=None)


def test_run_investigation_writes_one_cost_row(project_dir, monkeypatch):
    import re
    from types import SimpleNamespace

    import synlynk
    import synlynk.support_engineer as se_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(synlynk, "LOGS_DIR", str(project_dir))
    monkeypatch.setattr(synlynk, "PROMPTS_DIR", str(project_dir))

    def fake_run(cmd, **kwargs):
        shell_cmd = cmd[2]
        match = re.search(r">\s*(?P<log>\S+)\s+2>&1", shell_cmd)
        assert match is not None
        log_path = match.group("log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as f:
            f.write(
                "Input tokens: 12\n"
                "Output tokens: 8\n"
                "# synlynk-meta\n"
                "model_version = claude-sonnet-4-6\n"
            )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(se_mod.subprocess, "run", fake_run)

    finding = {
        "signal_hash": "abc123",
        "type": "flatline",
        "severity": "high",
        "detail": "3 consecutive failures",
        "summary": "flatline detected",
    }
    agent_cfg = {"investigator": "claude"}

    se_mod._run_investigation(finding, agent_cfg)

    conn = synlynk._get_db()
    rows = conn.execute("SELECT cost_source FROM cost_entries").fetchall()
    conn.close()
    assert len(rows) == 1


def test_cmd_launch_writes_estimated_tshirt_not_bare_zero(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope=None: None)
    monkeypatch.setattr(synlynk.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda e: None)

    synlynk.cmd_launch("claude", story_id=None)

    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0


def test_reconcile_daemon_jobs_writes_cost_row(project_dir, monkeypatch):
    import synlynk
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, pid, status, started_at, enqueued_at, log_path) "
        "VALUES ('job-recon-1', 'claude', 'reconcile test', NULL, 999999, 'running', '2026-07-13T00:00:00', "
        "'2026-07-13T00:00:00', ?)",
        (os.path.join(project_dir, "job-recon-1.log"),),
    )
    conn.commit()
    conn.close()

    with open(os.path.join(project_dir, "job-recon-1.log"), "w") as f:
        f.write("Input tokens: 500\nOutput tokens: 200\n")

    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (pid, 0))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda pid, sig: None)

    jobs_mod._reconcile_daemon_jobs()

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, input_tokens FROM cost_entries WHERE job_id='job-recon-1'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == 500


def test_dispatch_writes_cost_row_even_on_zero_token_extraction(project_dir, monkeypatch):
    import synlynk
    import synlynk.dispatch as dispatch_mod
    from synlynk.costs import _TokenCounts

    class _FakeStdout:
        def readline(self):
            return b""

        def close(self):
            return None

    class _FakeProcess:
        returncode = 0
        stdout = _FakeStdout()

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    monkeypatch.setattr(synlynk, "_check_pre_exec_gate", lambda force=False: True)
    monkeypatch.setattr(synlynk, "generate_context", lambda scope="full", out_path=None: None)
    monkeypatch.setattr(synlynk, "check_budgets", lambda: None)
    monkeypatch.setattr(synlynk, "set_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synlynk, "_check_costs_freshness", lambda: None)
    monkeypatch.setattr(synlynk, "check_sentinel_patterns", lambda **_kwargs: None)
    monkeypatch.setattr(synlynk, "_check_instruction_drift", lambda: None)
    monkeypatch.setattr(synlynk, "log_telemetry_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synlynk, "get_username", lambda: "nikhil")
    monkeypatch.setattr(synlynk, "_dr_sync", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        synlynk,
        "_synlynk_project_docs_dir",
        lambda: os.path.join(project_dir, ".synlynk", "project-docs"),
    )
    monkeypatch.setattr(synlynk, "extract_tokens", lambda _text: _TokenCounts(0, 0, 0, "none"))
    monkeypatch.setattr(
        synlynk,
        "extract_model_version",
        lambda _text, agent=None: "claude-sonnet-4-6",
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **k: _FakeProcess())

    exit_code = dispatch_mod.exec_command(["claude", "-p", "hi"])

    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT cost_source, input_tokens, output_tokens FROM cost_entries"
    ).fetchone()
    conn.close()

    assert exit_code == 0
    assert row is not None
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0
    assert row[2] > 0


def test_update_costs_zero_tokens_still_writes_tshirt_row(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)
    update_costs("claude -p 'x'", 0, 0, 5.0, model_version="claude-sonnet-4-6", agent="claude")
    conn = synlynk._get_db()
    row = conn.execute("SELECT cost_source, input_tokens FROM cost_entries").fetchone()
    conn.close()
    assert row[0] == "estimated_tshirt"
    assert row[1] > 0


def test_update_costs_failed_job_marker_survives_short_cmd_truncation(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    long_command = "claude -p some-long-task-description-that-is-way-over-twenty-chars"
    update_costs(
        "[failed job] " + long_command,
        0,
        0,
        5.0,
        model_version="claude-sonnet-4-6",
        agent="claude",
    )

    conn = synlynk._get_db()
    notes = conn.execute("SELECT notes FROM cost_entries").fetchone()[0]
    conn.close()

    assert len(long_command) > 20
    assert "failed job" in notes
    assert notes.startswith("exec: [failed job] ")


def test_update_costs_costs_md_includes_provenance_prefix(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    monkeypatch.setattr(synlynk, "_is_migrated", lambda: True)

    costs_path = project_dir / ".synlynk" / "project-docs" / "costs.md"

    update_costs("claude -p 'x'", 0, 0, 5.0, model_version="claude-sonnet-4-6", agent="claude")
    estimated_line = costs_path.read_text().strip().splitlines()[-1]
    assert "[est] $" in estimated_line

    update_costs(
        "local -p 'x'",
        100,
        50,
        5.0,
        model_version="claude-sonnet-4-6",
        agent="local",
        basis="regex_pair",
    )
    actual_line = costs_path.read_text().strip().splitlines()[-1]
    assert "| $" in actual_line
    assert "[est] $" not in actual_line
    assert "[legacy] $" not in actual_line


def test_load_model_rates_missing_file_uses_hardcoded_default(project_dir):
    from synlynk.costs import _load_model_rates

    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"]["input"] == 0.003


def test_resolve_billing_mode_local_hardcoded_actual(project_dir):
    from synlynk.costs import _resolve_billing_mode

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "unit": "usd_per_1k_tokens",
                "models": {},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
                "billing_mode": {"default": "subscription", "local": "subscription"},
            },
            f,
        )
    os.chdir(project_dir)
    assert _resolve_billing_mode("local") == "actual"


def test_resolve_billing_mode_falls_back_to_default(project_dir):
    from synlynk.costs import _resolve_billing_mode

    os.makedirs(os.path.join(project_dir, ".synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, ".synlynk", "model_rates.json")
    with open(rates_path, "w") as f:
        json.dump(
            {
                "unit": "usd_per_1k_tokens",
                "models": {},
                "default": {"input": 0.003, "output": 0.015, "cache_read": 0.0},
                "billing_mode": {"default": "subscription"},
            },
            f,
        )
    os.chdir(project_dir)
    assert _resolve_billing_mode("codex") == "subscription"

def test_estimate_tshirt_tier1_story_estimate(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, discipline, phase, estimated_tokens) "
        "VALUES ('story-1', 'Test', 'backend', 'build', 4000)"
    )
    conn.commit()
    conn.close()
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id="story-1", discipline="backend", phase="build")
    assert basis == "story_estimate"
    assert in_t + out_t == 4000


def test_estimate_tshirt_tier2_historical_avg(project_dir, monkeypatch):
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'backend', 'build')",
            (f"story-hist-{i}",),
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500, cache_read_tokens=0,
            cost_source="actual", total_cost_usd=0.01, story_id=f"story-hist-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "historical_avg"
    assert (in_t, out_t) == (1000, 500)


def test_estimate_tshirt_tier3_fixed_default(project_dir, monkeypatch):
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="backend", phase="build")
    assert basis == "fixed_default"
    assert in_t > 0 and out_t > 0


def test_estimate_tshirt_ignores_estimated_tshirt_rows_in_history(project_dir, monkeypatch):
    """Historical averaging must not recycle guessed rows into future guesses (Grok's finding)."""
    import synlynk
    from synlynk.db import _insert_cost_row

    monkeypatch.setattr(synlynk, "DB_PATH", os.path.join(project_dir, "state.db"))
    conn = synlynk._get_db()
    for i in range(3):
        conn.execute(
            "INSERT INTO stories (story_id, title, discipline, phase) VALUES (?, 'T', 'frontend', 'build')",
            (f"story-guess-{i}",),
        )
    conn.commit()
    conn.close()
    for i in range(3):
        _insert_cost_row(
            session_date="2026-07-01", agent="claude", model="claude-sonnet-4-6",
            input_tokens=9999, output_tokens=9999, cache_read_tokens=0,
            cost_source="estimated_tshirt", estimate_basis="fixed_default",
            total_cost_usd=0.01, story_id=f"story-guess-{i}",
        )
    in_t, out_t, basis = _estimate_tshirt_tokens(story_id=None, discipline="frontend", phase="build")
    assert basis == "fixed_default"
    assert in_t != 9999


def test_insert_cost_row_reachable_via_pkg_lookup():
    import synlynk

    assert hasattr(synlynk, "_insert_cost_row")


def test_only_insert_cost_row_writes_to_cost_entries():
    """Every INSERT/UPDATE against cost_entries in the source tree must go
    through _insert_cost_row - no other call site is allowed to write directly.
    """

    allowed_files_with_direct_sql = {
        "synlynk/db.py",
    }
    repo_root = os.path.join(os.path.dirname(__file__), "..")
    violations = []
    for dirpath, _, filenames in os.walk(os.path.join(repo_root, "synlynk")):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            rel_path = os.path.relpath(os.path.join(dirpath, fname), repo_root)
            with open(os.path.join(dirpath, fname)) as f:
                content = f.read()
            if rel_path in allowed_files_with_direct_sql:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if "INSERT INTO cost_entries" in line or "UPDATE cost_entries" in line:
                    violations.append(f"{rel_path}:{lineno}")
    assert violations == [], f"Direct cost_entries writes outside db.py: {violations}"
