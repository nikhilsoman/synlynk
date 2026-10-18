from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def normalize_username(username: str) -> str:
    """Return a canonical username, enforcing its tracked requirements.

    REQ-001: Remove surrounding whitespace and convert the username to lowercase.
    REQ-002: Reject a username that is empty after whitespace is removed.
    """
    normalized = username.strip().lower()
    if not normalized:
        raise ValueError("username must not be empty")
    return normalized
