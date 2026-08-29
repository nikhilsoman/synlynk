"""synlynk quota: per-harness quota headroom, upsert, and cost estimation."""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

try:
    from datetime import UTC  # Python 3.11+
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[misc,assignment]


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

# Rolling window lengths used for telemetry aggregation (#291).
# "monthly" is approximated as 30 days — provider calendars vary.
_QUOTA_WINDOW_SECONDS = {
    "5h": 5 * 3600,
    "hourly": 3600,
    "daily": 86400,
    "weekly": 7 * 86400,
    "monthly": 30 * 86400,
}

# Default capacity when providers don't expose a usage/limits API.
# These are synlynk-proxy ceilings (telemetry-derived usage vs config limits),
# not live Anthropic/OpenAI plan meters. Override via
# .synlynk/config.json → budget.quota_limits.
_DEFAULT_QUOTA_LIMITS = {
    "5h": {"tokens": 200_000, "requests": 100},
    "hourly": {"tokens": 100_000, "requests": 30},
    "daily": {"tokens": 500_000, "requests": 200},
    "weekly": {"tokens": 2_000_000, "requests": 1_000},
    "monthly": {"tokens": 5_000_000, "requests": 3_000},
}

# Harness binary names we attribute telemetry to (first token of command).
_KNOWN_AGENT_BINARIES = frozenset({
    "claude", "agy", "codex", "grok", "gemini", "local",
})


def _quota_headroom(limit_tokens: int, used_tokens: int) -> int:
    """Return remaining capacity for a quota row (never negative)."""
    try:
        return max(0, int(limit_tokens) - int(used_tokens or 0))
    except (TypeError, ValueError):
        return 0


def _load_telemetry_events(telemetry_path: Optional[str] = None) -> list:
    """Load .synlynk/telemetry.json events; return [] on missing/unreadable."""
    path = telemetry_path or os.path.join(".synlynk", "telemetry.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, TypeError):
        return []


def _event_epoch(event: dict) -> Optional[float]:
    """Best-effort epoch seconds from a telemetry event."""
    ts = event.get("_ts")
    if ts is not None:
        try:
            return float(ts)
        except (TypeError, ValueError):
            pass
    raw = event.get("timestamp")
    if not raw or not isinstance(raw, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt.endswith("Z") or "T" in fmt:
                dt = dt.replace(tzinfo=UTC)
            else:
                # Naive local timestamps — treat as local wall clock via time.mktime.
                return time.mktime(dt.timetuple())
            return dt.timestamp()
        except ValueError:
            continue
    return None


def _agent_from_telemetry_event(event: dict) -> Optional[str]:
    """Resolve harness name from an explicit field or the command's first token."""
    agent = event.get("agent")
    if isinstance(agent, str) and agent.strip():
        name = agent.strip().lower()
        # Normalize common aliases
        if name == "gemini":
            return "agy"
        return name
    cmd = event.get("command") or ""
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    first = cmd.strip().split()[0]
    # Strip path components: /usr/local/bin/claude → claude
    first = os.path.basename(first).lower()
    if first == "gemini":
        return "agy"
    if first in _KNOWN_AGENT_BINARIES:
        return first
    return None


def _quota_limits_from_config() -> dict:
    """Merge config budget.quota_limits over defaults.

    Expected shape (all optional)::

        "budget": {
          "quota_limits": {
            "5h": {"tokens": 200000, "requests": 100},
            ...
          }
        }
    """
    limits = {
        qtype: dict(vals) for qtype, vals in _DEFAULT_QUOTA_LIMITS.items()
    }
    try:
        config = _pkg("load_config")()
        overrides = (config or {}).get("budget", {}).get("quota_limits") or {}
    except Exception:
        return limits
    if not isinstance(overrides, dict):
        return limits
    for qtype, vals in overrides.items():
        if qtype not in limits or not isinstance(vals, dict):
            continue
        for unit_key in ("tokens", "requests"):
            if unit_key in vals:
                try:
                    limits[qtype][unit_key] = int(vals[unit_key])
                except (TypeError, ValueError):
                    pass
    return limits


def _window_reset_at_iso(now: float, window_seconds: int) -> str:
    """ISO-8601 UTC timestamp for when the current rolling window ends."""
    # Rolling window: reset is "now + remaining time until window rolls fully"
    # For a simple rolling proxy, report end of current window as now + full length
    # from the oldest event's alignment is complex; use now + window as horizon.
    # More useful for operators: next full-window expiry from now.
    reset_epoch = now + window_seconds
    return datetime.fromtimestamp(reset_epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aggregate_usage_from_telemetry(
    events: list,
    *,
    now: Optional[float] = None,
) -> dict:
    """Aggregate per-harness token and request usage inside each quota window.

    Returns::

        {
          "claude": {
            "5h": {"tokens": 1200, "requests": 3},
            "hourly": {...},
            ...
          },
          ...
        }

    Only agents observed in telemetry are included. Events without a parseable
    timestamp are skipped (cannot attribute to a window).
    """
    now_ts = float(now if now is not None else time.time())
    usage: dict = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        # Count exec + completed dispatch-related token rows; skip pure markers
        # without usage when type is unknown. Prefer type=="exec" (has tokens).
        etype = event.get("type")
        if etype not in (None, "exec", "dispatch"):
            # Still allow bare events that carry tokens/harness without type
            if event.get("in_tokens") is None and event.get("out_tokens") is None:
                if etype not in ("exec",):
                    continue
        agent = _agent_from_telemetry_event(event)
        if not agent:
            continue
        epoch = _event_epoch(event)
        if epoch is None:
            continue
        try:
            in_tok = int(event.get("in_tokens") or 0)
            out_tok = int(event.get("out_tokens") or 0)
        except (TypeError, ValueError):
            in_tok, out_tok = 0, 0
        total_tok = max(0, in_tok) + max(0, out_tok)
        # Request-count proxy: every exec (and token-bearing dispatch) counts as 1
        is_request = etype == "exec" or total_tok > 0 or event.get("command")
        if not is_request and total_tok <= 0:
            continue
        agent_usage = usage.setdefault(agent, {
            q: {"tokens": 0, "requests": 0} for q in QUOTA_TYPES
        })
        for qtype, window_s in _QUOTA_WINDOW_SECONDS.items():
            if epoch >= now_ts - window_s:
                agent_usage[qtype]["tokens"] += total_tok
                if etype == "exec" or total_tok > 0:
                    agent_usage[qtype]["requests"] += 1
    return usage


def refresh_agent_quotas_from_telemetry(
    conn=None,
    *,
    telemetry_path: Optional[str] = None,
    now: Optional[float] = None,
) -> int:
    """Populate harness_quotas from .synlynk/telemetry.json usage proxy (#291).

    Provider CLIs rarely expose a durable usage/limits API, so synlynk uses its
    own exec telemetry as the usage signal and config/default ceilings as
    limits. Upserts tokens + requests rows for every plan window for each
    agent seen in telemetry.

    Returns the number of harness_quotas rows written/updated.
    """
    events = _load_telemetry_events(telemetry_path)
    if not events:
        return 0
    now_ts = float(now if now is not None else time.time())
    usage = _aggregate_usage_from_telemetry(events, now=now_ts)
    if not usage:
        return 0
    limits = _quota_limits_from_config()
    own_conn = conn is None
    if own_conn:
        conn = _pkg("_get_db")()
    written = 0
    try:
        for agent, windows in usage.items():
            for qtype in QUOTA_TYPES:
                w = windows.get(qtype) or {"tokens": 0, "requests": 0}
                window_s = _QUOTA_WINDOW_SECONDS[qtype]
                reset_at = _window_reset_at_iso(now_ts, window_s)
                qlimits = limits.get(qtype) or _DEFAULT_QUOTA_LIMITS[qtype]
                token_limit = int(qlimits.get("tokens") or 0)
                req_limit = int(qlimits.get("requests") or 0)
                if token_limit > 0:
                    _upsert_agent_quota(
                        agent,
                        qtype,
                        limit_tokens=token_limit,
                        used_tokens=int(w.get("tokens") or 0),
                        model="unknown",
                        unit="tokens",
                        reset_at=reset_at,
                        conn=conn,
                    )
                    written += 1
                if req_limit > 0:
                    _upsert_agent_quota(
                        agent,
                        qtype,
                        limit_tokens=req_limit,
                        used_tokens=int(w.get("requests") or 0),
                        model="unknown",
                        unit="requests",
                        reset_at=reset_at,
                        conn=conn,
                    )
                    written += 1
        # Always commit quota rows so stage-2 / CLI see durable headroom even when
        # the caller passed an open connection (SQLite same-conn visibility alone
        # is not enough once that conn closes without commit).
        if written:
            conn.commit()
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return written


# Back-compat private alias used by package re-exports / tests.
_refresh_agent_quotas_from_telemetry = refresh_agent_quotas_from_telemetry


def cmd_quota(agent: Optional[str] = None, json_output: bool = False) -> None:
    """Report per-harness quota headroom and reset times (synlynk quota).

    Refreshes harness_quotas from telemetry first so the table is never a
    permanent empty shell when usage data exists.
    """
    # Refresh proxy usage before read so CLI and stage-2 share one pipeline.
    refresh_agent_quotas_from_telemetry()

    conn = _pkg("_get_db")()
    try:
        if agent:
            agents = [agent]
        else:
            rows = conn.execute(
                "SELECT DISTINCT harness FROM harness_quotas ORDER BY harness"
            ).fetchall()
            agents = [r[0] for r in rows]
            if not agents:
                # Also surface known fleet agents with no signal yet
                baselines = _pkg("HARNESS_CAPABILITY_BASELINES") or {}
                agents = sorted(baselines.keys()) if baselines else []

        report = []
        for name in agents:
            rows = _read_agent_quota_rows(conn, name) or []
            status = _quota_status_for_agent(conn, name)
            report.append({
                "agent": name,
                "status": status.get("status"),
                "degraded": status.get("degraded"),
                "reason": status.get("reason"),
                "min_headroom": status.get("headroom"),
                "unit": status.get("unit"),
                "windows": [
                    {
                        "quota_type": r["quota_type"],
                        "unit": r["unit"],
                        "limit": r["limit_tokens"],
                        "used": r["used_tokens"],
                        "headroom": r["headroom"],
                        "reset_at": r["reset_at"],
                        "updated_at": r["updated_at"],
                    }
                    for r in rows
                ],
            })
    finally:
        conn.close()

    if json_output:
        print(json.dumps({"agents": report, "source": "telemetry_proxy"}, indent=2))
        return

    if not report or all(not a["windows"] for a in report):
        print("  No agent quota data yet.")
        print("  Run synlynk exec / dispatch so telemetry accumulates, then re-run")
        print("  `synlynk quota`. Limits come from budget.quota_limits (or defaults).")
        return

    print("  Agent quota headroom  (source: telemetry proxy + config limits)")
    print("  " + "─" * 72)
    for entry in report:
        name = entry["agent"]
        windows = entry["windows"]
        if not windows:
            print(f"  {name:10s}  (no rows — degraded/unknown for stage-2 gate)")
            continue
        st = entry["status"]
        deg = " degraded" if entry.get("degraded") else ""
        mh = entry.get("min_headroom")
        unit = entry.get("unit") or ""
        mh_s = f"{mh:,} {unit}" if mh is not None else "—"
        print(f"  {name:10s}  status={st}{deg}  min_headroom={mh_s}")
        # Group by quota_type for a compact table
        by_type: dict = {}
        for w in windows:
            by_type.setdefault(w["quota_type"], []).append(w)
        for qtype in QUOTA_TYPES:
            if qtype not in by_type:
                continue
            parts = []
            reset_at = None
            for w in by_type[qtype]:
                parts.append(
                    f"{w['unit']}: {w['used']:,}/{w['limit']:,} "
                    f"(headroom {w['headroom']:,})"
                )
                reset_at = w.get("reset_at") or reset_at
            reset_s = f"  reset≈{reset_at}" if reset_at else ""
            print(f"    {qtype:8s}  " + "  ·  ".join(parts) + reset_s)
    print()
    print("  Note: usage is summed from .synlynk/telemetry.json within each rolling")
    print("  window; limits are config defaults, not live provider plan meters.")


def cmd_quota_tpm_view() -> None:
    """Read-only CLI wrapper around tpm_observe_reservations()."""
    from synlynk.tpm_hooks import tpm_observe_reservations

    conn = _pkg("_get_db")()
    try:
        reservations = tpm_observe_reservations(conn)
    finally:
        conn.close()

    if not reservations:
        print("  No open reservations")
        return

    print(
        f"\n  {'Harness':<10} {'Tokens':>10} {'Scope':<10} "
        f"{'Scope ID':<14} {'Job ID':<14} {'Headroom':>10}"
    )
    print("  " + "-" * 72)
    for reservation in reservations:
        headroom = (
            "unknown"
            if reservation["current_headroom"] is None
            else f"{reservation['current_headroom']:,}"
        )
        print(
            f"  {reservation['harness']:<10} {reservation['tokens']:>10,} "
            f"{reservation['scope']:<10} "
            f"{(reservation['scope_id'] or '-'):<14} "
            f"{(reservation['job_id'] or '-'):<14} {headroom:>10}"
        )


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
    """Insert or update an harness_quotas row. Validates quota_type and unit."""
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
            INSERT INTO harness_quotas
                (harness, model, quota_type, unit, limit_tokens, used_tokens,
                 reset_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(harness, model, quota_type, unit) DO UPDATE SET
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
        conn.commit()
    finally:
        if own_conn:
            conn.close()


_RESERVATION_EXPIRY_SECONDS = 24 * 3600  # comfortably > longest QUOTA_TYPES window (5h)


def _open_reservation(
    conn,
    harness: str,
    tokens: int,
    scope: str,
    scope_id: Optional[str] = None,
    job_id: Optional[str] = None,
) -> int:
    """Opens an harness_reservations row. Returns the new reservation id.

    scope is one of 'plan' | 'session' | 'adhoc' (not validated here -- callers
    are internal and already constrained by the design's dispatch-time flow).
    """
    cur = conn.execute(
        "INSERT INTO harness_reservations (harness, tokens, scope, scope_id, job_id, status) "
        "VALUES (?, ?, ?, ?, ?, 'open')",
        (harness, int(tokens), scope, scope_id, job_id),
    )
    conn.commit()
    return cur.lastrowid


def _release_reservation(conn, reservation_id: int) -> None:
    """Marks a reservation released. Idempotent -- releasing twice is a no-op
    on the second call since the WHERE clause only matches status='open'."""
    conn.execute(
        "UPDATE harness_reservations SET status='released', released_at=CURRENT_TIMESTAMP "
        "WHERE id=? AND status='open'",
        (reservation_id,),
    )
    conn.commit()


def _open_reservations_sum(conn, harness: str) -> int:
    """Sums tokens from open, non-expired reservations for one harness.

    Lazy expiry: a reservation older than _RESERVATION_EXPIRY_SECONDS is
    excluded from the sum on read, not physically mutated -- avoids an extra
    write on every dispatch just to sweep abandoned reservations.
    """
    cutoff = datetime.now(UTC).timestamp() - _RESERVATION_EXPIRY_SECONDS
    cutoff_iso = datetime.fromtimestamp(cutoff, UTC).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT COALESCE(SUM(tokens), 0) FROM harness_reservations "
        "WHERE harness=? AND status='open' AND created_at >= ?",
        (harness, cutoff_iso),
    ).fetchone()
    return int(row[0] or 0)


def _force_exhaust_quota(conn, harness: str, window: str) -> None:
    """Reactive correction: zeroes `harness`'s headroom for `window` immediately,
    from a real observed rejection signal (see sentinel.py QUOTA_EXHAUSTED).

    Never touches daemon_jobs -- running jobs keep running (wait/resume policy).
    If no harness_quotas row exists yet for this harness/window, creates a
    zero-headroom placeholder row so the next _quota_status_for_agent() call
    sees it as exhausted rather than "unknown" (degraded, non-blocking).
    """
    if window not in QUOTA_TYPES:
        window = "5h"
    rows = conn.execute(
        "SELECT model, unit, limit_tokens FROM harness_quotas WHERE harness=? AND quota_type=?",
        (harness, window),
    ).fetchall()
    if not rows:
        _upsert_agent_quota(
            harness, window, limit_tokens=0, used_tokens=0, unit="tokens", conn=conn
        )
        return
    for model, unit, limit_tokens in rows:
        conn.execute(
            "UPDATE harness_quotas SET used_tokens=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE harness=? AND model=? AND quota_type=? AND unit=?",
            (int(limit_tokens), harness, model, window, unit),
        )
    conn.commit()


def _project_request_quota_from_config() -> Optional[dict]:
    """Unify project-level budget.limit_requests with harness_quotas request unit.

    Returns a synthetic quota dict, or None if config cannot be read.
    This is the bridge between .synlynk/config.json limit_requests and the
    per-harness request-unit rows in harness_quotas — not a substitute for
    per-harness plan quotas, but a workspace floor when no harness-level request
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
    """Read harness_quotas rows for a harness.

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
            SELECT harness, model, quota_type, unit, limit_tokens, used_tokens,
                   reset_at, updated_at
            FROM harness_quotas
            WHERE harness = ?
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
            "source": "harness_quotas",
        })
    return result


def _quota_status_for_agent(
    conn,
    agent: str,
    estimated_tokens: Optional[int] = None,
    estimated_requests: int = 1,
) -> dict:
    """Stage-2 quota gate for one harness.

    Returns dict with keys:
      status: "ok" | "exhausted" | "unknown"
      headroom: int | None  (min headroom across binding windows, tokens unit)
      unit: "tokens" | "requests" | None
      degraded: bool  True when signal unavailable — do not hard-block

    Degraded-mode behavior (documented + implemented, #141):
      If quota rows cannot be read this cycle, or no rows exist for the agent,
      status="unknown" and degraded=True. The routing engine keeps the harness
      eligible (does not hard-block) but ranks known-headroom harnesses first.
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
        # No per-harness signal. Optionally fold in project request budget so
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
    reserved = _pkg("_open_reservations_sum")(conn, agent)
    min_token_headroom = None
    min_request_headroom = None

    for row in rows:
        unit = row["unit"]
        headroom = row["headroom"]
        if unit == "tokens":
            headroom = max(0, headroom - reserved)
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
            "reason": "harness_quotas",
        }
    if min_request_headroom is not None:
        return {
            "status": "ok",
            "headroom": min_request_headroom,
            "unit": "requests",
            "degraded": False,
            "reason": "harness_quotas",
        }
    return {
        "status": "unknown",
        "headroom": None,
        "unit": None,
        "degraded": True,
        "reason": "empty_after_filter",
    }


def _estimate_story_cost_usd(
    model_version: Optional[str],
    estimated_tokens: Optional[int],
    agent: Optional[str] = None,
) -> float:
    """Rough USD cost for stage-3 routing (capability → quota → cost)."""
    tokens = int(estimated_tokens or 0)
    if tokens <= 0:
        tokens = 1000  # nominal unit for ranking when estimate missing
    rates = _pkg("_model_rate_for_version")(model_version or "unknown", agent=agent)
    # Assume ~70% input / 30% output for ranking purposes only.
    in_tok = int(tokens * 0.7)
    out_tok = tokens - in_tok
    return (in_tok / 1000 * rates["input"]) + (out_tok / 1000 * rates["output"])
