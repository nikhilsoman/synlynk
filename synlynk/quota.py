"""synlynk quota: per-agent quota headroom, upsert, and cost estimation."""

import json
import sys
import time

from typing import Optional


def _pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)


# Plan-driven quota windows. Harnesses reset on different cadences — not a
# fixed shared shape. "5h" covers Claude Max/Team rolling plan windows.
QUOTA_TYPES = ("5h", "hourly", "daily", "weekly", "monthly")
QUOTA_UNITS = ("tokens", "requests")
# Capability scores within this gap are considered ties → break on cost (#140).
_CAPABILITY_COST_TIE_GAP = 0.15


def _quota_headroom(limit_tokens: int, used_tokens: int) -> int:
    """Return remaining capacity for a quota row (never negative)."""
    try:
        return max(0, int(limit_tokens) - int(used_tokens or 0))
    except (TypeError, ValueError):
        return 0


def _upsert_agent_quota(
    agent: str,
    quota_type: str,
    limit_tokens: int,
    used_tokens: int = 0,
    *,
    model: str = "unknown",
    unit: str = "tokens",
    reset_at: Optional[str] = None,
    conn=None,
) -> None:
    """Insert or update an agent_quotas row. Validates quota_type and unit."""
    if quota_type not in QUOTA_TYPES:
        raise ValueError(
            f"Invalid quota_type {quota_type!r}. Allowed: {', '.join(QUOTA_TYPES)}"
        )
    if unit not in QUOTA_UNITS:
        raise ValueError(
            f"Invalid unit {unit!r}. Allowed: {', '.join(QUOTA_UNITS)}"
        )
    own_conn = conn is None
    if own_conn:
        conn = _pkg("_get_db")()
    try:
        conn.execute(
            """
            INSERT INTO agent_quotas
                (agent, model, quota_type, unit, limit_tokens, used_tokens,
                 reset_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(agent, model, quota_type, unit) DO UPDATE SET
                limit_tokens = excluded.limit_tokens,
                used_tokens  = excluded.used_tokens,
                reset_at     = excluded.reset_at,
                updated_at   = CURRENT_TIMESTAMP
            """,
            (
                agent,
                model or "unknown",
                quota_type,
                unit,
                int(limit_tokens),
                int(used_tokens or 0),
                reset_at,
            ),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def _project_request_quota_from_config() -> Optional[dict]:
    """Unify project-level budget.limit_requests with agent_quotas request unit.

    Returns a synthetic quota dict, or None if config cannot be read.
    This is the bridge between .synlynk/config.json limit_requests and the
    per-agent request-unit rows in agent_quotas — not a substitute for
    per-agent plan quotas, but a workspace floor when no agent-level request
    row exists.
    """
    try:
        config = _pkg("load_config")()
        limit_reqs = int(config.get("budget", {}).get("limit_requests") or 0)
    except Exception:
        return None
    if limit_reqs <= 0:
        return None
    used = 0
    telemetry_file = ".synlynk/telemetry.json"
    if __import__("os").path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
            used = sum(1 for e in data if e.get("type") == "exec")
        except (json.JSONDecodeError, IOError, TypeError):
            # Degraded: cannot read usage this cycle — treat used as 0 so we
            # don't hard-block on a missing signal (conservative headroom).
            used = 0
    return {
        "agent": "*",
        "model": "project",
        "quota_type": "monthly",
        "unit": "requests",
        "limit_tokens": limit_reqs,
        "used_tokens": used,
        "headroom": _quota_headroom(limit_reqs, used),
        "source": "config.budget.limit_requests",
    }


def _read_agent_quota_rows(conn, agent: str) -> Optional[list]:
    """Read agent_quotas rows for an agent.

    Returns:
      - list of row dicts on success (may be empty — empty means no signal)
      - None if the table/query failed (degraded: quota unreadable this cycle)

    Degraded-mode contract (#141): callers must not hard-block when this
    returns None or an empty list. Route conservatively (prefer agents with
    known headroom) but keep the agent eligible.
    """
    try:
        rows = conn.execute(
            """
            SELECT agent, model, quota_type, unit, limit_tokens, used_tokens,
                   reset_at, updated_at
            FROM agent_quotas
            WHERE agent = ?
            """,
            (agent,),
        ).fetchall()
    except Exception:
        return None
    result = []
    for r in rows:
        limit_v = r[4]
        used_v = r[5]
        result.append({
            "agent": r[0],
            "model": r[1],
            "quota_type": r[2],
            "unit": r[3] or "tokens",
            "limit_tokens": limit_v,
            "used_tokens": used_v,
            "headroom": _quota_headroom(limit_v, used_v),
            "reset_at": r[6],
            "updated_at": r[7],
            "source": "agent_quotas",
        })
    return result


def _quota_status_for_agent(
    conn,
    agent: str,
    estimated_tokens: Optional[int] = None,
    estimated_requests: int = 1,
) -> dict:
    """Stage-2 quota gate for one agent.

    Returns dict with keys:
      status: "ok" | "exhausted" | "unknown"
      headroom: int | None  (min headroom across binding windows, tokens unit)
      unit: "tokens" | "requests" | None
      degraded: bool  True when signal unavailable — do not hard-block

    Degraded-mode behavior (documented + implemented, #141):
      If quota rows cannot be read this cycle, or no rows exist for the agent,
      status="unknown" and degraded=True. The routing engine keeps the agent
      eligible (does not hard-block) but ranks known-headroom agents first.
    """
    rows = _pkg("_read_agent_quota_rows")(conn, agent)
    if rows is None:
        return {
            "status": "unknown",
            "headroom": None,
            "unit": None,
            "degraded": True,
            "reason": "quota_unreadable",
        }
    if not rows:
        # No per-agent signal. Optionally fold in project request budget so
        # limit_requests is not an orphan field relative to the quota matrix.
        project_req = _pkg("_project_request_quota_from_config")()
        if project_req is None:
            return {
                "status": "unknown",
                "headroom": None,
                "unit": None,
                "degraded": True,
                "reason": "no_quota_rows",
            }
        # Project-level requests only — still a real gate when present.
        need = max(1, int(estimated_requests or 1))
        if project_req["headroom"] < need:
            return {
                "status": "exhausted",
                "headroom": project_req["headroom"],
                "unit": "requests",
                "degraded": False,
                "reason": "project_request_budget",
            }
        return {
            "status": "ok",
            "headroom": project_req["headroom"],
            "unit": "requests",
            "degraded": False,
            "reason": "project_request_budget",
        }

    need_tokens = int(estimated_tokens) if estimated_tokens else 0
    need_requests = max(1, int(estimated_requests or 1))
    min_token_headroom = None
    min_request_headroom = None

    for row in rows:
        unit = row["unit"]
        headroom = row["headroom"]
        if unit == "tokens":
            min_token_headroom = (
                headroom if min_token_headroom is None
                else min(min_token_headroom, headroom)
            )
            if need_tokens > 0 and headroom < need_tokens:
                return {
                    "status": "exhausted",
                    "headroom": headroom,
                    "unit": "tokens",
                    "degraded": False,
                    "reason": f"{row['quota_type']}_tokens",
                }
            if need_tokens <= 0 and headroom <= 0:
                return {
                    "status": "exhausted",
                    "headroom": 0,
                    "unit": "tokens",
                    "degraded": False,
                    "reason": f"{row['quota_type']}_tokens_zero",
                }
        elif unit == "requests":
            min_request_headroom = (
                headroom if min_request_headroom is None
                else min(min_request_headroom, headroom)
            )
            if headroom < need_requests:
                return {
                    "status": "exhausted",
                    "headroom": headroom,
                    "unit": "requests",
                    "degraded": False,
                    "reason": f"{row['quota_type']}_requests",
                }

    # Prefer reporting token headroom when present; else request headroom.
    if min_token_headroom is not None:
        return {
            "status": "ok",
            "headroom": min_token_headroom,
            "unit": "tokens",
            "degraded": False,
            "reason": "agent_quotas",
        }
    if min_request_headroom is not None:
        return {
            "status": "ok",
            "headroom": min_request_headroom,
            "unit": "requests",
            "degraded": False,
            "reason": "agent_quotas",
        }
    return {
        "status": "unknown",
        "headroom": None,
        "unit": None,
        "degraded": True,
        "reason": "empty_after_filter",
    }


def _estimate_story_cost_usd(model_version: Optional[str], estimated_tokens: Optional[int]) -> float:
    """Rough USD cost for stage-3 routing (capability → quota → cost)."""
    tokens = int(estimated_tokens or 0)
    if tokens <= 0:
        tokens = 1000  # nominal unit for ranking when estimate missing
    rates = _pkg("_model_rate_for_version")(model_version or "unknown")
    # Assume ~70% input / 30% output for ranking purposes only.
    in_tok = int(tokens * 0.7)
    out_tok = tokens - in_tok
    return (in_tok / 1000 * rates["input"]) + (out_tok / 1000 * rates["output"])
