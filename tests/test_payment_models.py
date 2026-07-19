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
