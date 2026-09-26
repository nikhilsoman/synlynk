"""Event-Driven 7-Stage GOVERNS Lifecycle State Machine (FSM).

Automatically transitions stories across the 7 GOVERNS stages in response to
workspace events (spec commit, plan approval, PR merge, closeout, etc.).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

GOVERNS_STAGES = (
    "goal",
    "open",
    "visualize",
    "execute",
    "release",
    "notify",
    "sustain",
)

GOVERNS_STAGE_RANKS = {stage: i for i, stage in enumerate(GOVERNS_STAGES)}


def determine_target_stage(event_type: str, payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Map an event type and payload to its target GOVERNS lifecycle stage."""
    payload = payload or {}
    et = (event_type or "").lower().strip()

    if et in ("goal_created", "goal_linked"):
        return "goal"

    if et in ("story_created", "backlog_captured", "issue_opened", "issue_ingested"):
        return "open"

    if et in ("spec_committed", "decide_recorded", "spec_verified", "architecture_designed"):
        return "visualize"

    if et in ("plan_approved", "worktree_added", "pr_opened", "dispatch_started", "task_progress"):
        return "execute"

    if et == "spec_or_plan_committed":
        spec_path = str(payload.get("spec_path") or "").lower()
        plan_path = str(payload.get("plan_path") or "").lower()
        file_path = str(payload.get("file_path") or "").lower()
        doc_type = str(payload.get("type") or "").lower()
        if "plan" in plan_path or "plan" in file_path or doc_type == "plan":
            return "execute"
        return "visualize"

    if et in ("pr_merged", "qa_gate_passed", "merge_approved"):
        return "release"

    if et in ("marketing_synced", "broadcast_emitted", "sync_pr", "release_announced"):
        return "notify"

    if et in ("story_done", "closeout_completed", "closeout_receipt", "checkpoint_saved", "job_terminal"):
        if et == "job_terminal" and payload.get("status") != "succeeded":
            return None
        return "sustain"

    return None


def advance_story_governs_stage(
    story_id_or_ref: str,
    event_type: str,
    event_payload: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None,
    force: bool = False,
) -> Optional[str]:
    """Advance a story's governs_stage in state.db if the event represents forward progression."""
    event_payload = event_payload or {}
    target_stage = determine_target_stage(event_type, event_payload)
    if not target_stage:
        return None

    owns_conn = False
    if conn is None:
        try:
            from synlynk import _get_db
            conn = _get_db()
            owns_conn = True
        except Exception:
            return None

    try:
        # Find the story row
        ref = str(story_id_or_ref).strip()
        row = conn.execute(
            "SELECT story_id, governs_stage, status FROM stories WHERE story_id = ? OR gh_issue = ? OR gh_issue = ?",
            (ref, ref.lstrip("#"), f"#{ref.lstrip('#')}"),
        ).fetchone()

        if not row:
            return None

        actual_story_id, current_stage, current_status = row[0], row[1] or "open", row[2] or "open"
        current_rank = GOVERNS_STAGE_RANKS.get(current_stage, 1)
        target_rank = GOVERNS_STAGE_RANKS.get(target_stage, 1)

        # Monotonicity rule: only advance forward unless forced
        if target_rank >= current_rank or force:
            new_status = "done" if target_stage == "sustain" else current_status
            conn.execute(
                "UPDATE stories SET governs_stage = ?, stage = ?, status = ? WHERE story_id = ?",
                (target_stage, target_stage, new_status, actual_story_id),
            )
            conn.commit()
            return target_stage
        return current_stage
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                pass


def handle_event_stage_transition(event_type: str, payload: Dict[str, Any]) -> None:
    """Extract story references from an event and trigger FSM stage transition."""
    if not payload or not isinstance(payload, dict):
        return

    # Look for candidate story references
    candidates = []
    if payload.get("story_id"):
        candidates.append(payload["story_id"])
    if payload.get("issue_number"):
        candidates.append(str(payload["issue_number"]))
    if payload.get("gh_issue"):
        candidates.append(str(payload["gh_issue"]))
    if payload.get("pr_number"):
        candidates.append(str(payload["pr_number"]))

    for candidate in candidates:
        try:
            advance_story_governs_stage(candidate, event_type, payload)
        except Exception:
            pass
