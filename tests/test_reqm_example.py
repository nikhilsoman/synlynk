"""Requirements definition and management for clamp_to_unit_interval."""

import math

import pytest

from synlynk.examples import (
    CLAMP_REQUIREMENTS,
    Requirement,
    RequirementError,
    advance_requirement,
    clamp_to_unit_interval,
    define_requirement,
    index_requirements,
)


def test_define_requirement_captures_statement_criteria_and_starts_proposed():
    requirement = define_requirement(
        "REQ-CLAMP-1",
        "Map a number onto the closed interval [0.0, 1.0].",
        (
            "Values inside the interval are returned unchanged as floats.",
            "Values below 0.0 become 0.0.",
            "Values above 1.0 become 1.0.",
        ),
        constraints=("Input must be an int or a float.", "NaN and booleans are rejected."),
    )

    assert isinstance(requirement, Requirement)
    assert requirement.req_id == "REQ-CLAMP-1"
    assert requirement.statement == "Map a number onto the closed interval [0.0, 1.0]."
    assert requirement.acceptance_criteria == (
        "Values inside the interval are returned unchanged as floats.",
        "Values below 0.0 become 0.0.",
        "Values above 1.0 become 1.0.",
    )
    assert requirement.constraints == (
        "Input must be an int or a float.",
        "NaN and booleans are rejected.",
    )
    assert requirement.status == "proposed"


def test_define_requirement_defaults_constraints_to_empty():
    requirement = define_requirement("REQ-1", "State the need.", ("It is observable.",))

    assert requirement.constraints == ()


def test_define_requirement_strips_surrounding_whitespace():
    requirement = define_requirement(
        "  REQ-1  ",
        "  State the need.  ",
        ("  It is observable.  ",),
        constraints=("  Stay small.  ",),
    )

    assert requirement.req_id == "REQ-1"
    assert requirement.statement == "State the need."
    assert requirement.acceptance_criteria == ("It is observable.",)
    assert requirement.constraints == ("Stay small.",)


@pytest.mark.parametrize(
    ("req_id", "statement", "criteria", "constraints"),
    [
        ("", "State the need.", ("It is observable.",), ()),
        ("   ", "State the need.", ("It is observable.",), ()),
        ("REQ-1", "", ("It is observable.",), ()),
        ("REQ-1", "   ", ("It is observable.",), ()),
        ("REQ-1", "State the need.", (), ()),
        ("REQ-1", "State the need.", ("",), ()),
        ("REQ-1", "State the need.", ("   ",), ()),
        ("REQ-1", "State the need.", ("It is observable.",), ("",)),
        ("REQ-1", "State the need.", ("It is observable.",), ("   ",)),
    ],
)
def test_define_requirement_rejects_blank_fields(req_id, statement, criteria, constraints):
    with pytest.raises(RequirementError):
        define_requirement(req_id, statement, criteria, constraints=constraints)


def test_define_requirement_rejects_non_text_identifiers():
    with pytest.raises(RequirementError):
        define_requirement(1, "State the need.", ("It is observable.",))


def test_advance_requirement_moves_one_lifecycle_step_without_mutation():
    proposed = define_requirement("REQ-1", "State the need.", ("It is observable.",))

    approved = advance_requirement(proposed)
    implemented = advance_requirement(approved)
    verified = advance_requirement(implemented)

    assert proposed.status == "proposed"
    assert approved.status == "approved"
    assert implemented.status == "implemented"
    assert verified.status == "verified"
    assert approved.req_id == proposed.req_id
    assert approved.acceptance_criteria == proposed.acceptance_criteria


def test_advance_requirement_rejects_a_verified_requirement():
    verified = advance_requirement(
        advance_requirement(
            advance_requirement(
                define_requirement("REQ-1", "State the need.", ("It is observable.",))
            )
        )
    )

    with pytest.raises(RequirementError):
        advance_requirement(verified)


def test_index_requirements_keys_by_id_and_rejects_duplicates():
    first = define_requirement("REQ-1", "First need.", ("Observed once.",))
    second = define_requirement("REQ-2", "Second need.", ("Observed twice.",))

    assert index_requirements([first, second]) == {"REQ-1": first, "REQ-2": second}

    duplicate = define_requirement("REQ-1", "Conflicting need.", ("Observed differently.",))
    with pytest.raises(RequirementError):
        index_requirements([first, duplicate])


def test_clamp_requirements_are_defined_and_can_be_verified():
    indexed = index_requirements(CLAMP_REQUIREMENTS)
    requirement = indexed["REQ-CLAMP-1"]
    assert requirement.status == "proposed"
    assert len(requirement.acceptance_criteria) == 3

    verified = requirement
    while verified.status != "verified":
        verified = advance_requirement(verified)
    assert verified.status == "verified"


def test_clamp_to_unit_interval_keeps_interior_values():
    assert clamp_to_unit_interval(0.25) == 0.25
    assert clamp_to_unit_interval(0) == 0.0
    assert clamp_to_unit_interval(1) == 1.0


def test_clamp_to_unit_interval_applies_the_recorded_bounds():
    assert clamp_to_unit_interval(-0.1) == 0.0
    assert clamp_to_unit_interval(2) == 1.0


def test_clamp_to_unit_interval_rejects_non_finite_and_boolean_inputs():
    with pytest.raises(RequirementError):
        clamp_to_unit_interval(math.nan)
    with pytest.raises(RequirementError):
        clamp_to_unit_interval(True)
    with pytest.raises(RequirementError):
        clamp_to_unit_interval("0.5")
