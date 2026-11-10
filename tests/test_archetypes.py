import sqlite3

from synlynk.archetypes import (
    ensure_archetype_schema,
    get_archetype,
    list_archetypes,
)
from synlynk.db import _migrate_db


EXPECTED_ARCHETYPE_IDS = {
    "orchestrator",
    "strategist",
    "director",
    "creator",
    "inspector",
    "custodian",
}


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_ensure_archetype_schema_creates_tables_with_required_columns():
    conn = sqlite3.connect(":memory:")

    ensure_archetype_schema(conn)

    assert _column_names(conn, "agent_archetypes") == {
        "archetype_id",
        "name",
        "lifecycle_contract",
        "description",
    }
    assert _column_names(conn, "agent_workflow_edges") == {
        "edge_id",
        "workspace_id",
        "source_agent_id",
        "target_agent_id",
        "edge_type",
        "properties_json",
        "created_at",
    }
    assert _column_names(conn, "rsi_evaluations") == {
        "eval_id",
        "agent_id",
        "cycle_timestamp",
        "proposals_count",
        "proposals_accepted",
        "rework_count",
        "verification_passes",
        "estimated_cost",
        "actual_cost",
        "calculated_score",
        "circuit_breaker_tripped",
        "notes",
    }


def test_archetype_schema_seeds_six_capability_neutral_definitions():
    conn = sqlite3.connect(":memory:")

    ensure_archetype_schema(conn)

    archetypes = list_archetypes(conn)
    assert {item["archetype_id"] for item in archetypes} == EXPECTED_ARCHETYPE_IDS
    assert len(archetypes) == 6
    assert get_archetype(conn, "creator") == {
        "archetype_id": "creator",
        "name": "Creator",
        "lifecycle_contract": "brief_create_verify",
        "description": "Hands-on asset creation and implementation",
    }
    assert get_archetype(conn, "missing") is None


def test_archetype_definitions_do_not_embed_software_workflow_mechanics():
    conn = sqlite3.connect(":memory:")
    ensure_archetype_schema(conn)

    serialized_contracts = " ".join(
        f'{item["lifecycle_contract"]} {item["description"]}'
        for item in list_archetypes(conn)
    ).lower()

    for software_term in ("tdd", "merge", "regression", "release", "architect"):
        assert software_term not in serialized_contracts


def test_db_migration_adds_archetype_columns_to_workspace_agents():
    conn = sqlite3.connect(":memory:")

    _migrate_db(conn)

    assert {
        "archetype_id",
        "secondary_hat",
        "sfia_disciplines",
        "autonomy_level",
        "domain_autonomy_caps",
    } <= _column_names(conn, "workspace_agents")
    assert conn.execute(
        "SELECT COUNT(*) FROM agent_archetypes"
    ).fetchone()[0] == 6


def test_ensure_archetype_schema_is_idempotent_and_preserves_customized_rows():
    conn = sqlite3.connect(":memory:")
    ensure_archetype_schema(conn)
    conn.execute(
        "UPDATE agent_archetypes SET description = ? WHERE archetype_id = ?",
        ("Workspace-specific description", "creator"),
    )

    ensure_archetype_schema(conn)

    assert get_archetype(conn, "creator")["description"] == "Workspace-specific description"
