from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def calculate_total(price: float, quantity: int) -> float:
    """Calculate an order total from a price and quantity.

    Requirements:
    1. Both inputs must be non-negative.
    2. A valid total is ``price * quantity``.
    3. Invalid inputs raise ``ValueError``.
    """
    if price < 0 or quantity < 0:
        raise ValueError("price and quantity must be non-negative")
    return price * quantity
