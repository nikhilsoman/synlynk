"""Data models for token pricing and valuation."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BillingMode(str, Enum):
    API = "api"
    SUBSCRIPTION = "subscription"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ModelRates:
    __slots__ = ("model_id", "input_per_m", "output_per_m", "cache_write_per_m", "cache_read_per_m")

    model_id: str
    input_per_m: float
    output_per_m: float
    cache_write_per_m: float
    cache_read_per_m: float


@dataclass(frozen=True)
class CostResult:
    __slots__ = (
        "model",
        "nominal_usd",
        "effective_usd",
        "billing_mode",
        "input_tokens",
        "output_tokens",
        "cache_write_tokens",
        "cache_read_tokens",
    )

    model: str
    nominal_usd: float
    effective_usd: float
    billing_mode: BillingMode
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
