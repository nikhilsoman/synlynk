import json
import os
import sqlite3

import pytest


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

    os.makedirs(os.path.join(project_dir, "synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, "synlynk", "model_rates.json")
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

    os.makedirs(os.path.join(project_dir, "synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, "synlynk", "model_rates.json")
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


def test_load_model_rates_missing_file_uses_hardcoded_default(project_dir):
    from synlynk.costs import _load_model_rates

    os.chdir(project_dir)
    rates = _load_model_rates()
    assert rates["default"]["input"] == 0.003


def test_resolve_billing_mode_local_hardcoded_actual(project_dir):
    from synlynk.costs import _resolve_billing_mode

    os.makedirs(os.path.join(project_dir, "synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, "synlynk", "model_rates.json")
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

    os.makedirs(os.path.join(project_dir, "synlynk"), exist_ok=True)
    rates_path = os.path.join(project_dir, "synlynk", "model_rates.json")
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
