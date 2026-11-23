"""Tests for token-breaker modularity and execution circuit breaking."""

import ast
import os
import pytest
from token_breaker.models import BreakerBudget, CircuitBreakerError, RepetitionStallError
from token_breaker.breaker import TokenCircuitBreaker


def test_modularity_zero_synlynk_imports():
    """Verify that packages/token-breaker/src contains ZERO imports of synlynk."""
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as pyfile:
                    tree = ast.parse(pyfile.read(), filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert not alias.name.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {alias.name}"
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                assert not node.module.startswith("synlynk"), f"Forbidden synlynk import in {fpath}: {node.module}"


def test_stream_token_limit_trips_breaker():
    """Verify generator stream trips when token budget is exceeded."""
    budget = BreakerBudget(max_tokens=100)
    breaker = TokenCircuitBreaker(budget)

    # 15 chunks of 10 tokens each = 150 tokens > 100
    raw_stream = (f"chunk-{i}" for i in range(15))
    wrapped = breaker.wrap_stream(raw_stream, tokens_per_chunk=10)

    yielded = []
    with pytest.raises(CircuitBreakerError, match="Token budget exceeded"):
        for chunk in wrapped:
            yielded.append(chunk)

    # First 10 chunks should yield fine (100 tokens), 11th chunk (110 tokens) trips
    assert len(yielded) == 10


def test_spend_limit_trips_breaker():
    """Verify spend budget tripping."""
    budget = BreakerBudget(max_cost_usd=1.0)
    breaker = TokenCircuitBreaker(budget)

    breaker.record_usage(tokens=1000, cost_usd=0.60)
    assert breaker.accumulated_cost_usd == 0.60

    with pytest.raises(CircuitBreakerError, match="Spend budget exceeded"):
        breaker.record_usage(tokens=1000, cost_usd=0.50)


def test_repetition_stall_trips_breaker():
    """Verify repetition stall tripping on consecutive errors."""
    budget = BreakerBudget(max_consecutive_errors=3)
    breaker = TokenCircuitBreaker(budget)

    breaker.record_error()
    breaker.record_error()
    assert breaker.consecutive_errors == 2

    with pytest.raises(RepetitionStallError, match="Repetition stall: 3 consecutive failures"):
        breaker.record_error()
