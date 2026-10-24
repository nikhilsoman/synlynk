from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def clamp(value: float, lower: float, upper: float) -> float:
    """Return ``value`` limited to the inclusive range ``[lower, upper]``."""
    if lower > upper:
        raise ValueError("lower bound must not exceed upper bound")
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value
