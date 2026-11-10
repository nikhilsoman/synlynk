"""Tests for the 3-Tier Autonomy Evolutionary Ladder and Sentinel Circuit Breakers."""
import sqlite3
import pytest

from synlynk.autonomy import (
    AutonomyLevel,
    get_agent_autonomy_level,
    promote_agent_autonomy,
    demote_agent_autonomy,
)
from synlynk.archetypes import ensure_archetype_schema
from synlynk.db import _migrate_db


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    _migrate_db(conn)
    ensure_archetype_schema(conn)
    # Insert test agents
    conn.execute(
        """
        INSERT INTO workspace_agents (
            agent_id, workspace_id, role, archetype_id, autonomy_level, domain_autonomy_caps
        ) VALUES
        ('tpm', 'default', 'tpm', 'orchestrator', 'L1_ADVISORY', 'L3_AUTONOMOUS'),
        ('dev', 'default', 'dev', 'creator', 'L1_ADVISORY', NULL),
        ('rxcc-coordinator', 'default', 'trial-coordinator', 'orchestrator', 'L1_ADVISORY', 'L2_GATED')
        """
    )
    conn.commit()
    yield conn
    conn.close()


def test_default_autonomy_level_is_l1_advisory(test_db):
    assert get_agent_autonomy_level("tpm", conn=test_db) == AutonomyLevel.L1_ADVISORY
    assert get_agent_autonomy_level("dev", conn=test_db) == AutonomyLevel.L1_ADVISORY


def test_agent_self_promotion_fails_closed(test_db):
    # Safety Invariant: promotions require explicit human confirmation
    with pytest.raises(PermissionError, match="requires explicit human authorization"):
        promote_agent_autonomy("tpm", AutonomyLevel.L2_GATED, authorized_by="agent", conn=test_db)


def test_human_authorized_promotion_succeeds(test_db):
    promote_agent_autonomy("tpm", AutonomyLevel.L2_GATED, authorized_by="human", conn=test_db)
    assert get_agent_autonomy_level("tpm", conn=test_db) == AutonomyLevel.L2_GATED


def test_l3_restricted_to_tpm_at_launch(test_db):
    # Binding Amendment 3: in v0.31.0, only TPM is eligible for L3
    promote_agent_autonomy("dev", AutonomyLevel.L2_GATED, authorized_by="human", conn=test_db)
    with pytest.raises(ValueError, match="L3_AUTONOMOUS is currently restricted to TPM orchestrator"):
        promote_agent_autonomy("dev", AutonomyLevel.L3_AUTONOMOUS, authorized_by="human", conn=test_db)


def test_domain_autonomy_cap_prevents_high_risk_l3(test_db):
    # Binding Amendment 3: high-risk domain ceiling
    promote_agent_autonomy("rxcc-coordinator", AutonomyLevel.L2_GATED, authorized_by="human", conn=test_db)
    with pytest.raises(ValueError, match="Domain autonomy cap forbids promotion past L2_GATED"):
        promote_agent_autonomy("rxcc-coordinator", AutonomyLevel.L3_AUTONOMOUS, authorized_by="human", conn=test_db)


def test_sentinel_owned_automatic_demotion(test_db):
    # Promote TPM to L3
    promote_agent_autonomy("tpm", AutonomyLevel.L2_GATED, authorized_by="human", conn=test_db)
    promote_agent_autonomy("tpm", AutonomyLevel.L3_AUTONOMOUS, authorized_by="human", conn=test_db)
    assert get_agent_autonomy_level("tpm", conn=test_db) == AutonomyLevel.L3_AUTONOMOUS

    # Sentinel trips circuit breaker
    demote_agent_autonomy("tpm", reason="TOKEN_CIRCUIT_BREAKER_TRIPPED", tripped_by="sentinel", conn=test_db)
    assert get_agent_autonomy_level("tpm", conn=test_db) == AutonomyLevel.L2_GATED

    # Verify RSI evaluations ledger records the tripwire event
    rows = test_db.execute("SELECT circuit_breaker_tripped, notes FROM rsi_evaluations WHERE agent_id='tpm'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1
    assert "TOKEN_CIRCUIT_BREAKER_TRIPPED" in rows[0][1]
