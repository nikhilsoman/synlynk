import json
import os
import sys

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


def test_resolve_payment_value_unconfigured_agent_defaults_pay_as_you_go(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    import os

    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("claude", tokens_in=100, tokens_out=100)
    assert result.mode == "pay_as_you_go"
