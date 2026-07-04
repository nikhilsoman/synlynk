"""Regression tests for synlynk module re-exports during modularisation."""


def test_constants_importable_from_package():
    from synlynk import AGENT_CAPABILITY_BASELINES, QUOTA_PATTERNS, VERSION

    assert isinstance(VERSION, str)
    assert "claude" in AGENT_CAPABILITY_BASELINES
    assert isinstance(QUOTA_PATTERNS, list)
