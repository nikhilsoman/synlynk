from __future__ import annotations

"""Small examples for common Python tasks."""

from dataclasses import dataclass, replace
from typing import Iterable, Mapping


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]


# --- Requirements Definition and Management ---------------------------------
#
# A tiny catalog + one function. Requirements are first-class records that can
# be defined, status-updated, and checked for test-trace coverage. ``clamp``
# is the subject function those requirements specify.

VALID_REQUIREMENT_STATUSES = frozenset({"open", "satisfied", "deferred"})


@dataclass(frozen=True)
class Requirement:
    """A single requirement: identifier, statement, and lifecycle status."""

    id: str
    statement: str
    status: str = "open"


def define_requirements(
    specs: Iterable[tuple[str, str]],
) -> dict[str, Requirement]:
    """Build a catalog from ``(id, statement)`` pairs.

    Duplicate ids are rejected so the catalog stays a 1:1 map.
    """
    catalog: dict[str, Requirement] = {}
    for req_id, statement in specs:
        if req_id in catalog:
            raise ValueError(f"duplicate requirement id: {req_id}")
        catalog[req_id] = Requirement(id=req_id, statement=statement)
    return catalog


def set_requirement_status(
    catalog: Mapping[str, Requirement],
    req_id: str,
    status: str,
) -> dict[str, Requirement]:
    """Return a new catalog with ``req_id`` moved to ``status``."""
    if status not in VALID_REQUIREMENT_STATUSES:
        raise ValueError(f"unknown requirement status: {status}")
    if req_id not in catalog:
        raise KeyError(req_id)
    updated = dict(catalog)
    updated[req_id] = replace(catalog[req_id], status=status)
    return updated


def uncovered_requirement_ids(
    catalog: Mapping[str, Requirement],
    traced_ids: Iterable[str],
) -> list[str]:
    """Return catalog ids that still need a test trace (open, untraced)."""
    traced = set(traced_ids)
    return [
        req_id
        for req_id, req in catalog.items()
        if req.status == "open" and req_id not in traced
    ]


def clamp(value: float, lo: float, hi: float) -> float:
    """Constrain ``value`` to the inclusive range ``[lo, hi]``.

    Specified by:
      REQ-CLAMP-01  return ``value`` when ``lo <= value <= hi``
      REQ-CLAMP-02  return ``lo`` when ``value < lo``
      REQ-CLAMP-03  return ``hi`` when ``value > hi``
      REQ-CLAMP-04  raise ``ValueError`` when ``lo > hi``
    """
    if lo > hi:
        raise ValueError("lo must be <= hi")
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


CLAMP_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("REQ-CLAMP-01", "return value unchanged when lo <= value <= hi"),
    ("REQ-CLAMP-02", "return lo when value is below the lower bound"),
    ("REQ-CLAMP-03", "return hi when value is above the upper bound"),
    ("REQ-CLAMP-04", "raise ValueError when lo is greater than hi"),
)
