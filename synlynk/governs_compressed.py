"""synlynk.governs_compressed: 5-Stage Compressed GOVERNS Surface Projection.

Invariant 5: Standardizes default user-facing lifecycle presentation to a compressed
5-stage workflow (Plan → Build → Verify → Ship → Sustain) while preserving the full
underlying 7-stage GOVERNS FSM (Dream → Plan → Work → Review/Verify → Ship → Maint → Engag).
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional

COMPRESSED_STAGES = ["plan", "build", "verify", "ship", "sustain"]

STAGE_TO_COMPRESSED: Dict[str, str] = {
    "dream": "plan",
    "plan": "plan",
    "work": "build",
    "review": "verify",
    "verify": "verify",
    "ship": "ship",
    "maint": "sustain",
    "engag": "sustain",
}

COMPRESSED_STAGE_TITLES: Dict[str, str] = {
    "plan": "1. Plan",
    "build": "2. Build",
    "verify": "3. Verify",
    "ship": "4. Ship",
    "sustain": "5. Sustain",
}

FULL_STAGE_TITLES: Dict[str, str] = {
    "dream": "1. Dream",
    "plan": "2. Plan",
    "work": "3. Work",
    "review": "4. Review",
    "ship": "5. Ship",
    "maint": "6. Maint",
    "engag": "7. Engag",
}


def compress_governs_stage(stage: Optional[str]) -> str:
    """Map an internal 7-stage GOVERNS stage name to its compressed 5-stage equivalent."""
    if not stage:
        return "plan"
    norm = str(stage).strip().lower()
    return STAGE_TO_COMPRESSED.get(norm, "plan")


def get_compressed_stage_progress(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group items into the 5 compressed GOVERNS stages."""
    result: Dict[str, List[Dict[str, Any]]] = {stage: [] for stage in COMPRESSED_STAGES}
    for item in items:
        raw_stage = item.get("stage") or item.get("governs_stage") or "plan"
        compressed = compress_governs_stage(raw_stage)
        result[compressed].append(item)
    return result


def format_compressed_governs_summary(items: List[Dict[str, Any]], full: bool = False) -> str:
    """Format a summary table of items across GOVERNS stages (compressed 5-stage by default)."""
    lines = []
    if full:
        lines.append("=== GOVERNS Lifecycle Stages (Full 7-Stage FSM) ===")
        stages = ["dream", "plan", "work", "review", "ship", "maint", "engag"]
        for st in stages:
            matching = [it for it in items if (it.get("stage") or "").lower() == st]
            title = FULL_STAGE_TITLES.get(st, st.capitalize())
            lines.append(f"{title}: {len(matching)} item(s)")
            for it in matching:
                item_id = it.get("id", "")
                item_title = it.get("title", "")
                lines.append(f"  - [{item_id}] {item_title}")
    else:
        lines.append("=== GOVERNS Workflow Progress (Compressed 5-Stage View) ===")
        progress = get_compressed_stage_progress(items)
        for st in COMPRESSED_STAGES:
            matching = progress[st]
            title = COMPRESSED_STAGE_TITLES[st]
            lines.append(f"{title}: {len(matching)} item(s)")
            for it in matching:
                item_id = it.get("id", "")
                item_title = it.get("title", "")
                lines.append(f"  - [{item_id}] {item_title}")
    return "\n".join(lines)
