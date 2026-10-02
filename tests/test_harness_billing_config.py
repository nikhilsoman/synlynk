import json
from pathlib import Path

import pytest


HARNESSES = ("claude", "codex", "agy", "grok")
CONFIG_PATH = Path(__file__).parents[1] / ".synlynk" / "config.json"


def _quad_harness_billing():
    return {
        harness: {
            "payment_mode": "subscription",
            "monthly_base_fee_usd": 30.0 if harness == "grok" else 20.0,
            "projected_monthly_tokens": 10_000_000,
            "allow_extra_usage": False,
        }
        for harness in HARNESSES
    }


def test_repository_config_has_quad_harness_subscription_billing():
    config = json.loads(CONFIG_PATH.read_text())
    billing = config["harness_billing"]

    assert set(billing) == set(HARNESSES)
    assert sum(item["monthly_base_fee_usd"] for item in billing.values()) == pytest.approx(90.0)
    for harness in HARNESSES:
        assert billing[harness]["payment_mode"] == "subscription"
        assert billing[harness]["projected_monthly_tokens"] == 10_000_000
        assert billing[harness]["allow_extra_usage"] is False
    assert billing["grok"]["monthly_base_fee_usd"] == 30.0


def test_payment_model_config_resolves_all_harnesses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"harness_billing": _quad_harness_billing()})
    )

    from synlynk.costs import _payment_model_config_for_agent

    for harness in HARNESSES:
        config = _payment_model_config_for_agent(harness)
        assert config["mode"] == "subscription"
        assert config["monthly_base_fee_usd"] == (30.0 if harness == "grok" else 20.0)


def test_subscription_value_is_amortized_and_differs_from_api_equivalent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(
        json.dumps({"harness_billing": _quad_harness_billing()})
    )

    from synlynk.costs import resolve_payment_value

    values = {harness: resolve_payment_value(harness, 1_000, 500) for harness in HARNESSES}
    for value in values.values():
        assert value.mode == "subscription"
        assert value.actual_usd > 0
        assert value.actual_usd != value.api_equivalent_usd
    assert values["grok"].actual_usd > values["claude"].actual_usd
