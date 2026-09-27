"""Tests verifying _DEFAULT_MODELS_BY_TIER in synlynk.dispatch matches the 2026 SOTA catalog."""

import pytest
from synlynk.dispatch import (
    _DEFAULT_MODELS_BY_TIER,
    MODEL_TIER_FAST,
    MODEL_TIER_PRO,
    MODEL_TIER_REASONING,
    resolve_dispatch_model,
)
from synlynk.models import load_model_catalog


def test_no_deprecated_gemini_1_5_models_in_dispatch_defaults():
    """Ensure zero occurrences of deprecated gemini-1.5 models in dispatch defaults."""
    for tier, harness_map in _DEFAULT_MODELS_BY_TIER.items():
        for harness, model_id in harness_map.items():
            assert "gemini-1.5" not in model_id, f"Deprecated model found in {tier}.{harness}: {model_id}"


def test_default_models_by_tier_parity_with_catalog():
    """Verify _DEFAULT_MODELS_BY_TIER matches the 2026 SOTA model catalog in models.json."""
    catalog = load_model_catalog()
    catalog_tiers = catalog.get("tiers", {})

    for tier in (MODEL_TIER_FAST, MODEL_TIER_PRO, MODEL_TIER_REASONING):
        assert tier in _DEFAULT_MODELS_BY_TIER, f"Missing tier {tier} in dispatch defaults"
        assert tier in catalog_tiers, f"Missing tier {tier} in catalog"

        # Check agy tier alignment
        assert _DEFAULT_MODELS_BY_TIER[tier]["agy"] == catalog_tiers[tier]["agy"]

        # Check codex tier alignment
        assert _DEFAULT_MODELS_BY_TIER[tier]["codex"] == "gpt-5.6-luna"

        # Check grok tier alignment
        assert _DEFAULT_MODELS_BY_TIER[tier]["grok"] in ("grok-4.6", "grok-4.7")


def test_resolve_dispatch_model_agy_resolves_to_2026_models():
    """Verify resolve_dispatch_model resolves agy tiers to 2026 models."""
    fast_res = resolve_dispatch_model("agy", "simple syntax validation", model_tier="fast")
    assert fast_res["resolved_model"] == "gemini-3.7-flash-medium"

    pro_res = resolve_dispatch_model("agy", "multi-file refactor", model_tier="pro")
    assert pro_res["resolved_model"] in ("gemini-3.1-pro-low", "gemini-3.7-flash-high")

    reasoning_res = resolve_dispatch_model("agy", "architecture design", model_tier="reasoning")
    assert reasoning_res["resolved_model"] == "gemini-3.1-pro-high"
