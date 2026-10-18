from __future__ import annotations

"""Small examples for common Python tasks."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
