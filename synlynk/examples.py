from __future__ import annotations

"""Small examples for common Python tasks."""

import math
from dataclasses import dataclass, replace

_REQUIREMENT_STATUSES = ("proposed", "approved", "implemented", "verified")


class RequirementError(ValueError):
    """A requirement record or a requirement-governed input is invalid."""


@dataclass(frozen=True)
class Requirement:
    """One managed requirement: statement, acceptance criteria, constraints, status."""

    req_id: str
    statement: str
    acceptance_criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    status: str = "proposed"


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise RequirementError(f"{field} must be text")
    text = value.strip()
    if not text:
        raise RequirementError(f"{field} must not be blank")
    return text


def _required_texts(values: object, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise RequirementError(f"{field} must be a list of text items")
    texts = tuple(_required_text(item, field) for item in values)
    if not texts and not allow_empty:
        raise RequirementError(f"{field} must not be empty")
    return texts


def define_requirement(
    req_id: str,
    statement: str,
    acceptance_criteria: tuple[str, ...] | list[str],
    constraints: tuple[str, ...] | list[str] = (),
) -> Requirement:
    """Record a requirement in the proposed state.

    Blank ids, statements, criteria, or constraints are rejected. Callers
    advance status separately so definition stays distinct from approval.
    """
    return Requirement(
        req_id=_required_text(req_id, "req_id"),
        statement=_required_text(statement, "statement"),
        acceptance_criteria=_required_texts(acceptance_criteria, "acceptance_criteria", allow_empty=False),
        constraints=_required_texts(constraints, "constraints", allow_empty=True),
        status="proposed",
    )


def advance_requirement(requirement: Requirement) -> Requirement:
    """Move a requirement one lifecycle step: proposed, approved, implemented, verified."""
    if not isinstance(requirement, Requirement):
        raise RequirementError("requirement must be a Requirement")
    try:
        index = _REQUIREMENT_STATUSES.index(requirement.status)
    except ValueError as exc:
        raise RequirementError(f"unknown status {requirement.status!r}") from exc
    if index == len(_REQUIREMENT_STATUSES) - 1:
        raise RequirementError("verified requirements cannot advance")
    return replace(requirement, status=_REQUIREMENT_STATUSES[index + 1])


def index_requirements(requirements: list[Requirement] | tuple[Requirement, ...]) -> dict[str, Requirement]:
    """Index requirements by id. Duplicate ids are a management conflict."""
    indexed: dict[str, Requirement] = {}
    for requirement in requirements:
        if not isinstance(requirement, Requirement):
            raise RequirementError("requirements must be Requirement values")
        if requirement.req_id in indexed:
            raise RequirementError(f"duplicate requirement id {requirement.req_id}")
        indexed[requirement.req_id] = requirement
    return indexed


def clamp_to_unit_interval(value: float) -> float:
    """Map a number onto [0.0, 1.0], as specified by REQ-CLAMP-1."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequirementError("value must be an int or a float")
    if not math.isfinite(value):
        raise RequirementError("value must be finite")
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


# REQ-CLAMP-1 governs clamp_to_unit_interval. It starts proposed; management
# advances it through approved, implemented, and verified.
CLAMP_REQUIREMENTS = (
    define_requirement(
        "REQ-CLAMP-1",
        "Map a number onto the closed interval [0.0, 1.0].",
        (
            "Values inside the interval are returned unchanged as floats.",
            "Values below 0.0 become 0.0.",
            "Values above 1.0 become 1.0.",
        ),
        constraints=("Input must be an int or a float.", "NaN and booleans are rejected."),
    ),
)


def greet(name: str) -> str:
    """Return a friendly greeting for a person's name."""
    return f"Hello, {name}!"


def active_items(items: list[dict]) -> list[dict]:
    """Return items whose ``active`` flag is truthy."""
    return [item for item in items if item.get("active")]
