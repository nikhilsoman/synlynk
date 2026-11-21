from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


#: Requirements Definition and Management example: every behavior of
#: ``clamp`` is defined once here and traced to exactly one test.
REQUIREMENTS: dict[str, str] = {
    "REQ-1": "A value inside [low, high] is returned unchanged.",
    "REQ-2": "A value below low returns low.",
    "REQ-3": "A value above high returns high.",
    "REQ-4": "Bounds with low > high raise ValueError.",
}


def clamp(value: float, low: float, high: float) -> float:
    """Constrain ``value`` to the inclusive range [``low``, ``high``].

    Implements REQUIREMENTS REQ-1 through REQ-4; each requirement is
    covered by the same-named test in tests/test_requirements_example.py.
    """
    if low > high:
        raise ValueError(f"low ({low}) must not exceed high ({high})")  # REQ-4
    if value < low:
        return low  # REQ-2
    if value > high:
        return high  # REQ-3
    return value  # REQ-1
