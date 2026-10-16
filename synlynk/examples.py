from __future__ import annotations

"""Small examples for common Python tasks.

Requirements example: ``is_adult``
---------------------------------
Baseline requirements (the ``REQ`` IDs are stable references for review):

* REQ-ADULT-1: accept an age from 0 through 120, inclusive; reject other
  values with ``ValueError``.
* REQ-ADULT-2: return ``True`` at age 18 or older and ``False`` below 18.

The tests named with these IDs are the acceptance checks. When a requirement
changes, update its description and corresponding acceptance check together.
"""


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


def is_adult(age: int) -> bool:
    """Return whether an age is at least 18; reject ages outside 0..120."""
    if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 120:
        raise ValueError("age must be an integer from 0 through 120")
    return age >= 18
