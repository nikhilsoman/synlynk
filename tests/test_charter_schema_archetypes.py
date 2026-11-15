"""Tests for charter schema validation with Archetypes, Secondary Hats, and Autonomy Caps."""
import pytest
from synlynk.charter_schema import (
    validate_charter,
    CharterValidationError,
    VALID_ARCHETYPES,
    VALID_AUTONOMY_LEVELS,
)


def _valid_base_charter():
    return """---
schema_version: 1
role: dev
primary_archetype: creator
description: Software Developer
durability: dispatch-only
tools: []
credentials: []
---

## Instructions
Execute implementation tasks.

## Authority & Escalation
Escalate architectural blockers.

## Workflow Ownership
Owns source code modules.
"""


def test_charter_with_valid_archetype_and_secondary_hat_passes():
    content = """---
schema_version: 1
role: architect
primary_archetype: director
secondary_hat: strategist
autonomy_level: L1_ADVISORY
description: System Architect
durability: session-only
tools: []
credentials: []
---

## Instructions
Define structural contracts.

## Authority & Escalation
Escalate roadmap disputes.

## Workflow Ownership
Owns architecture specs.
"""
    parsed = validate_charter(content)
    assert parsed["primary_archetype"] == "director"
    assert parsed["secondary_hat"] == "strategist"
    assert parsed["autonomy_level"] == "L1_ADVISORY"


def test_charter_with_invalid_archetype_raises_error():
    content = _valid_base_charter().replace("primary_archetype: creator", "primary_archetype: wizard")
    with pytest.raises(CharterValidationError) as exc_info:
        validate_charter(content)
    assert "unknown primary_archetype 'wizard'" in str(exc_info.value)


def test_charter_with_invalid_secondary_hat_raises_error():
    content = _valid_base_charter().replace("primary_archetype: creator", "primary_archetype: creator\nsecondary_hat: boss")
    with pytest.raises(CharterValidationError) as exc_info:
        validate_charter(content)
    assert "unknown secondary_hat 'boss'" in str(exc_info.value)


def test_charter_with_invalid_autonomy_level_raises_error():
    content = _valid_base_charter().replace("primary_archetype: creator", "primary_archetype: creator\nautonomy_level: GOD_MODE")
    with pytest.raises(CharterValidationError) as exc_info:
        validate_charter(content)
    assert "invalid autonomy_level 'GOD_MODE'" in str(exc_info.value)


def test_charter_with_chief_of_staff_and_sfia_passes():
    content = """---
schema_version: 1
role: wingman
primary_archetype: chief-of-staff
description: Personal Chief of Staff
durability: session-only
tools: []
credentials: []
boundaries:
  - Never execute un-fenced Tier-3 changes unilaterally.
sfia_mapping: {"composite_skills": [{"skill": "BAPM", "level": 2}, {"skill": "PROG", "level": 3}]}
---

## Instructions
Personal co-pilot tasks.

## Authority & Escalation
Escalate Tier 3.

## Workflow Ownership
Single operator assistance.
"""
    parsed = validate_charter(content)
    assert parsed["primary_archetype"] == "chief-of-staff"
    assert parsed["role"] == "wingman"
    assert len(parsed["boundaries"]) == 1
    assert "composite_skills" in parsed["sfia_mapping"]


def test_charter_with_sfia_taxonomy_lookup():
    from synlynk.charter_schema import get_sfia_skill, get_sfia_taxonomy
    tax = get_sfia_taxonomy()
    assert "skills" in tax
    assert "PGMG" in tax["skills"]
    assert "PROG" in tax["skills"]

    pgmg = get_sfia_skill("PGMG")
    assert pgmg is not None
    assert pgmg["name"] == "Program Management"
    assert 5 in pgmg["levels"]
