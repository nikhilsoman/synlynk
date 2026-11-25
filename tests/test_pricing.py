from synlynk import pricing


def test_known_model_prices_all_four_token_kinds(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {"m1": {"input": 0.003, "output": 0.015, "cache_read": 0.0000003}}})
    usd = pricing.price_usd("m1", input_tokens=1000, output_tokens=1000, cache_read_tokens=1_000_000, cache_creation_tokens=1000)
    # 1000*0.003/1000 + 1000*0.015/1000 + 1e6*0.0000003/1000 + 1000*(0.003*1.25)/1000
    assert abs(usd - (0.003 + 0.015 + 0.0003 + 0.00375)) < 1e-9


def test_explicit_cache_write_rate_wins(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {"m1": {"input": 0.003, "output": 0.015, "cache_read": 0.0, "cache_write": 0.01}}})
    assert abs(pricing.price_usd("m1", 0, 0, 0, 1000) - 0.01) < 1e-9


def test_unknown_model_is_none_never_a_default_rate(monkeypatch):
    monkeypatch.setattr(pricing, "_rates", lambda: {"models": {}, "default": {"input": 9, "output": 9, "cache_read": 9}})
    assert pricing.price_usd("claude-unknown", 1000, 1000, 0, 0) is None
