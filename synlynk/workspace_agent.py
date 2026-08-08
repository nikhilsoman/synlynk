"""Pilot durable workspace agent for local lifecycle boundary nudges.

Durability here is provided by the agent config, persisted subscription
checkpoints, and cron-scheduled execution rather than a long-lived process.
"""

AGENT_NAME = "workspace-lifecycle-nudge"
_EVENT_TYPES = ["pr_merged", "story_done", "spec_or_plan_committed", "cron_heartbeat"]


def cmd_workspace_agent_run() -> None:
    """Consume workspace lifecycle events and print any actionable nudges."""
    from synlynk import _get_db
    from synlynk.events import advance_checkpoint, pending_events, scan_local_events
    from synlynk.fencing import NudgeData, render_nudge_fence

    scan_local_events(AGENT_NAME)

    nudges = []
    conn = _get_db()

    for event in pending_events(AGENT_NAME, "story_done"):
        goal_ids = event["payload"].get("goal_ids", [])
        for goal_id in goal_ids:
            total = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE goal_id=?", (goal_id,)
            ).fetchone()[0]
            done = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE goal_id=? AND status='done'",
                (goal_id,),
            ).fetchone()[0]
            if total > 0 and total == done:
                outcome = conn.execute(
                    "SELECT outcome FROM goals WHERE goal_id=?", (goal_id,)
                ).fetchone()
                nudges.append(NudgeData(
                    nudge_id=f"goal-closed-{goal_id}",
                    title="Goal closed",
                    message=(
                        f"{goal_id} ({outcome[0] if outcome else goal_id}) "
                        "— all linked stories are done"
                    ),
                    follow_up="synlynk goal status",
                ))
        advance_checkpoint(AGENT_NAME, "story_done", event["id"])

    for event_type in ("pr_merged", "spec_or_plan_committed", "cron_heartbeat"):
        for event in pending_events(AGENT_NAME, event_type):
            advance_checkpoint(AGENT_NAME, event_type, event["id"])

    conn.close()

    for nudge in nudges:
        print(render_nudge_fence(nudge))
