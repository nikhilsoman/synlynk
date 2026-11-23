"""Canonical model pricing catalog and valuation math."""

from typing import Dict, List, Optional
from tokenprice.models import ModelRates, CostResult, BillingMode

# Rates per 1,000,000 tokens in USD
_DEFAULT_CATALOG: Dict[str, ModelRates] = {
    # Anthropic Claude
    "claude-3-7-sonnet": ModelRates("claude-3-7-sonnet", 3.00, 15.00, 3.75, 0.30),
    "claude-3-5-sonnet": ModelRates("claude-3-5-sonnet", 3.00, 15.00, 3.75, 0.30),
    "claude-3-5-haiku": ModelRates("claude-3-5-haiku", 0.80, 4.00, 1.00, 0.08),
    "claude-3-opus": ModelRates("claude-3-opus", 15.00, 75.00, 18.75, 1.50),
    # Google Gemini
    "gemini-2.5-pro": ModelRates("gemini-2.5-pro", 1.25, 5.00, 1.25, 0.3125),
    "gemini-2.0-flash": ModelRates("gemini-2.0-flash", 0.10, 0.40, 0.10, 0.025),
    "gemini-1.5-pro": ModelRates("gemini-1.5-pro", 1.25, 5.00, 1.25, 0.3125),
    "gemini-1.5-flash": ModelRates("gemini-1.5-flash", 0.075, 0.30, 0.075, 0.01875),
    # OpenAI
    "gpt-4o": ModelRates("gpt-4o", 2.50, 10.00, 2.50, 1.25),
    "gpt-4o-mini": ModelRates("gpt-4o-mini", 0.15, 0.60, 0.15, 0.075),
    "o1": ModelRates("o1", 15.00, 60.00, 15.00, 7.50),
    "o1-mini": ModelRates("o1-mini", 3.00, 12.00, 3.00, 1.50),
    "o3-mini": ModelRates("o3-mini", 1.10, 4.40, 1.10, 0.55),
    # xAI Grok
    "grok-3": ModelRates("grok-3", 2.00, 10.00, 2.00, 0.50),
    "grok-2": ModelRates("grok-2", 2.00, 10.00, 2.00, 0.50),
    # Meta Llama / DeepSeek (OpenRouter rates)
    "deepseek-r1": ModelRates("deepseek-r1", 0.55, 2.19, 0.55, 0.14),
    "deepseek-v3": ModelRates("deepseek-v3", 0.14, 0.28, 0.14, 0.03),
}

_ALIASES: Dict[str, str] = {
    "sonnet": "claude-3-5-sonnet",
    "sonnet-3.5": "claude-3-5-sonnet",
    "sonnet-3.7": "claude-3-7-sonnet",
    "haiku": "claude-3-5-haiku",
    "opus": "claude-3-opus",
    "flash": "gemini-2.0-flash",
    "pro": "gemini-2.5-pro",
    "gpt4o": "gpt-4o",
    "gpt4o-mini": "gpt-4o-mini",
}


def normalize_model_id(model: str) -> str:
    cleaned = (model or "").strip().lower()
    # Strip date suffixes, e.g. claude-3-5-sonnet-20241022 -> claude-3-5-sonnet
    for base in _DEFAULT_CATALOG:
        if cleaned.startswith(base):
            return base
    return _ALIASES.get(cleaned, cleaned)


def get_model_rates(model: str) -> Optional[ModelRates]:
    norm = normalize_model_id(model)
    return _DEFAULT_CATALOG.get(norm)


def list_models() -> List[str]:
    return sorted(_DEFAULT_CATALOG.keys())


def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    billing_mode: BillingMode = BillingMode.API,
    custom_rates: Optional[ModelRates] = None,
) -> CostResult:
    rates = custom_rates or get_model_rates(model)
    if rates is None:
        # Fallback to standard tier rates if unknown model
        rates = ModelRates(model, 3.00, 15.00, 3.75, 0.30)

    in_cost = (input_tokens / 1_000_000.0) * rates.input_per_m
    out_cost = (output_tokens / 1_000_000.0) * rates.output_per_m
    cw_cost = (cache_write_tokens / 1_000_000.0) * rates.cache_write_per_m
    cr_cost = (cache_read_tokens / 1_000_000.0) * rates.cache_read_per_m

    nominal_usd = round(in_cost + out_cost + cw_cost + cr_cost, 6)

    if billing_mode == BillingMode.SUBSCRIPTION:
        effective_usd = 0.0
    else:
        effective_usd = nominal_usd

    return CostResult(
        model=model,
        nominal_usd=nominal_usd,
        effective_usd=effective_usd,
        billing_mode=billing_mode,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_write_tokens,
        cache_read_tokens=cache_read_tokens,
    )
