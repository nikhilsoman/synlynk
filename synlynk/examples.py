from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def word_count(text: str) -> int:
    """Return the number of whitespace-separated words in text."""
    return len(text.split())


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
