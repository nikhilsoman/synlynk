from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def calculate_discounted_price(price: float, discount_percent: float) -> float:
    """Return ``price`` after applying ``discount_percent``."""
    return price * (1 - discount_percent / 100)


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
