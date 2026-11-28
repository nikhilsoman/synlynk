from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def calculate_discount(subtotal: float, rate: float) -> float:
    """Return a discounted subtotal while keeping requirements traceable.

    Requirements:
    - REQ-001: accept a non-negative subtotal and a discount rate from 0 to 100.
    - REQ-002: reject values outside those ranges with ``ValueError``.
    - REQ-003: return the resulting amount rounded to two decimal places.

    The requirement IDs are intentionally kept next to the implementation so
    changes can be reviewed against the acceptance tests.
    """
    if subtotal < 0 or not 0 <= rate <= 100:
        raise ValueError("subtotal must be non-negative and rate must be 0-100")
    return round(subtotal * (1 - rate / 100), 2)
