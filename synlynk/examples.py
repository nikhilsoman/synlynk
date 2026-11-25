from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def calculate_shipping_cost(order_total: float) -> float:
    """Calculate shipping for an order using three traceable requirements.

    REQ-1: Charge a 5.99 standard fee for orders below 50.00.
    REQ-2: Ship orders of 50.00 or more for free.
    REQ-3: Reject negative order totals with ``ValueError``.
    """
    if order_total < 0:
        raise ValueError("order total cannot be negative")
    return 0.00 if order_total >= 50.00 else 5.99


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
