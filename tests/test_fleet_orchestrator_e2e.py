"""End-to-End integration test suite for Autonomous Fleet Orchestrator (Horizon 3 Foundation).

Validates:
1. 6 universal archetypes with capability-neutral contracts.
2. In-repo domain packs (software, hitchcock, rxcc) with suggested tool baselines.
3. 3-tier autonomy ladder (L1 Advisory -> L2 Gated -> L3 Autonomous) with human-only promotion.
4. Mandatory domain autonomy caps (rxcc <= L2).
5. Sentinel-owned automatic demotion on circuit breaker tripwire.
6. Non-regression: 10 software agent roles remain 100% valid under the new schema.
"""
import sqlite3
import pytest

from synlynk.archetypes import (
    ensure_archetype_schema,
    list_archetypes,
    get_archetype,
    ARCHETYPE_DEFINITIONS,
)
from synlynk.domain_packs import (
    load_domain_pack,
    list_domain_packs,
    get_suggested_tool_baseline,
)
from synlynk.autonomy import (
    AutonomyLevel,
    get_agent_autonomy_level,
    promote_agent_autonomy,
    demote_agent_autonomy,
)
from synlynk.charter_schema import (
    validate_charter,
    KNOWN_ROLES,
    VALID_ARCHETYPES,
    VALID_AUTONOMY_LEVELS,
)
from synlynk.db import _migrate_db


@pytest.fixture
def clean_db():
    conn = sqlite3.connect(":memory:")
    _migrate_db(conn)
    ensure_archetype_schema(conn)
    yield conn
    conn.close()


def test_e2e_six_universal_archetypes_seeded_cleanly(clean_db):
    archetypes = list_archetypes(clean_db)
    assert len(archetypes) == 6
    archetype_ids = {a["archetype_id"] for a in archetypes}
    assert archetype_ids == {
        "orchestrator", "strategist", "director", "creator", "inspector", "custodian"
    }

    # Verify capability-neutrality invariant (Binding Amendment 1)
    for a in archetypes:
        desc = (a["lifecycle_contract"] + " " + a["description"]).lower()
        for soft_term in ("tdd", "git", "worktree", "merge"):
            assert soft_term not in desc, f"Software term '{soft_term}' leaked into archetype {a['archetype_id']}"


def test_e2e_domain_packs_and_security_boundary():
    # Verify in-repo domain packs
    packs = list_domain_packs()
    assert {"software", "hitchcock", "rxcc"} <= set(packs)

    # Hitchcock Film Studio suggestions
    hitchcock_tools = get_suggested_tool_baseline("hitchcock", "creator", sfia_codes=["MUDI", "ANIM"])
    assert len(hitchcock_tools) >= 2
    for tool in hitchcock_tools:
        # Binding Amendment 2: Every suggested tool MUST require human confirmation
        assert tool["requires_confirmation"] is True
        assert tool["confirmed"] is False
        assert len(tool["scope_paths"]) > 0

    # Rxcc Biopharma domain cap
    rxcc = load_domain_pack("rxcc")
    assert rxcc["max_autonomy_level"] == "L2_GATED"


def test_e2e_autonomy_progression_and_circuit_breaker_drill(clean_db):
    # Setup TPM and Rxcc agents
    clean_db.execute(
        """
        INSERT INTO workspace_agents (
            agent_id, workspace_id, role, archetype_id, autonomy_level, domain_autonomy_caps
        ) VALUES
        ('tpm', 'ws-default', 'tpm', 'orchestrator', 'L1_ADVISORY', 'L3_AUTONOMOUS'),
        ('rxcc-lead', 'ws-default', 'trial-coordinator', 'orchestrator', 'L1_ADVISORY', 'L2_GATED')
        """
    )
    clean_db.commit()

    # 1. Starts at L1 Advisory
    assert get_agent_autonomy_level("tpm", conn=clean_db) == AutonomyLevel.L1_ADVISORY

    # 2. Self-promotion fails closed (Safety Invariant 1)
    with pytest.raises(PermissionError, match="requires explicit human authorization"):
        promote_agent_autonomy("tpm", AutonomyLevel.L2_GATED, authorized_by="agent_tpm", conn=clean_db)

    # 3. Human promotion to L2 Gated succeeds
    promote_agent_autonomy("tpm", AutonomyLevel.L2_GATED, authorized_by="human", conn=clean_db)
    assert get_agent_autonomy_level("tpm", conn=clean_db) == AutonomyLevel.L2_GATED

    # 4. Human promotion to L3 Autonomous succeeds for TPM
    promote_agent_autonomy("tpm", AutonomyLevel.L3_AUTONOMOUS, authorized_by="human", conn=clean_db)
    assert get_agent_autonomy_level("tpm", conn=clean_db) == AutonomyLevel.L3_AUTONOMOUS

    # 5. Rxcc cannot be promoted to L3 (Domain Cap Invariant)
    promote_agent_autonomy("rxcc-lead", AutonomyLevel.L2_GATED, authorized_by="human", conn=clean_db)
    with pytest.raises(ValueError, match="Domain autonomy cap forbids promotion past L2_GATED"):
        promote_agent_autonomy("rxcc-lead", AutonomyLevel.L3_AUTONOMOUS, authorized_by="human", conn=clean_db)

    # 6. Sentinel Demotion Drill: Token runaway trips circuit breaker
    demoted_level = demote_agent_autonomy(
        "tpm",
        reason="TOKEN_CIRCUIT_BREAKER_TRIPPED: runaway token burn (756,341 tokens)",
        tripped_by="sentinel",
        conn=clean_db,
    )
    assert demoted_level == AutonomyLevel.L2_GATED
    assert get_agent_autonomy_level("tpm", conn=clean_db) == AutonomyLevel.L2_GATED

    # Verify audit record in rsi_evaluations
    ledger = clean_db.execute(
        "SELECT circuit_breaker_tripped, notes FROM rsi_evaluations WHERE agent_id='tpm'"
    ).fetchall()
    assert len(ledger) == 1
    assert ledger[0][0] == 1
    assert "TOKEN_CIRCUIT_BREAKER_TRIPPED" in ledger[0][1]


def test_e2e_non_regression_across_all_ten_software_roles():
    # Verify all 10 software agent roles remain recognized and validate cleanly
    expected_software_roles = [
        "pm", "architect", "tpm", "dev", "designer", "qa", "marketing", "maintainer", "secops", "infra-devops"
    ]
    for role in expected_software_roles:
        assert role in KNOWN_ROLES

        charter = f"""---
schema_version: 1
role: {role}
description: Standard {role} role
durability: durable
tools: []
credentials: []
---

## Instructions
Operational instructions for {role}.

## Authority & Escalation
Escalation pathways for {role}.

## Workflow Ownership
Workflow ownership for {role}.
"""
        parsed = validate_charter(charter)
        assert parsed["role"] == role
