"""Sovereign Multi-Home Dynamic Handover & Drain-to-Boundary Protocol.

Pillar 5: Enables seamless interactive hot-swapping of Home Conductors
without AI context amnesia or abrupt mid-story task termination.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

SUPPORTED_HARNESSES = {"claude", "agy", "codex", "grok", "local", "muse"}


HANDOVER_FILE = ".synlynk/handover.json"
ACTIVE_SESSION_FILE = ".synlynk/active_session.json"


def get_active_story_for_harness(repo_path: Union[str, Path] = ".") -> Optional[Dict[str, Any]]:
    """Retrieve currently active in-progress story from state.db."""
    repo = Path(repo_path).resolve()
    db_path = repo / ".synlynk" / "state.db"
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Look for stories in 'in_progress' or 'claimed'
        cur.execute(
            "SELECT id, title, discipline, role, status FROM stories "
            "WHERE status IN ('in_progress', 'claimed') "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception:
        pass
    return None


def calculate_drain_horizon(
    harness: str,
    story_id: Optional[str] = None,
    repo_path: Union[str, Path] = ".",
) -> Dict[str, Any]:
    """Calculate predictive quota runway and safe task drain horizons."""
    repo = Path(repo_path).resolve()
    story = None
    if story_id:
        try:
            db_path = repo / ".synlynk" / "state.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT id, title, discipline, role, status FROM stories WHERE id = ?", (story_id,))
                r = cur.fetchone()
                if r:
                    story = dict(r)
                conn.close()
        except Exception:
            pass
    if not story:
        story = get_active_story_for_harness(repo)

    has_active_story = story is not None
    active_story_id = story["id"] if story else None
    
    # Default estimated drain time: 15-30 min if active story, else 0
    drain_minutes = 20 if has_active_story else 0
    
    return {
        "harness": harness,
        "active_story": story,
        "active_story_id": active_story_id,
        "draining": has_active_story,
        "drain_horizon_minutes": drain_minutes,
        "safe_to_switch_immediate": not has_active_story,
    }


def record_handover_state(
    outgoing_harness: str,
    incoming_harness: str,
    active_story_id: Optional[str] = None,
    repo_path: Union[str, Path] = ".",
) -> Dict[str, Any]:
    """Persist handover state to .synlynk/handover.json."""
    repo = Path(repo_path).resolve()
    synlynk_dir = repo / ".synlynk"
    synlynk_dir.mkdir(parents=True, exist_ok=True)
    handover_path = synlynk_dir / "handover.json"

    data = {
        "outgoing_harness": outgoing_harness,
        "incoming_harness": incoming_harness,
        "active_story_id": active_story_id,
        "status": "draining" if active_story_id else "completed",
        "switched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(handover_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def load_handover_state(repo_path: Union[str, Path] = ".") -> Optional[Dict[str, Any]]:
    """Read current handover state from .synlynk/handover.json."""
    repo = Path(repo_path).resolve()
    handover_path = repo / ".synlynk" / "handover.json"
    if not handover_path.exists():
        return None
    try:
        with open(handover_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def is_harness_draining(harness: str, repo_path: Union[str, Path] = ".") -> bool:
    """Check if the specified harness is currently marked as draining."""
    state = load_handover_state(repo_path)
    if not state:
        return False
    return (
        state.get("outgoing_harness") == harness
        and state.get("status") == "draining"
    )


def complete_harness_drain(harness: str, repo_path: Union[str, Path] = ".") -> None:
    """Mark draining status as completed when the active story finishes."""
    repo = Path(repo_path).resolve()
    handover_path = repo / ".synlynk" / "handover.json"
    state = load_handover_state(repo)
    if state and state.get("outgoing_harness") == harness:
        state["status"] = "completed"
        state["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(handover_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)


def execute_home_handover(
    target_harness: str,
    repo_path: Union[str, Path] = ".",
    force: bool = False,
) -> Dict[str, Any]:
    """Execute dynamic home harness switch with drain-to-boundary protocol."""
    from synlynk import _update_config, load_config
    from synlynk.context import detect_active_home_harness, generate_context

    repo = Path(repo_path).resolve()
    cfg_file = repo / ".synlynk" / "config.json"
    cfg = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    if not cfg:
        cfg = load_config() if callable(load_config) else {}
    
    current_home = cfg.get("home_harness") or detect_active_home_harness(cfg)

    target_harness = target_harness.lower().strip()
    valid_harnesses = {"claude", "agy", "codex", "grok", "local", "muse"}
    if target_harness not in valid_harnesses:
        raise ValueError(
            f"Invalid target home harness: {target_harness!r}. Must be one of {sorted(valid_harnesses)}"
        )


    if current_home == target_harness and not force:
        return {
            "status": "noop",
            "message": f"Harness '{target_harness}' is already the active Home Conductor.",
            "current_home": current_home,
        }

    drain_info = calculate_drain_horizon(current_home, repo_path=repo)
    active_story_id = drain_info["active_story_id"] if not force else None

    # Record handover state
    handover_data = record_handover_state(
        outgoing_harness=current_home,
        incoming_harness=target_harness,
        active_story_id=active_story_id,
        repo_path=repo,
    )

    # Update config.json
    _update_config({"home_harness": target_harness})

    # Regenerate context.md with new home conductor & drain note
    try:
        generate_context()
    except Exception:
        pass

    return {
        "status": "switched",
        "outgoing_harness": current_home,
        "incoming_harness": target_harness,
        "draining": bool(active_story_id),
        "active_story_id": active_story_id,
        "drain_horizon_minutes": drain_info["drain_horizon_minutes"],
        "handover_data": handover_data,
    }
