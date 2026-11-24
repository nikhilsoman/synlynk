from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def shipping_cost(weight_kg: float, express: bool = False) -> float:
    """Calculate shipping cost for a package.

    Requirements are intentionally kept next to the implementation so this
    small example has an obvious source of truth:

    - REQ-1: reject negative package weights.
    - REQ-2: charge a $5 base fee plus $2 per kilogram.
    - REQ-3: add a $10 fee when express delivery is requested.
    """
    if weight_kg < 0:
        raise ValueError("weight_kg must be non-negative")

    return 5.0 + (2.0 * weight_kg) + (10.0 if express else 0.0)
