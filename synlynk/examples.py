from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def clamp(value: int, lo: int, hi: int) -> int:
    """Return ``value`` constrained to the inclusive ``[lo, hi]`` range."""
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return min(max(value, lo), hi)
