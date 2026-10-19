from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def clamp(value: float, low: float, high: float) -> float:
    """Return ``value`` constrained to the inclusive range [low, high]."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
