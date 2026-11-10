"""Capability-neutral agent archetype definitions and persistence helpers."""

from __future__ import annotations

import sqlite3
from typing import Any


ARCHETYPE_DEFINITIONS: dict[str, dict[str, str]] = {
    "orchestrator": {
        "name": "Orchestrator",
        "lifecycle_contract": "intake_cluster_plan_dispatch_track",
        "description": "Coordinates workflow waves and dependencies",
    },
    "strategist": {
        "name": "Strategist",
        "lifecycle_contract": "vision_align_prioritize_gate",
        "description": "Maintains roadmap, intent, and scope gates",
    },
    "director": {
        "name": "Director",
        "lifecycle_contract": "frame_specify_contract_gate",
        "description": "Defines specifications and execution contracts",
    },
    "creator": {
        "name": "Creator",
        "lifecycle_contract": "brief_create_verify",
        "description": "Hands-on asset creation and implementation",
    },
    "inspector": {
        "name": "Inspector",
        "lifecycle_contract": "inspect_evaluate_gate",
        "description": "Quality assurance, compliance, and non-author review",
    },
    "custodian": {
        "name": "Custodian",
        "lifecycle_contract": "prune_sync_maintain_sustain",
        "description": "Substrate health, workspace hygiene, and operational continuity",
    },
}


def ensure_archetype_schema(conn: sqlite3.Connection) -> None:
    """Create archetype-owned tables and seed their immutable identifiers."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_archetypes (
            archetype_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lifecycle_contract TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_workflow_edges (
            edge_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            source_agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
            target_agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
            edge_type TEXT NOT NULL
                CHECK(edge_type IN ('delegation', 'review_gate', 'escalation')),
            properties_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rsi_evaluations (
            eval_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL REFERENCES workspace_agents(agent_id),
            cycle_timestamp TEXT NOT NULL,
            proposals_count INTEGER DEFAULT 0,
            proposals_accepted INTEGER DEFAULT 0,
            rework_count INTEGER DEFAULT 0,
            verification_passes INTEGER DEFAULT 0,
            estimated_cost REAL DEFAULT 0.0,
            actual_cost REAL DEFAULT 0.0,
            calculated_score REAL NOT NULL,
            circuit_breaker_tripped INTEGER DEFAULT 0,
            notes TEXT
        );
        """
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO agent_archetypes (
            archetype_id, name, lifecycle_contract, description
        ) VALUES (?, ?, ?, ?)
        """,
        (
            (
                archetype_id,
                definition["name"],
                definition["lifecycle_contract"],
                definition["description"],
            )
            for archetype_id, definition in ARCHETYPE_DEFINITIONS.items()
        ),
    )
    conn.commit()


def _row_to_archetype(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "archetype_id": row[0],
        "name": row[1],
        "lifecycle_contract": row[2],
        "description": row[3],
    }


def list_archetypes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all archetypes ordered by stable identifier."""
    rows = conn.execute(
        """
        SELECT archetype_id, name, lifecycle_contract, description
        FROM agent_archetypes
        ORDER BY archetype_id
        """
    ).fetchall()
    return [_row_to_archetype(row) for row in rows]


def get_archetype(
    conn: sqlite3.Connection, archetype_id: str
) -> dict[str, Any] | None:
    """Return one archetype, or ``None`` when its identifier is unknown."""
    row = conn.execute(
        """
        SELECT archetype_id, name, lifecycle_contract, description
        FROM agent_archetypes
        WHERE archetype_id = ?
        """,
        (archetype_id,),
    ).fetchone()
    return _row_to_archetype(row) if row is not None else None
