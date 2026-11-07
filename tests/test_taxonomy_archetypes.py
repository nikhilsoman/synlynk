# tests/test_taxonomy_archetypes.py
import pytest
from synlynk import taxonomy


def test_workspace_domains_defined():
    assert "mobile" in taxonomy.WORKSPACE_DOMAINS
    assert "ai_ml" in taxonomy.WORKSPACE_DOMAINS
    assert "fullstack_web" in taxonomy.WORKSPACE_DOMAINS
    assert "backend_distributed" in taxonomy.WORKSPACE_DOMAINS


def test_recommend_fleet_archetypes_mobile():
    roles = taxonomy.recommend_fleet_archetypes("mobile")
    role_names = [r["role"] for r in roles]
    assert "architect" in role_names
    assert "dev" in role_names
    assert "qa" in role_names
    assert any("mobile" in r.get("specialization", "").lower() or "ios" in r.get("specialization", "").lower() for r in roles)


def test_recommend_fleet_archetypes_aiml():
    roles = taxonomy.recommend_fleet_archetypes("ai_ml")
    role_names = [r["role"] for r in roles]
    assert "architect" in role_names
    assert any("model" in r.get("specialization", "").lower() or "eval" in r.get("specialization", "").lower() for r in roles)


def test_recommend_fleet_archetypes_fallback_unknown():
    roles = taxonomy.recommend_fleet_archetypes("unknown_domain")
    role_names = [r["role"] for r in roles]
    assert "pm" in role_names
    assert "architect" in role_names
    assert "dev" in role_names
    assert "qa" in role_names
