"""Data models and exceptions for token-breaker."""

from dataclasses import dataclass
from typing import Optional


class CircuitBreakerError(Exception):
    """Raised when token or spend limits are exceeded."""
    pass


class RepetitionStallError(CircuitBreakerError):
    """Raised when repetitive error loops or output stalls are detected."""
    pass


@dataclass
class BreakerBudget:
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_turns: Optional[int] = None
    max_consecutive_errors: int = 5
