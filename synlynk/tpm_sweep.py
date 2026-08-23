"""Run one policy-gated autonomous TPM sweep pass."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.approval_gate import raise_approval_ticket
from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority


def _ready_stories() -> list:
    from synlynk.db import _get_db

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT story_id, title, role FROM stories WHERE readiness='ready' "
            "AND NOT EXISTS (SELECT 1 FROM daemon_jobs dj "
            "WHERE dj.story_id=stories.story_id "
            "AND dj.status IN ('queued','running','done'))"
        ).fetchall()
        return [
            {"story_id": row[0], "title": row[1], "role": row[2] or "dev"}
            for row in rows
        ]
    finally:
        conn.close()


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    """Dispatch each ready, undispatched story after checking policy authority."""
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    for story in _ready_stories():
        authority = check_authority(
            "task_dispatch:implement",
            role=story["role"],
            repo_path=repo_path,
        )
        if not authority.allowed:
            summary["failed"] += 1
            continue

        if authority.requires_approval:
            action = "task_dispatch:implement"
            resolved_ticket = _find_ticket(story["story_id"], action, "resolved")
            if resolved_ticket:
                _mark_ticket_consumed(resolved_ticket["id"])
                # Fall through to dispatch below, same as an allowed authority.
            else:
                if not _find_ticket(story["story_id"], action, "open"):
                    emit_awaiting_approval(
                        story["story_id"],
                        action,
                        authority.reason,
                    )
                    issue_url = raise_approval_ticket(
                        story_id=story["story_id"],
                        action=action,
                        reason=authority.reason,
                        assignee=assignee,
                        context=f"Story: {story['title']}",
                    )
                    if issue_url:
                        _insert_ticket(story["story_id"], action, issue_url)
                summary["parked"] += 1
                continue

        try:
            dispatch_agent(
                "codex",
                story["title"],
                story_id=story["story_id"],
                task_type="implement",
                context_mode="full",
                role=story["role"],
            )
            summary["advanced"] += 1
        except Exception:
            summary["failed"] += 1

    return summary
