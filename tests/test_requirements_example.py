"""Requirements Definition and Management example.

Each behavior of ``clamp`` is defined once in ``REQUIREMENTS`` (the
definition) and each test below cites the requirement ID it covers
(the management/traceability part). A final test guards the registry
itself so requirements stay well-formed as they evolve.
"""

from synlynk.examples import REQUIREMENTS, clamp


def test_req_1_value_within_bounds_returned_unchanged():
    """REQ-1: value inside [low, high] is returned unchanged."""
    assert clamp(5, 1, 10) == 5


def test_req_2_value_below_low_returns_low():
    """REQ-2: value below low returns low."""
    assert clamp(-3, 0, 10) == 0


def test_req_3_value_above_high_returns_high():
    """REQ-3: value above high returns high."""
    assert clamp(99, 0, 10) == 10


def test_req_4_inverted_bounds_raise_value_error():
    """REQ-4: low > high raises ValueError."""
    import pytest

    with pytest.raises(ValueError):
        clamp(5, 10, 1)


def test_requirements_registry_is_well_formed():
    """Management: every requirement has a unique ID and a description."""
    assert len(REQUIREMENTS) >= 4
    for req_id, description in REQUIREMENTS.items():
        assert req_id.startswith("REQ-"), req_id
        assert isinstance(description, str) and description.strip(), req_id
