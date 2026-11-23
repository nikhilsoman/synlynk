import ast
import os
import pytest
from tokenprice.catalog import calculate_cost, get_model_rates, normalize_model_id
from tokenprice.models import BillingMode


def test_modularity_zero_synlynk_imports():
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/tokenprice"))
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                with open(p, "r") as fh:
                    tree = ast.parse(fh.read(), filename=p)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith("synlynk"), f"Illegal synlynk import in {p}"
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            assert not node.module.startswith("synlynk"), f"Illegal synlynk import in {p}"


def test_model_normalization_and_rates():
    assert normalize_model_id("claude-3-5-sonnet-20241022") == "claude-3-5-sonnet"
    assert normalize_model_id("sonnet") == "claude-3-5-sonnet"
    assert normalize_model_id("gemini-2.0-flash") == "gemini-2.0-flash"

    rates = get_model_rates("claude-3-5-sonnet")
    assert rates is not None
    assert rates.input_per_m == 3.00
    assert rates.output_per_m == 15.00
    assert rates.cache_read_per_m == 0.30


def test_calculate_cost_nominal_and_subscription():
    res_api = calculate_cost(
        model="claude-3-5-sonnet",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=500_000,
        billing_mode=BillingMode.API,
    )
    # 1M in = $3.00, 100k out = $1.50, 500k cache read = $0.15 => total = $4.65
    assert round(res_api.nominal_usd, 2) == 4.65
    assert round(res_api.effective_usd, 2) == 4.65

    res_sub = calculate_cost(
        model="claude-3-5-sonnet",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=500_000,
        billing_mode=BillingMode.SUBSCRIPTION,
    )
    assert round(res_sub.nominal_usd, 2) == 4.65
    assert res_sub.effective_usd == 0.0
