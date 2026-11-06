"""Minimal example: build a small greeting function."""


def greet(name: str) -> str:
    """Return a friendly greeting for *name*.

    Raises:
        ValueError: If *name* is blank or whitespace-only.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    return f"Hello, {cleaned}!"
