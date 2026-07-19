import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_load_config_defaults_payment_models_to_empty_dict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk as sl

    config = sl.load_config()
    assert config["payment_models"] == {}


def test_load_config_preserves_existing_payment_models_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump(
            {
                "payment_models": {
                    "codex": {
                        "mode": "subscription",
                        "tier_quota_tokens_in": 2000000,
                        "tier_quota_tokens_out": 500000,
                        "overage_rate_per_1k_in": 0.003,
                        "overage_rate_per_1k_out": 0.015,
                    }
                }
            },
            f,
        )

    import synlynk as sl

    config = sl.load_config()
    assert config["payment_models"]["codex"]["mode"] == "subscription"
    assert config["payment_models"]["codex"]["tier_quota_tokens_in"] == 2000000


def test_load_config_backfills_payment_models_into_existing_config_without_section(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"budget": {"limit_usd": 50}}, f)

    import synlynk as sl

    config = sl.load_config()
    assert config["payment_models"] == {}
    assert config["budget"]["limit_usd"] == 50


def test_migrate_db_creates_credit_grants_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, sqlite3

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    sl._migrate_db(conn)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "credit_grants" in tables

    cols = {row[1] for row in conn.execute("PRAGMA table_info(credit_grants)")}
    assert cols == {
        "id",
        "agent",
        "face_value_usd",
        "remaining_usd",
        "granted_at",
        "expires_at",
        "note",
    }
    conn.close()


def test_migrate_db_credit_grants_creation_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, sqlite3

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    sl._migrate_db(conn)
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 25.0, '2026-07-18')"
    )
    conn.commit()
    sl._migrate_db(conn)  # second call must not wipe existing rows

    count = conn.execute("SELECT COUNT(*) FROM credit_grants").fetchone()[0]
    assert count == 1
    conn.close()


def _write_config(tmp_path, payment_models):
    import json
    import os

    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"payment_models": payment_models}, f)


def test_resolve_payment_value_pay_as_you_go_matches_api_equivalent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("grok", tokens_in=1000, tokens_out=1000)
    assert result.mode == "pay_as_you_go"
    assert result.actual_usd == result.api_equivalent_usd
    assert result.api_equivalent_usd > 0


def test_resolve_payment_value_subscription_within_quota_is_free(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 2000000,
                "tier_quota_tokens_out": 500000,
                "overage_rate_per_1k_in": 0.003,
                "overage_rate_per_1k_out": 0.015,
            }
        },
    )
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("codex", tokens_in=1000, tokens_out=500)
    assert result.mode == "subscription"
    assert result.actual_usd == 0.0
    assert result.api_equivalent_usd > 0
    assert result.quota_pct_used is not None
    assert result.quota_pct_used < 1.0


def test_resolve_payment_value_subscription_overage_bills_only_the_excess(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 1000,
                "tier_quota_tokens_out": 1000,
                "overage_rate_per_1k_in": 0.003,
                "overage_rate_per_1k_out": 0.015,
            }
        },
    )
    import synlynk as sl
    from synlynk.quota import _upsert_agent_quota

    _upsert_agent_quota(
        "codex",
        "monthly",
        limit_tokens=1000,
        used_tokens=800,
        model="unknown",
        unit="tokens",
    )
    _upsert_agent_quota(
        "codex",
        "monthly",
        limit_tokens=1000,
        used_tokens=800,
        model="out",
        unit="tokens",
    )

    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("codex", tokens_in=500, tokens_out=500)
    expected_overage_usd = (300 / 1000 * 0.003) + (300 / 1000 * 0.015)
    assert result.mode == "subscription"
    assert abs(result.actual_usd - expected_overage_usd) < 0.0001
    assert result.quota_pct_used == 1.0


def test_resolve_payment_value_subscription_bills_marginal_overage_not_cumulative(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 1000,
                "tier_quota_tokens_out": 1000000,
                "overage_rate_per_1k_in": 1.0,
                "overage_rate_per_1k_out": 0.0,
            }
        },
    )
    import synlynk as sl
    from synlynk.quota import _upsert_agent_quota

    _upsert_agent_quota(
        "codex",
        "monthly",
        limit_tokens=1000,
        used_tokens=1000,
        model="unknown",
        unit="tokens",
    )
    _upsert_agent_quota(
        "codex",
        "monthly",
        limit_tokens=1000000,
        used_tokens=0,
        model="out",
        unit="tokens",
    )

    from synlynk.costs import resolve_payment_value

    pv1 = resolve_payment_value("codex", tokens_in=500, tokens_out=0)
    assert pv1.actual_usd == pytest.approx(0.5, abs=1e-6)

    pv2 = resolve_payment_value("codex", tokens_in=100, tokens_out=0)
    assert pv2.actual_usd == pytest.approx(0.1, abs=1e-6)

    conn = sl._get_db()
    row = conn.execute(
        "SELECT used_tokens FROM agent_quotas "
        "WHERE agent='codex' AND quota_type='monthly' AND unit='tokens' AND model='unknown'"
    ).fetchone()
    conn.close()
    assert row[0] == 1600


def test_resolve_payment_value_credit_grant_consumes_balance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"agy": {"mode": "credit_grant"}})
    import synlynk as sl

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 25.0, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("agy", tokens_in=1000, tokens_out=1000)
    assert result.mode == "credit_grant"
    assert result.actual_usd == 0.0
    assert result.credit_remaining_usd is not None
    assert result.credit_remaining_usd < 25.0

    conn = sl._get_db()
    remaining = conn.execute(
        "SELECT remaining_usd FROM credit_grants WHERE agent='agy'"
    ).fetchone()[0]
    conn.close()
    assert remaining == result.credit_remaining_usd


def test_resolve_payment_value_credit_grant_falls_back_when_exhausted(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"agy": {"mode": "credit_grant"}})
    import synlynk as sl

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 0.0001, 0.0001, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("agy", tokens_in=1000, tokens_out=1000)
    assert result.mode == "credit_grant"
    assert result.actual_usd > 0
    assert result.credit_remaining_usd == 0.0


def test_resolve_payment_value_credit_grant_chains_across_multiple_grants(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"agy": {"mode": "credit_grant"}})
    import synlynk as sl
    import synlynk.costs as costs

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 5.0, 5.0, '2026-07-01')"
    )
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 10.0, 10.0, '2026-07-10')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(costs, "extract_model_version", lambda output_text, agent=None: "stub")
    monkeypatch.setattr(
        costs,
        "_model_rate_for_version",
        lambda model_version, agent=None: {"input": 0.078, "output": 0.0, "cache_read": 0.0},
    )

    from synlynk.costs import resolve_payment_value

    pv = resolve_payment_value("agy", 100000, 0)
    assert pv.actual_usd == pytest.approx(0.0, abs=1e-6)

    conn = sl._get_db()
    remaining = conn.execute(
        "SELECT remaining_usd FROM credit_grants WHERE agent='agy' ORDER BY granted_at ASC"
    ).fetchall()
    conn.close()
    assert remaining[0][0] == pytest.approx(0.0, abs=1e-6)
    assert remaining[1][0] == pytest.approx(7.2, abs=1e-6)


def test_resolve_payment_value_unconfigured_agent_defaults_pay_as_you_go(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("claude", tokens_in=100, tokens_out=100)
    assert result.mode == "pay_as_you_go"


def test_update_costs_writes_actual_and_api_equivalent_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    monkeypatch.setattr(sl, "DB_PATH", os.path.join(tmp_path, ".synlynk", "state.db"))
    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 1000000,
                "tier_quota_tokens_out": 1000000,
                "overage_rate_per_1k_in": 0.003,
                "overage_rate_per_1k_out": 0.015,
            }
        },
    )

    import inspect

    from synlynk.costs import resolve_payment_value
    from synlynk.db import _insert_cost_row

    payment_value = resolve_payment_value("codex", tokens_in=1000, tokens_out=1000)
    signature = inspect.signature(_insert_cost_row)
    assert "api_equivalent_usd" in signature.parameters
    assert "actual_usd" in signature.parameters
    assert "payment_mode" in signature.parameters

    source = inspect.getsource(_insert_cost_row)
    assert "api_equivalent_usd" in source
    assert "actual_usd" in source
    assert "payment_mode" in source
    assert payment_value.mode == "subscription"
    assert payment_value.api_equivalent_usd > 0
    assert payment_value.actual_usd == 0.0


def test_costs_md_shows_two_dollar_columns_for_subscription_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    monkeypatch.setattr(sl, "DB_PATH", os.path.join(tmp_path, ".synlynk", "state.db"))
    monkeypatch.setattr(sl, "_is_migrated", lambda: True)
    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 1000000,
                "tier_quota_tokens_out": 1000000,
                "overage_rate_per_1k_in": 0.003,
                "overage_rate_per_1k_out": 0.015,
            }
        },
    )

    sl.update_costs("codex exec", in_tokens=1000, out_tokens=1000, duration=10, agent="codex")

    costs_file = os.path.join(sl._synlynk_project_docs_dir(), "costs.md")
    with open(costs_file) as f:
        content = f.read()

    assert "[in-quota]" in content


def test_parse_costs_md_sums_actual_not_api_equivalent_for_new_format_rows(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.costs import parse_costs_md

    monkeypatch.setattr(sl, "DB_PATH", os.path.join(tmp_path, ".synlynk", "state.db"))
    monkeypatch.setattr(sl, "_docs_dir", sl._synlynk_project_docs_dir)

    docs_dir = sl._synlynk_project_docs_dir()
    os.makedirs(docs_dir, exist_ok=True)
    costs_file = os.path.join(docs_dir, "costs.md")
    with open(costs_file, "w") as f:
        f.write(
            "| 2026-07-18 10:00 | codex | 1 | 1000/1000 | [est] $5.0000 | $0.0000 [in-quota] | exec: codex |\n"
        )
        f.write(
            "| 2026-07-18 10:05 | codex | 1 | 1000/1000 | [est] $5.0000 | $1.2300 [overage] | exec: codex |\n"
        )

    total_usd, total_requests = parse_costs_md()
    assert total_requests == 2
    assert round(total_usd, 4) == 1.23


def test_cmd_credit_grant_inserts_row(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.db import cmd_credit_grant

    cmd_credit_grant(agent="agy", amount=25.0, expires=None, note="Q3 promo credit")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT agent, face_value_usd, remaining_usd, note FROM credit_grants WHERE agent='agy'"
    ).fetchone()
    conn.close()
    assert row == ("agy", 25.0, 25.0, "Q3 promo credit")

    captured = capsys.readouterr()
    assert "25.00" in captured.out


def test_cmd_credit_grant_rejects_negative_amount(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.db import cmd_credit_grant
    import pytest

    with pytest.raises(ValueError):
        cmd_credit_grant(agent="agy", amount=-50.0, expires=None, note=None)


def test_check_budgets_prints_payment_model_rollup(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    _write_config(
        tmp_path,
        {
            "codex": {
                "mode": "subscription",
                "tier_quota_tokens_in": 1000000,
                "tier_quota_tokens_out": 1000000,
                "overage_rate_per_1k_in": 0.003,
                "overage_rate_per_1k_out": 0.015,
            },
            "agy": {"mode": "credit_grant"},
        },
    )
    conn = sl._get_db()
    sl._migrate_db(conn)
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 14.20, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(sl, "_is_migrated", lambda: True)
    sl.update_costs("codex exec", in_tokens=1000, out_tokens=1000, duration=10, agent="codex")
    from synlynk.db import _insert_cost_row

    _insert_cost_row(
        session_date="2026-07-19 10:30",
        agent="agy",
        model="unknown",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cost_source="actual",
        estimate_basis=None,
        total_cost_usd=0.0,
        api_equivalent_usd=0.0,
        actual_usd=0.0,
        payment_mode="credit_grant",
        notes="manual payment-model test",
    )

    sl.check_budgets()
    captured = capsys.readouterr()
    assert "Payment Models" in captured.out
    assert "codex" in captured.out
    assert "subscription" in captured.out
    assert "agy" in captured.out
    assert "14.20" in captured.out
