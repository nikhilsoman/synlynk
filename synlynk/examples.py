from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    """Return ``value`` constrained to the inclusive ``[low, high]`` range."""
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(high, value))
