from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def make_slug(text: str) -> str:
    """Return a lowercase, hyphen-separated slug for non-blank text."""
    normalized = "-".join(text.strip().lower().split())
    if not normalized:
        raise ValueError("text must contain at least one non-whitespace character")
    return normalized
