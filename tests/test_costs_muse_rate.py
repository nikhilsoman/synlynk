from synlynk.costs import _HARDCODED_FALLBACK_RATES, _model_rate_for_version


def test_muse_rate_is_not_the_generic_default():
    muse_rate = _HARDCODED_FALLBACK_RATES["models"]["muse-spark-1.3"]
    claude_sonnet_rate = _HARDCODED_FALLBACK_RATES["models"]["claude-sonnet-4-6"]
    assert muse_rate != claude_sonnet_rate, (
        "muse-spark-1.3 must not silently reuse the Claude Sonnet rate shape"
    )


def test_model_rate_for_version_returns_real_muse_rate():
    rate = _model_rate_for_version("muse-spark-1.3", agent="muse")
    assert rate == {"input": 0.00125, "output": 0.00425, "cache_read": 0.00015}
