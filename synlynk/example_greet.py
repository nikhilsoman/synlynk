"""Minimal example function used by tests/test_example_greet.py."""


def greet(name: str) -> str:
    """Return a greeting for `name`, falling back to "stranger" when blank."""
    cleaned = name.strip()
    if not cleaned:
        return "Hello, stranger!"
    return f"Hello, {cleaned}!"
