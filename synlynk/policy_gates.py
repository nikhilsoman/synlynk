"""Observe/enforce mode resolution and verdict logging for synlynk pr check gates."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _read_repo_policy_overrides() -> dict[str, Any]:
    try:
        with open(os.path.join(os.getcwd(), ".synlynk", "policy.json"), encoding="utf-8") as fh:
            policy = json.load(fh)
        return policy.get("overrides", {}) or {}
    except (OSError, TypeError, ValueError):
        return {}


def gate_mode(gate_section: str, mode_key: str) -> str:
    """Return 'enforce' (default) or 'observe' for a gate's mode flag."""
    overrides = _read_repo_policy_overrides()
    value = overrides.get(gate_section, {}).get(mode_key)
    return value if value in ("enforce", "observe") else "enforce"


_INSUFFICIENT_DATA_MARKERS = (
    "no implementing job provenance found",
    "no reviewing job provenance found",
    "ambiguous implementation job provenance",
    "incomplete harness/model provenance",
)


def classify_cross_harness_verdict(ok: bool, detail: str) -> tuple[str, str]:
    if ok:
        return "pass", detail
    if any(marker in detail for marker in _INSUFFICIENT_DATA_MARKERS):
        return "insufficient_data", detail
    return "warn", detail


def classify_governs_violations(violations: list[dict]) -> tuple[str, str]:
    if not violations:
        return "pass", "no GOVERNS linkage violations"
    summary = "; ".join(
        f"{v['job_id']} (story={v.get('story_id') or 'none'}; {v['reason']})"
        for v in violations
    )
    return "warn", summary


def record_gate_event(conn, *, pr_number: int, gate: str, mode: str, verdict: str, detail: str) -> None:
    try:
        conn.execute(
            "INSERT INTO policy_gate_events (pr_number, gate, mode, verdict, detail, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pr_number, gate, mode, verdict, detail, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except Exception as exc:
        print(f"  ⚠ [PR CHECK] failed to record policy_gate_events row for gate {gate!r}: {exc}")


def gate_streak(conn, gate: str) -> int | None:
    try:
        rows = conn.execute(
            "SELECT verdict FROM policy_gate_events WHERE gate=? ORDER BY id DESC",
            (gate,),
        ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    streak = 0
    for (verdict,) in rows:
        if verdict != "pass":
            break
        streak += 1
    return streak


RE_HARDEN_THRESHOLD = 100


@dataclass
class GateEvaluation:
    should_block: bool
    verdict: str
    message: str


def _evaluate_gate(
    conn, *, pr_number: int, gate: str, mode_key: str, verdict: tuple[str, str],
) -> GateEvaluation:
    mode = gate_mode(gate, mode_key)
    status, detail = verdict
    record_gate_event(conn, pr_number=pr_number, gate=gate, mode=mode, verdict=status, detail=detail)

    if status == "pass":
        return GateEvaluation(should_block=False, verdict=status, message=detail)
    if mode == "enforce":
        return GateEvaluation(should_block=True, verdict=status, message=detail)
    return GateEvaluation(
        should_block=False,
        verdict=status,
        message=f"[OBSERVE MODE — not blocking] {detail}",
    )
