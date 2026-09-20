"""synlynk advisory: Empirical Time-of-Day Dynamic Quota & Fleet Advisory Service."""

from datetime import datetime, timezone
import json
from typing import Any, Optional

try:
    from datetime import UTC  # Python 3.11+
except ImportError:  # pragma: no cover
    UTC = timezone.utc  # type: ignore[misc,assignment]


_HARNESS_RECOMMENDATIONS = {
    "claude": {"off_peak_multiplier": 1.5, "peak_multiplier": 0.65},
    "agy": {"off_peak_multiplier": 1.7, "peak_multiplier": 0.70},
    "codex": {"off_peak_multiplier": 1.4, "peak_multiplier": 0.75},
    "grok": {"off_peak_multiplier": 1.3, "peak_multiplier": 0.80},
}

_TIME_BLOCKS = [
    {
        "utc_range": "00:00 - 08:00 UTC",
        "type": "off_peak",
        "multiplier": 1.6,
        "regional_concurrency": "Low (US late night / Asia morning)",
        "description": "Expanded capacity window (~1.6x)",
    },
    {
        "utc_range": "08:00 - 13:00 UTC",
        "type": "standard",
        "multiplier": 1.0,
        "regional_concurrency": "Moderate (Europe workday)",
        "description": "Standard baseline allowance (1.0x)",
    },
    {
        "utc_range": "13:00 - 19:00 UTC",
        "type": "peak_surge",
        "multiplier": 0.65,
        "regional_concurrency": "High (US workday & EU peak)",
        "description": "Peak surge throttling (~0.65x)",
    },
    {
        "utc_range": "19:00 - 24:00 UTC",
        "type": "standard",
        "multiplier": 1.0,
        "regional_concurrency": "Moderate (US afternoon)",
        "description": "Standard baseline allowance (1.0x)",
    },
]


def get_current_capacity_factor(utc_hour: Optional[int] = None) -> dict[str, Any]:
    """Determine current dynamic capacity factor and recommended dispatch strategy based on UTC hour."""
    if utc_hour is None:
        utc_hour = datetime.now(UTC).hour

    if 0 <= utc_hour < 8:
        return {
            "utc_hour": utc_hour,
            "window_type": "off_peak",
            "capacity_multiplier": 1.6,
            "recommended_action": "Optimal for swarm dispatches and heavy batch jobs",
        }
    elif 13 <= utc_hour < 19:
        return {
            "utc_hour": utc_hour,
            "window_type": "peak_surge",
            "capacity_multiplier": 0.65,
            "recommended_action": "Throttle non-critical tasks or defer to off-peak",
        }
    else:
        return {
            "utc_hour": utc_hour,
            "window_type": "standard",
            "capacity_multiplier": 1.0,
            "recommended_action": "Standard dispatch operations",
        }


def get_utilization_advisory(now_dt: Optional[datetime] = None) -> dict[str, Any]:
    """Synthesize full fleet utilization advisory with 24-hour time blocks and harness multipliers."""
    dt = now_dt or datetime.now(UTC)
    current_hour = dt.hour
    status = get_current_capacity_factor(current_hour)

    return {
        "schema_version": 1,
        "generated_at": dt.isoformat(),
        "current_utc_hour": current_hour,
        "current_status": status,
        "time_blocks": _TIME_BLOCKS,
        "harness_recommendations": _HARNESS_RECOMMENDATIONS,
    }


def format_advisory_text(advisory: dict[str, Any]) -> str:
    """Format advisory summary formatted strictly <= 56 characters wide."""
    curr = advisory.get("current_status", {})
    win_type = curr.get("window_type", "unknown").upper().replace("_", "-")
    hour = advisory.get("current_utc_hour", 0)
    mult = curr.get("capacity_multiplier", 1.0)
    action = curr.get("recommended_action", "")

    # Format cleanly <= 56 cols
    lines = [
        "=" * 56,
        "  SYNLYNK FLEET UTILIZATION ADVISORY (2026)",
        "=" * 56,
        f"Status: {win_type} ({hour:02d}:00 UTC)",
        f"Capacity Multiplier: {mult:.2f}x",
        f"Action: {action}"[:56],
        "",
        "--- Dynamic 24H Capacity Windows ---",
        "00:00-08:00 UTC : 1.60x (Off-Peak / US Night)",
        "08:00-13:00 UTC : 1.00x (Standard / EU Workday)",
        "13:00-19:00 UTC : 0.65x (Peak Surge / US Peak)",
        "19:00-24:00 UTC : 1.00x (Standard / US Afternoon)",
        "",
        "--- Harness Off-Peak Multipliers ---",
        "• claude : 1.50x bonus capacity",
        "• agy    : 1.70x bonus (Gemini & Claude)",
        "• codex  : 1.40x bonus capacity",
        "• grok   : 1.30x bonus capacity",
        "=" * 56,
    ]
    return "\n".join(lines)


def export_advisory_json(advisory: dict[str, Any]) -> str:
    """Export advisory structure to formatted JSON string."""
    return json.dumps(advisory, indent=2)
