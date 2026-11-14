from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def clamp(value: int, low: int, high: int) -> int:
    """Return ``value`` constrained to the inclusive range ``[low, high]``."""
    if low > high:
        raise ValueError("low must be less than or equal to high")
    return min(max(value, low), high)
