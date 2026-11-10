import json
import os
import uuid
import datetime
from enum import Enum
import sqlite3
from typing import Any


class AutonomyMode(str, Enum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class AutonomyLevel(str, Enum):
    L1_ADVISORY = "L1_ADVISORY"
    L2_GATED = "L2_GATED"
    L3_AUTONOMOUS = "L3_AUTONOMOUS"


LEVEL_ORDER = {
    AutonomyLevel.L1_ADVISORY: 1,
    AutonomyLevel.L2_GATED: 2,
    AutonomyLevel.L3_AUTONOMOUS: 3,
}


def _get_config_path() -> str:
    workspace_path = os.path.join(os.getcwd(), ".synlynk", "workspace.json")
    if os.path.exists(workspace_path):
        return workspace_path
    return os.path.join(os.getcwd(), ".synlynk", "config.json")


def get_autonomy_mode() -> AutonomyMode:
    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            mode_val = data.get("autonomy_mode", "supervised").lower()
            return AutonomyMode(mode_val)
        except (json.JSONDecodeError, ValueError, OSError):
            return AutonomyMode.SUPERVISED
    return AutonomyMode.SUPERVISED


def set_autonomy_mode(mode) -> AutonomyMode:
    if isinstance(mode, AutonomyMode):
        target = mode
    else:
        try:
            target = AutonomyMode(str(mode).lower())
        except ValueError:
            raise ValueError(
                f"Invalid autonomy mode '{mode}'. Choose from: manual, supervised, autonomous"
            )

    path = _get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    data["autonomy_mode"] = target.value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return target


def can_auto_advance(stage: str, mode: AutonomyMode) -> bool:
    stage_normalized = stage.lower().strip()
    if mode == AutonomyMode.MANUAL:
        return False
    if mode == AutonomyMode.SUPERVISED:
        # Pauses before execution and public release
        if stage_normalized in ("execute", "release"):
            return False
        return True
    if mode == AutonomyMode.AUTONOMOUS:
        return True
    return False


# --- Horizon 3 Autonomy Evolutionary Ladder ---


def _resolve_db(conn: sqlite3.Connection | None = None) -> tuple[sqlite3.Connection, bool]:
    if conn is not None:
        return conn, False
    from synlynk.db import _get_db
    return _get_db(), True


def get_agent_autonomy_level(agent_id: str, conn: sqlite3.Connection | None = None) -> AutonomyLevel:
    """Return the current autonomy level for an agent, defaulting to L1_ADVISORY."""
    db, should_close = _resolve_db(conn)
    try:
        row = db.execute(
            "SELECT autonomy_level FROM workspace_agents WHERE agent_id = ? OR role = ?",
            (agent_id, agent_id),
        ).fetchone()
        if row and row[0]:
            try:
                return AutonomyLevel(row[0])
            except ValueError:
                return AutonomyLevel.L1_ADVISORY
        return AutonomyLevel.L1_ADVISORY
    finally:
        if should_close:
            db.close()


def promote_agent_autonomy(
    agent_id: str,
    target_level: str | AutonomyLevel,
    authorized_by: str,
    conn: sqlite3.Connection | None = None,
) -> AutonomyLevel:
    """Promote an agent to a higher autonomy level.

    Safety Invariants:
    1. Promotions require explicit human authorization (never agent self-promotion).
    2. In v0.31.0, L3_AUTONOMOUS is restricted to TPM orchestrator only.
    3. Mandatory domain autonomy caps (e.g. Rxcc <= L2_GATED) are enforced.
    """
    if authorized_by != "human":
        raise PermissionError(
            f"Autonomy promotion for agent '{agent_id}' requires explicit human authorization; "
            f"got authorized_by={authorized_by!r}."
        )

    target = AutonomyLevel(target_level)
    db, should_close = _resolve_db(conn)
    try:
        row = db.execute(
            "SELECT agent_id, role, autonomy_level, domain_autonomy_caps FROM workspace_agents WHERE agent_id = ? OR role = ?",
            (agent_id, agent_id),
        ).fetchone()
        if not row:
            raise KeyError(f"Agent '{agent_id}' not found in workspace_agents")

        actual_id, role, current_level_str, domain_caps = row
        current_level = AutonomyLevel(current_level_str) if current_level_str else AutonomyLevel.L1_ADVISORY

        # Check domain autonomy caps
        if domain_caps:
            try:
                cap_level = AutonomyLevel(domain_caps)
                if LEVEL_ORDER[target] > LEVEL_ORDER[cap_level]:
                    raise ValueError(
                        f"Domain autonomy cap forbids promotion past {cap_level.value} for agent '{agent_id}'"
                    )
            except ValueError as e:
                if "Domain autonomy cap" in str(e):
                    raise

        # Check v0.31.0 L3 launch restriction (TPM only)
        if target == AutonomyLevel.L3_AUTONOMOUS:
            if actual_id != "tpm" and role != "tpm":
                raise ValueError(
                    f"L3_AUTONOMOUS is currently restricted to TPM orchestrator only at launch; "
                    f"agent '{agent_id}' (role={role}) cannot be promoted to L3."
                )

        db.execute(
            "UPDATE workspace_agents SET autonomy_level = ? WHERE agent_id = ?",
            (target.value, actual_id),
        )
        db.commit()
        return target
    finally:
        if should_close:
            db.close()


def demote_agent_autonomy(
    agent_id: str,
    reason: str,
    tripped_by: str = "sentinel",
    conn: sqlite3.Connection | None = None,
) -> AutonomyLevel:
    """Automatically demote an agent to a lower autonomy tier upon a Sentinel tripwire."""
    db, should_close = _resolve_db(conn)
    try:
        row = db.execute(
            "SELECT agent_id, autonomy_level FROM workspace_agents WHERE agent_id = ? OR role = ?",
            (agent_id, agent_id),
        ).fetchone()
        if not row:
            raise KeyError(f"Agent '{agent_id}' not found in workspace_agents")

        actual_id, current_level_str = row
        current_level = AutonomyLevel(current_level_str) if current_level_str else AutonomyLevel.L1_ADVISORY

        # Demote down one level
        if current_level == AutonomyLevel.L3_AUTONOMOUS:
            new_level = AutonomyLevel.L2_GATED
        else:
            new_level = AutonomyLevel.L1_ADVISORY

        db.execute(
            "UPDATE workspace_agents SET autonomy_level = ? WHERE agent_id = ?",
            (new_level.value, actual_id),
        )

        # Record tripwire event in rsi_evaluations ledger
        eval_id = f"eval-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.execute(
            """
            INSERT INTO rsi_evaluations (
                eval_id, agent_id, cycle_timestamp, calculated_score, circuit_breaker_tripped, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (eval_id, actual_id, now, 0.0, 1, f"Demoted by {tripped_by}: {reason}"),
        )
        db.commit()
        return new_level
    finally:
        if should_close:
            db.close()
