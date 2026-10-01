"""Canonical headless state machine for Synlynk Onboarding."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

STAGE_S1_ORIENTATION = "S1_Orientation"
STAGE_S2_DEPENDENCIES = "S2_Dependencies"
STAGE_S3_HARNESS_BINDING = "S3_HarnessBinding"
STAGE_S4_TOPOLOGY = "S4_TopologyConfirmation"
STAGE_S5_GOVERNS_INTRO = "S5_GovernsIntro"
STAGE_S6_DISPATCH_DECIDE = "S6_DispatchDecide"
STAGE_S7_AGENT_TEAM = "S7_AgentTeam"
STAGE_S8_FLEET_TEMPLATES = "S8_FleetTemplates"
STAGE_S9_FIRST_WIN_INTAKE = "S9_FirstWinIntake"
STAGE_S10_BUILD_EXPERIENCE = "S10_BuildExperience"

STAGES = [
    STAGE_S1_ORIENTATION,
    STAGE_S2_DEPENDENCIES,
    STAGE_S3_HARNESS_BINDING,
    STAGE_S4_TOPOLOGY,
    STAGE_S5_GOVERNS_INTRO,
    STAGE_S6_DISPATCH_DECIDE,
    STAGE_S7_AGENT_TEAM,
    STAGE_S8_FLEET_TEMPLATES,
    STAGE_S9_FIRST_WIN_INTAKE,
    STAGE_S10_BUILD_EXPERIENCE,
]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for json_col in ("topology_candidate", "topology_confirmed", "harness_probes", "dependency_checks", "first_win_meta"):
        if d.get(json_col):
            try:
                d[json_col] = json.loads(d[json_col])
            except Exception:
                d[json_col] = {}
        else:
            d[json_col] = {}
    return d


def get_or_create_session(conn: sqlite3.Connection, product_id: str) -> Dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM onboarding_sessions WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    if row:
        return _row_to_dict(row)

    session_id = f"onb-{uuid.uuid4().hex[:8]}"
    now = time.time()
    conn.execute(
        """INSERT INTO onboarding_sessions (
            session_id, product_id, current_stage, topology_status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, product_id, STAGE_S1_ORIENTATION, "pending", now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def advance_stage(
    conn: sqlite3.Connection,
    session_id: str,
    target_stage: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if target_stage not in STAGES:
        raise ValueError(f"Invalid onboarding stage: {target_stage}")

    now = time.time()
    completed_at = now if target_stage == STAGE_S10_BUILD_EXPERIENCE else None

    conn.execute(
        """UPDATE onboarding_sessions
           SET current_stage = ?, updated_at = ?, completed_at = COALESCE(completed_at, ?)
           WHERE session_id = ?""",
        (target_stage, now, completed_at, session_id),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def confirm_topology(
    conn: sqlite3.Connection,
    session_id: str,
    confirmed_topology: Dict[str, Any],
) -> Dict[str, Any]:
    now = time.time()
    conn.execute(
        """UPDATE onboarding_sessions
           SET topology_status = 'confirmed',
               topology_confirmed = ?,
               updated_at = ?
           WHERE session_id = ?""",
        (json.dumps(confirmed_topology), now, session_id),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def record_probe(
    conn: sqlite3.Connection,
    session_id: str,
    probe_type: str,  # 'harness' or 'dependency'
    item_key: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise ValueError(f"Session not found: {session_id}")

    session = _row_to_dict(row)
    now = time.time()

    if probe_type == "harness":
        data = session.get("harness_probes", {})
        data[item_key] = result
        col = "harness_probes"
    elif probe_type == "dependency":
        data = session.get("dependency_checks", {})
        data[item_key] = result
        col = "dependency_checks"
    else:
        raise ValueError(f"Invalid probe_type: {probe_type}")

    conn.execute(
        f"UPDATE onboarding_sessions SET {col} = ?, updated_at = ? WHERE session_id = ?",
        (json.dumps(data), now, session_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM onboarding_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)
