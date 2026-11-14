import pytest
from synlynk.constitution import (
    CONSTITUTION_LAWS,
    ConstitutionLaw,
    DeliveryTier,
    get_law,
    list_laws,
    validate_citation_tag,
)


def test_constitution_canonical_laws_exist():
    """Verify all 4 Asimov laws and Intent-Based Engineering invariant exist."""
    expected_ids = {"law-0", "law-1", "law-2", "law-3", "intent-invariant"}
    assert set(CONSTITUTION_LAWS.keys()) == expected_ids

    # Law 0: Secrets & System Integrity
    law0 = CONSTITUTION_LAWS["law-0"]
    assert law0.number == 0
    assert "Secrets" in law0.name
    assert law0.tier == DeliveryTier.INJECTED

    # Law 1: Human Sovereignty
    law1 = CONSTITUTION_LAWS["law-1"]
    assert law1.number == 1
    assert "Human Sovereignty" in law1.name
    assert law1.tier == DeliveryTier.INJECTED

    # Law 2: Evidence Over Assertions
    law2 = CONSTITUTION_LAWS["law-2"]
    assert law2.number == 2
    assert "Evidence Over Assertions" in law2.name
    assert law2.tier == DeliveryTier.INJECTED

    # Law 3: Metered Self-Preservation
    law3 = CONSTITUTION_LAWS["law-3"]
    assert law3.number == 3
    assert "Self-Preservation" in law3.name
    assert law3.tier == DeliveryTier.CITED

    # Intent Invariant
    inv = CONSTITUTION_LAWS["intent-invariant"]
    assert inv.number is None
    assert "Intent-Based" in inv.name
    assert inv.tier == DeliveryTier.CITED


def test_get_law():
    """Test get_law lookup by id or alias."""
    assert get_law("law-0") is not None
    assert get_law("LAW-0") is not None
    assert get_law("0") is not None
    assert get_law("law-1") is not None
    assert get_law("intent-invariant") is not None
    assert get_law("nonexistent") is None


def test_list_laws():
    """Test list_laws returns all registered laws."""
    laws = list_laws()
    assert len(laws) == 5
    assert all(isinstance(l, ConstitutionLaw) for l in laws)


def test_validate_citation_tag():
    """Test validation of HTML/Markdown citation tags."""
    assert validate_citation_tag("<!-- constitution: law-0 -->") == "law-0"
    assert validate_citation_tag("<!-- constitution: law-1 -->") == "law-1"
    assert validate_citation_tag("<!-- constitution: intent-invariant -->") == "intent-invariant"
    assert validate_citation_tag("<!-- constitution: unknown -->") is None
    assert validate_citation_tag("regular text without tag") is None
