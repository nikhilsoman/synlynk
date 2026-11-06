"""State machine and persistence for Greenfield Guided Onboarding (v0.28.5)."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

STAGE_S0_FLEET = "S0_FLEET"
STAGE_S1_PM = "S1_PM"
STAGE_S2_ARCH = "S2_ARCH"
STAGE_S3_DECIDE = "S3_DECIDE"
STAGE_S4_TPM = "S4_TPM"
STAGE_S5_DEV_QA = "S5_DEV_QA"
STAGE_COMPLETED = "COMPLETED"

STAGES = [
    STAGE_S0_FLEET,
    STAGE_S1_PM,
    STAGE_S2_ARCH,
    STAGE_S3_DECIDE,
    STAGE_S4_TPM,
    STAGE_S5_DEV_QA,
    STAGE_COMPLETED,
]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("daily_sync_channels"):
        try:
            d["daily_sync_channels"] = json.loads(d["daily_sync_channels"])
        except Exception:
            d["daily_sync_channels"] = ["cli", "vizor"]
    else:
        d["daily_sync_channels"] = ["cli", "vizor"]
    return d


def create_or_resume_session(
    conn: sqlite3.Connection,
    project_name: str,
    raw_intent: str,
    *,
    fast_forward: bool = False,
    github_repo: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new greenfield session or resume existing pending session."""
    conn.row_factory = sqlite3.Row
    existing = conn.execute(
        "SELECT * FROM greenfield_sessions WHERE project_name = ? AND completed_at IS NULL ORDER BY created_at DESC LIMIT 1",
        (project_name,),
    ).fetchone()
    if existing:
        return _row_to_dict(existing)

    session_id = f"gen-{uuid.uuid4().hex[:8]}"
    now = time.time()
    channels_json = json.dumps(["cli", "vizor"])

    conn.execute(
        """INSERT INTO greenfield_sessions (
            session_id, project_name, raw_intent, github_repo, current_stage,
            fast_forwarded, daily_sync_channels, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            project_name,
            raw_intent,
            github_repo,
            STAGE_S0_FLEET,
            1 if fast_forward else 0,
            channels_json,
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM greenfield_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def advance_stage(
    conn: sqlite3.Connection,
    session_id: str,
    target_stage: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Advance session to a target stage and update optional properties."""
    if target_stage not in STAGES:
        raise ValueError(f"Invalid greenfield stage: {target_stage}")

    now = time.time()
    completed_at = now if target_stage == STAGE_COMPLETED else None

    updates = ["current_stage = ?", "updated_at = ?"]
    params: List[Any] = [target_stage, now]

    if completed_at is not None:
        updates.append("completed_at = COALESCE(completed_at, ?)")
        params.append(completed_at)

    for field in ("github_repo", "dilemma_topic", "dilemma_decision_id", "fast_forwarded"):
        if field in kwargs:
            updates.append(f"{field} = ?")
            params.append(kwargs[field])

    params.append(session_id)
    query = f"UPDATE greenfield_sessions SET {', '.join(updates)} WHERE session_id = ?"
    conn.execute(query, tuple(params))
    conn.commit()

    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM greenfield_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise KeyError(f"Greenfield session not found: {session_id}")
    return _row_to_dict(row)


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve greenfield session dictionary by ID."""
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM greenfield_sessions WHERE session_id = ?", (session_id,)).fetchone()
    return _row_to_dict(row) if row else None
