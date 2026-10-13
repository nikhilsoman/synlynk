"""Run one policy-gated autonomous TPM sweep pass."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.approval_gate import raise_approval_ticket
from synlynk.backlog import ingest_backlog, triage_backlog
from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority, load_policy

_FALLBACK_HARNESS = "codex"


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


def _resolve_harness(role: str, repo_path: str) -> str:
    """Look up the default dispatch harness for a story's role.

    Falls back to codex (the pre-existing hardcoded behavior) for any role
    with no entry in policy["agent_roles"], so unmapped roles keep working
    exactly as before this change.
    """
    policy = load_policy(repo_path=repo_path)
    role_entry = policy.get("agent_roles", {}).get(role)
    if role_entry and role_entry.get("default_harness"):
        return role_entry["default_harness"]
    return _FALLBACK_HARNESS


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    """Dispatch each ready, undispatched story after checking policy authority."""
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    try:
        from synlynk.backlog import auto_promote_backlog
        auto_promote_backlog()
    except Exception:
        pass

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
            harness = _resolve_harness(story["role"], repo_path)
            dispatch_agent(
                harness,
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


def run_tpm_wake_cycle() -> dict:
    """Run the TPM wake-cycle SOP: intake, triage, ambiguity routing, sweep.

    Raw GitHub issues are ingested and triaged, then each triaged backlog item
    is routed to a PM-approval-gate status based on its ambiguity signals:
    a missing goal link needs the architect, a tier-3 item needs PM
    prioritisation, and everything else is routine TPM-drafted work. The
    existing sweep pass then runs unchanged for downstream tracking.
    """
    from synlynk.db import _get_db

    routed = {
        "needs_architect_input": 0,
        "needs_pm_priority_input": 0,
        "tpm_drafted": 0,
    }

    conn = _get_db()
    try:
        ingest_backlog(db_conn=conn)
        triaged_items = triage_backlog(auto_promote=False, db_conn=conn)

        for item in triaged_items:
            if not item.get("goal_id"):
                new_status = "needs_architect_input"
            elif item.get("complexity_tier") == 3:
                new_status = "needs_pm_priority_input"
            else:
                new_status = "tpm_drafted"
            conn.execute(
                "UPDATE backlog_items SET status = ? WHERE id = ?",
                (new_status, item["id"]),
            )
            routed[new_status] += 1
        conn.commit()
    finally:
        conn.close()

    sweep_result = run_sweep_pass()

    return {
        "triaged": len(triaged_items),
        "routed": routed,
        "sweep": sweep_result,
    }
