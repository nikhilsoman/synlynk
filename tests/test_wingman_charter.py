"""Tests for the canonical Wingman role charter and TPM orchestrator charter."""
import json
import os
import pytest
from pathlib import Path

from synlynk.charter_schema import get_sfia_skill, VALID_ARCHETYPES, KNOWN_ROLES


def test_wingman_charter_file_exists_and_validates():
    repo_root = Path(__file__).parent.parent
    wingman_path = repo_root / ".synlynk" / "charters" / "wingman.json"
    assert wingman_path.is_file(), f"wingman.json not found at {wingman_path}"

    with open(wingman_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["role"] == "wingman"
    assert data["role"] in KNOWN_ROLES
    assert data["primary_archetype"] == "chief-of-staff"
    assert data["primary_archetype"] in VALID_ARCHETYPES
    assert data["edition_tier"] == "personal_default"

    # Verify composite skills
    sfia = data.get("sfia_mapping", {})
    assert "composite_skills" in sfia
    skills = {item["skill"] for item in sfia["composite_skills"]}
    assert {"BAPM", "PROG", "TEST", "ITOP"}.issubset(skills)

    # Verify boundaries and graduation gate
    assert len(data.get("boundaries", [])) >= 3
    assert "graduation_gate" in data
    assert "triggers" in data["graduation_gate"]


def test_tpm_charter_file_has_orchestrator_and_sfia():
    repo_root = Path(__file__).parent.parent
    tpm_path = repo_root / ".synlynk" / "charters" / "tpm.json"
    assert tpm_path.is_file(), f"tpm.json not found at {tpm_path}"

    with open(tpm_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["role"] == "tpm"
    assert data["primary_archetype"] == "orchestrator"
    assert data["primary_archetype"] in VALID_ARCHETYPES

    sfia = data.get("sfia_mapping", {})
    assert sfia.get("sfia_code") == "PGMG"
    assert sfia.get("sfia_level") == 5

    # Verify boundaries
    boundaries = data.get("boundaries", [])
    assert len(boundaries) >= 4
    assert any("Never implement application logic" in b for b in boundaries)

    # Verify coordination pattern
    coord = data.get("coordination_pattern", {})
    assert "intake_and_mining" in coord
    assert "ambiguity_gate" in coord
    assert "package_proposal" in coord
    assert "role_delegation" in coord
    assert "review_routing" in coord
    assert "release_trigger" in coord
    assert "hygiene_gate" in coord
