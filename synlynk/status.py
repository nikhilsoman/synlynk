"""Ecosystem status and capacity reporting for synlynk."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Optional

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.hud import CYCLES

TIER1_CAPACITY = {
    "claude": {"ctx_window_tokens": 200_000, "read_budget_tokens": 750_000, "write_budget_tokens": 32_000, "tool_budget_count": 200},
    "agy": {"ctx_window_tokens": 1_000_000, "read_budget_tokens": 900_000, "write_budget_tokens": 65_000, "tool_budget_count": 500},
    "codex": {"ctx_window_tokens": 128_000, "read_budget_tokens": 110_000, "write_budget_tokens": 16_000, "tool_budget_count": 128},
    "grok": {"ctx_window_tokens": 131_000, "read_budget_tokens": 115_000, "write_budget_tokens": 16_000, "tool_budget_count": 100},
}

TOOL_DEF_OVERHEAD = {"claude": 2200, "agy": 1800, "codex": 1600, "grok": 1400}
TASK_TYPE_OUTPUT = {"implement": 8000, "review": 2000, "plan": 3000, "debug": 1500, "test": 2500, "docs": 2000, "default": 4000}
SYSTEM_OVERHEAD = 2000
LEGACY_CYCLE_ALIASES = {
    "dream": "goal",
    "design": "visualize",
    "plan": "open",
    "work": "execute",
    "build": "execute",
    "ship": "release",
    "maintain": "sustain",
    "engage": "execute",
}
_CATEGORY_TO_CYCLE = {
    "dispatch": "execute",
    "observability": "sustain",
    "harness": "sustain",
    "pm": "open",
    "workspace": "sustain",
}


def _classify_task_type(prompt: str) -> str:
    """Return a coarse task class from prompt text."""
    lower = (prompt or "").lower()
    for keyword in ("implement", "review", "plan", "debug", "test", "docs"):
        if keyword in lower:
            return keyword
    return "default"


def _get_avg_tool_calls(harness_name: str, db_conn=None) -> float:
    """Return a rolling mean tool-call count, or a baseline default."""
    defaults = {"claude": 25, "agy": 30, "codex": 20, "grok": 18}
    default = float(defaults.get(harness_name, 20))

    if db_conn is not None:
        try:
            row = db_conn.execute(
                "SELECT AVG(tool_call_count) FROM telemetry_events "
                "WHERE agent=? AND tool_call_count IS NOT NULL "
                "AND recorded_at >= datetime('now', '-30 days')",
                (harness_name,),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        except Exception:
            pass

    telemetry_file = os.path.join(".synlynk", "telemetry.json")
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                events = json.load(f)
            samples = [e.get("tool_call_count") for e in events if e.get("tool_call_count") is not None]
            if samples:
                return float(sum(samples) / len(samples))
        except Exception:
            pass

    return default


def estimate_dispatch_tokens(prompt: str, context_md: str, harness_name: str) -> dict:
    """Estimate token pressure before dispatch."""
    input_est = (
        len((context_md or "").split()) * 1.3
        + len((prompt or "").split()) * 1.3
        + TOOL_DEF_OVERHEAD.get(harness_name, 2000)
        + SYSTEM_OVERHEAD
    )
    task_type = _classify_task_type(prompt)
    output_est = TASK_TYPE_OUTPUT.get(task_type, TASK_TYPE_OUTPUT["default"])
    tool_est = _get_avg_tool_calls(harness_name) * 800
    return {"input": int(input_est), "output": int(output_est), "tools": int(tool_est)}


def _cycle_from_row(row: sqlite3.Row, cols: set[str]) -> Optional[str]:
    """Map a harness_verb_map row to a lifecycle cycle."""
    cycle_hint = row["cycle_hint"] if "cycle_hint" in cols else None
    if cycle_hint in CYCLES:
        return cycle_hint
    if cycle_hint in LEGACY_CYCLE_ALIASES:
        return LEGACY_CYCLE_ALIASES[cycle_hint]

    verb_category = row["verb_category"] if "verb_category" in cols else None
    if verb_category in _CATEGORY_TO_CYCLE:
        return _CATEGORY_TO_CYCLE[verb_category]

    verb = row["verb"] if "verb" in cols else (row["synlynk_verb"] if "synlynk_verb" in cols else None)
    if isinstance(verb, str):
        if "probe" in verb or "doctor" in verb:
            return "sustain"
        if "dispatch" in verb:
            return "execute"
        if "decide" in verb:
            return "goal"
        if "story" in verb or "epic" in verb:
            return "open"
    return None


def _compute_cycle_capability(harness_name: str, db_conn) -> dict:
    """Aggregate harness verb support into the cycle_capability table."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result = {cycle: {"support": "none", "verb_count": 0, "full_count": 0, "partial_count": 0, "notes": None} for cycle in CYCLES}

    try:
        db_conn.row_factory = sqlite3.Row
        cols = {row[1] for row in db_conn.execute("PRAGMA table_info(harness_verb_map)").fetchall()}
        rows = db_conn.execute("SELECT * FROM harness_verb_map WHERE harness_name=?", (harness_name,)).fetchall()
    except Exception:
        return result

    for row in rows:
        cycle = _cycle_from_row(row, cols)
        if cycle is None:
            continue
        support = None
        if "support" in cols:
            support = row["support"]
        if support is None and "supported" in cols:
            support = row["supported"]
        if support is None:
            support = "none"
        result[cycle]["verb_count"] += 1
        if support == "full":
            result[cycle]["full_count"] += 1
        elif support == "partial":
            result[cycle]["partial_count"] += 1
        if result[cycle]["notes"] is None:
            if "notes" in cols and row["notes"]:
                result[cycle]["notes"] = row["notes"]
            elif "partial_notes" in cols and row["partial_notes"]:
                result[cycle]["notes"] = row["partial_notes"]

    for cycle, data in result.items():
        vc = data["verb_count"]
        fc = data["full_count"]
        pc = data["partial_count"]
        if vc == 0:
            data["support"] = "none"
        elif fc == vc and pc == 0:
            data["support"] = "full"
        elif fc > 0 or pc > 0:
            data["support"] = "partial"
        else:
            data["support"] = "none"

        try:
            db_conn.execute(
                """
                INSERT INTO cycle_capability
                    (harness_name, cycle, support, notes, verb_count, full_count, partial_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(harness_name, cycle) DO UPDATE SET
                    support=excluded.support,
                    notes=excluded.notes,
                    verb_count=excluded.verb_count,
                    full_count=excluded.full_count,
                    partial_count=excluded.partial_count,
                    updated_at=excluded.updated_at
                """,
                (harness_name, cycle, data["support"], data.get("notes"), vc, fc, pc, now),
            )
        except Exception:
            pass

    try:
        db_conn.commit()
    except Exception:
        pass
    return result


def _headless_efficiency_ratio(jobs: list, history_fraction: float = 0.76) -> float:
    """Compute a coarse headless efficiency ratio."""
    if not jobs:
        return 1.0
    total_actual = sum((j.get("context_tokens", 0) or 0) + (j.get("total_tokens", 0) or 0) for j in jobs)
    if total_actual <= 0:
        return 1.0
    total_interactive = total_actual / (1 - history_fraction)
    if total_interactive <= total_actual:
        return 1.0
    return round(total_interactive / total_actual, 1)


def _load_harness_status_rows(db_conn) -> list:
    """Return harness_status rows as dicts, falling back to harness_records."""
    try:
        db_conn.row_factory = sqlite3.Row
        rows = db_conn.execute("SELECT * FROM harness_status ORDER BY harness_name").fetchall()
        if rows:
            return [dict(row) for row in rows]
    except Exception:
        pass

    try:
        db_conn.row_factory = sqlite3.Row
        rows = db_conn.execute(
            "SELECT harness_name, installed_version, last_probe_at, compliance_status, capability_hash "
            "FROM harness_records ORDER BY harness_name"
        ).fetchall()
    except Exception:
        return []

    result = []
    for row in rows:
        data = dict(row)
        status = data.get("compliance_status") or "unknown"
        result.append(
            {
                "harness_name": data.get("harness_name"),
                "attach_rate_24h": 0.0,
                "attach_point_in_time": 1 if status == "ok" else 0,
                "adherence_score": None,
                "completion_rate_24h": None,
                "rescue_count_24h": 0,
                "output_velocity_p50": None,
                "installed_version": data.get("installed_version") or "—",
                "latest_version": None,
                "plan_tier": "unknown",
                "plan_type": "d2c",
                "ctx_window_tokens": None,
                "read_budget_tokens": None,
                "write_budget_tokens": None,
                "tool_budget_count": None,
                "tc1_status": status,
                "tc2_status": status,
                "tc3_status": status,
                "tc4_status": status,
                "harness_compat_score": None,
                "last_probe_at": data.get("last_probe_at"),
                "last_telemetry_at": None,
            }
        )
    return result


def _load_cycle_capability_rows(db_conn) -> dict:
    """Return cycle capability rows as {agent: {cycle: support}}."""
    result: dict[str, dict[str, str]] = {}
    try:
        db_conn.row_factory = sqlite3.Row
        rows = db_conn.execute("SELECT harness_name, cycle, support FROM cycle_capability").fetchall()
    except Exception:
        return result
    for row in rows:
        result.setdefault(row["harness_name"], {})[row["cycle"]] = row["support"]
    return result


def _load_exec_jobs_from_telemetry() -> list:
    """Load recent exec telemetry into headless-efficiency samples."""
    telemetry_file = os.path.join(".synlynk", "telemetry.json")
    if not os.path.exists(telemetry_file):
        return []
    try:
        with open(telemetry_file) as f:
            events = json.load(f)
    except Exception:
        return []
    jobs = []
    for event in events:
        if event.get("type") != "exec":
            continue
        in_tokens = int(event.get("in_tokens", 0) or 0)
        out_tokens = int(event.get("out_tokens", 0) or 0)
        jobs.append({"context_tokens": in_tokens, "total_tokens": in_tokens + out_tokens})
    return jobs


def _format_rates_line(rates_updated_at: Optional[str]) -> str:
    if rates_updated_at:
        return f"RATES   updated {rates_updated_at}"
    return "RATES   never updated ⚠ (hardcoded defaults)"


def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
    rates_updated_at: Optional[str] = None,
    worktree_hint: Optional[dict] = None,
) -> str:
    """Format status output for terminal or JSON consumers."""
    agents = [r["harness_name"] for r in harness_rows] or sorted(HARNESS_CAPABILITY_BASELINES)
    attached = sum(1 for r in harness_rows if int(r.get("attach_point_in_time", 0) or 0))

    if json_output:
        payload = {
            "headless_efficiency": efficiency_ratio,
            "fleet": {
                "attached": attached,
                "total": len(agents),
                "dispatch_mode": dispatch_mode,
            },
            "agents": {r["harness_name"]: r for r in harness_rows},
            "cycle_capability": cycle_map,
            "capacity": TIER1_CAPACITY,
            "sentinels_active": sentinels_active,
            "rates_updated_at": rates_updated_at,
            "worktrees": worktree_hint or {"local": 0, "stale_hint": 0},
        }
        return json.dumps(payload, indent=2)

    support_char = {"full": "●", "partial": "◐", "none": "○"}
    ts = time.strftime("%Y-%m-%d %H:%M")
    lines = [
        f"SYNLYNK ECOSYSTEM STATUS  {ts}",
        "━" * 44,
        "",
        f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
        "",
        f"FLEET   {attached}/{len(agents)} attached   mode: {dispatch_mode}",
    ]
    if worktree_hint and worktree_hint.get("stale_hint", 0) > 0:
        lines.append(
            f"WORKTREES  {worktree_hint['local']} local, {worktree_hint['stale_hint']} "
            "look stale — run `synlynk worktree audit`",
        )
    lines += [
        "BUDGET  limit tracked via .synlynk/config.json",
        _format_rates_line(rates_updated_at),
        "",
        f"{'AGENT SCORE':<14} {'TIER':>10}  {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
    ]
    for row in harness_rows:
        attach = f"{float(row.get('attach_rate_24h', 0.0) or 0.0) * 100:.0f}%"
        completion = row.get("completion_rate_24h")
        complete = f"{completion * 100:.0f}%" if completion is not None else "—"
        ver = row.get("installed_version") or "—"
        drift = " ⚠" if row.get("latest_version") and row.get("latest_version") != ver else ""
        tier = row.get("fleet_tier") or "—"
        lines.append(
            f"  {row['harness_name']:<12} {tier:>10}  {attach:>8}  {complete:>9}  {ver}{drift}"
        )

    lines += ["", f"{'CAPACITY':<14} {'R(read)':>8}  {'W(write)':>9}  {'T(tools)':>8}  {'CTX':>8}"]
    for agent in agents:
        cap = TIER1_CAPACITY.get(agent, {})
        r_tok = f"{cap.get('read_budget_tokens', 0) // 1000}K"
        w_tok = f"{cap.get('write_budget_tokens', 0) // 1000}K"
        t_bud = f"~{cap.get('tool_budget_count', 0)}"
        ctx = f"{cap.get('ctx_window_tokens', 0) // 1000}K"
        lines.append(
            f"  {agent:<12} {r_tok:>8}  {w_tok:>9}  {t_bud:>8}  {ctx:>8}"
        )

    lines += ["", "CYCLE CAPABILITY      " + "  ".join(f"{cycle[:5]:>5}" for cycle in ["Dream", "Plan", "Work", "Ship", "Maint", "Engage"])]
    for agent in agents:
        agent_cycles = cycle_map.get(agent, {})
        dots = "  ".join(f"{support_char.get(agent_cycles.get(cycle, 'none'), '○'):>5}" for cycle in CYCLES)
        lines.append(f"  {agent:<18} {dots}")
    lines += ["", "  ● full  ◐ partial  ○ none", "", f"SENTINELS   {'none active' if sentinels_active == 0 else f'{sentinels_active} active'}"]
    return "\n".join(lines)


def cmd_status(db_conn=None, json_output: bool = False) -> str:
    """Print ecosystem status for the current workspace."""
    from synlynk import _get_db, _read_sentinel_alerts, load_config
    from synlynk.capability_watch import is_smoke_test_stale
    from synlynk.costs import _load_model_rates
    from synlynk.worktree import _worktree_status_hint

    if db_conn is None:
        db_conn = _get_db()

    config = load_config()
    dispatch_mode = config.get("dispatch_mode", "daily-grind")
    harness_rows = _load_harness_status_rows(db_conn)
    # Annotate fleet operability tier (Supported / Proven / Experimental / …)
    try:
        from synlynk.fleet import tier_for_agent

        for row in harness_rows:
            row["fleet_tier"] = tier_for_agent(db_conn, row.get("harness_name", ""))
    except Exception:
        for row in harness_rows:
            row.setdefault("fleet_tier", "—")
    cycle_map = _load_cycle_capability_rows(db_conn)
    efficiency = _headless_efficiency_ratio(_load_exec_jobs_from_telemetry())
    sentinels_active = len(_read_sentinel_alerts())
    rates_updated_at = _load_model_rates().get("rates_updated_at")
    worktree_hint = _worktree_status_hint()
    output = _format_status_terminal(
        harness_rows,
        cycle_map,
        efficiency,
        dispatch_mode,
        sentinels_active,
        json_output=json_output,
        rates_updated_at=rates_updated_at,
        worktree_hint=worktree_hint,
    )
    if not json_output:
        extra_lines = []
        if is_smoke_test_stale(db_conn, threshold_days=7):
            extra_lines.append(
                "⚠ smoke test overdue - run `synlynk selftest --live` or enable `auto_smoke_test` in config"
            )

        recent_incidents = db_conn.execute(
            "SELECT harness, failing_path, classification, detected_at FROM capability_incidents "
            "WHERE classification = 'regression' ORDER BY detected_at DESC LIMIT 5"
        ).fetchall()
        if recent_incidents:
            extra_lines.append("Recent regressions:")
            for harness, path, classification, detected_at in recent_incidents:
                extra_lines.append(f"  [{classification}] {harness} - {path} ({detected_at})")

        if extra_lines:
            output = output + "\n" + "\n".join(extra_lines)
    print(output)
    return output
