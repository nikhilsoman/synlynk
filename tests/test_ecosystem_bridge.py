"""Verification tests for synlynk.ecosystem bridge facade and standalone suite."""

import pytest
from synlynk.ecosystem import tokenprice, tokentrail, worktree_lease, harness_spec, token_breaker
from synlynk.pr_check import check_cost_provenance_gate
from synlynk.constitution import CONSTITUTION_LAWS, DeliveryTier


def test_ecosystem_modules_importable():
    """Verify that all 5 standalone packages in packages/ are imported through synlynk.ecosystem."""
    assert tokenprice is not None
    assert tokentrail is not None
    assert worktree_lease is not None
    assert harness_spec is not None
    assert token_breaker is not None


def test_tokenprice_standalone_calculation():
    """Verify rate calculation through ecosystem facade."""
    from tokenprice.catalog import calculate_cost, get_model_rates
    rates = get_model_rates("claude-3-5-sonnet")
    assert rates.input_per_m == 3.0
    res = calculate_cost("claude-3-5-sonnet", input_tokens=1000, output_tokens=1000)
    assert res.nominal_usd > 0


def test_tokentrail_transcript_models():
    """Verify tokentrail models through ecosystem facade."""
    from tokentrail.models import TokenUsage
    u = TokenUsage(100, 200, 300, 400)
    assert u.total_tokens == 1000


def test_worktree_lease_manager():
    """Verify worktree_lease manager through ecosystem facade."""
    from worktree_lease.manager import WorktreeLeaseManager
    mgr = WorktreeLeaseManager(repo_root=".")
    assert mgr.base_dir.endswith(".worktrees")


def test_harness_spec_probe():
    """Verify harness_spec probing through ecosystem facade."""
    from harness_spec.probe import probe_all_known
    contracts = probe_all_known()
    assert "claude" in contracts


def test_token_breaker_trip():
    """Verify token_breaker tripping through ecosystem facade."""
    from token_breaker.models import BreakerBudget, CircuitBreakerError
    from token_breaker.breaker import TokenCircuitBreaker
    breaker = TokenCircuitBreaker(BreakerBudget(max_tokens=10))
    with pytest.raises(CircuitBreakerError):
        breaker.record_usage(tokens=11)


def test_constitutional_law_3_tier_3_injected():
    """Verify Law 3 is Tier 3 INJECTED in synlynk constitution."""
    law3 = CONSTITUTION_LAWS["law-3"]
    assert law3.tier == DeliveryTier.INJECTED
    assert "Cost Traceability" in law3.name


def test_cost_provenance_gate():
    """Verify PR check cost provenance gate."""
    res = check_cost_provenance_gate(".")
    assert res["passed"] is True
    assert res["tier"] == "injected"
