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
