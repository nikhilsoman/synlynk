"""Per-model pricing interface. Unknown models are never priced at another model's rate."""
from typing import Optional

CACHE_WRITE_INPUT_MULTIPLIER = 1.25  # used only when a model has no explicit cache_write rate


def _rates() -> dict:
    from synlynk.costs import _load_model_rates

    return _load_model_rates()


def price_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> Optional[float]:
    rate = _rates().get("models", {}).get(model)
    if not rate:
        return None
    cache_write = rate.get("cache_write", rate["input"] * CACHE_WRITE_INPUT_MULTIPLIER)
    return (
        input_tokens * rate["input"]
        + output_tokens * rate["output"]
        + cache_read_tokens * rate.get("cache_read", 0.0)
        + cache_creation_tokens * cache_write
    ) / 1000.0
