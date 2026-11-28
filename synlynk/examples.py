from __future__ import annotations

"""Small examples for common Python tasks."""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


# Requirements are kept next to the function so they have one visible source
# of truth and can be traced directly to the acceptance test.
REQUIREMENTS: dict[str, str] = {
    "REQ-1": "Return a value already inside the inclusive range unchanged.",
    "REQ-2": "Return the lower bound when the value is below it.",
    "REQ-3": "Return the upper bound when the value is above it.",
    "REQ-4": "Raise ValueError when the lower bound exceeds the upper bound.",
}


def clamp(value: float, low: float, high: float) -> float:
    """Constrain ``value`` to the inclusive range from ``low`` to ``high``."""
    if low > high:
        raise ValueError("low must not exceed high")
    if value < low:
        return low
    if value > high:
        return high
    return value
