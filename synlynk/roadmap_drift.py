"""Detect drift between decisions, goals, and roadmap arcs (gh:#5020-adjacent)."""

from __future__ import annotations

from typing import Any


def find_roadmap_drift(conn) -> list[dict[str, Any]]:
    """Return a list of drift findings across decisions/goals/roadmap_arcs.

    Three finding kinds:
    - DECISION_GOAL_UNPLACED: an approved decision links a goal whose
      placement_status is not 'placed' (the goal was never actually put
      on the roadmap)
    - ARC_NO_DECISION: a roadmap arc claims a goal_id with no backing
      approved decision (the arc's authority is unverifiable)
    - DECISION_GOAL_MISSING: a decision's goal_id does not resolve in
      goals at all. The decisions.goal_id foreign key normally prevents
      this, but it is checked defensively in case FK enforcement was
      bypassed for a sentinel write (see synlynk/db.py's
      _record_goal_link_status).
    """
    findings: list[dict[str, Any]] = []

    unplaced_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id, g.placement_status "
        "FROM decisions d JOIN goals g ON g.goal_id = d.goal_id "
        "WHERE d.goal_id IS NOT NULL AND g.placement_status != 'placed'"
    ).fetchall()
    for decision_id, goal_id, placement_status in unplaced_rows:
        findings.append(
            {
                "kind": "DECISION_GOAL_UNPLACED",
                "decision_id": decision_id,
                "goal_id": goal_id,
                "detail": (
                    f"decision {decision_id} links goal {goal_id}, but that goal's "
                    f"placement_status is {placement_status!r} (not 'placed')"
                ),
            }
        )

    no_decision_rows = conn.execute(
        "SELECT ra.version, ra.goal_id FROM roadmap_arcs ra "
        "WHERE ra.goal_id IS NOT NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM decisions d WHERE d.goal_id = ra.goal_id AND d.status = 'approved'"
        ")"
    ).fetchall()
    for arc_version, goal_id in no_decision_rows:
        findings.append(
            {
                "kind": "ARC_NO_DECISION",
                "arc_version": arc_version,
                "goal_id": goal_id,
                "detail": (
                    f"roadmap arc {arc_version} claims goal {goal_id}, but no approved "
                    f"decision links that goal"
                ),
            }
        )

    missing_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id FROM decisions d "
        "WHERE d.goal_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM goals g WHERE g.goal_id = d.goal_id)"
    ).fetchall()
    for decision_id, goal_id in missing_rows:
        findings.append(
            {
                "kind": "DECISION_GOAL_MISSING",
                "decision_id": decision_id,
                "goal_id": goal_id,
                "detail": (
                    f"decision {decision_id} references goal_id {goal_id}, which does "
                    f"not exist in goals"
                ),
            }
        )

    return findings


def classify_roadmap_drift(
    findings: list[dict[str, Any]],
) -> tuple[str, str]:
    """Mirror policy_gates.classify_governs_violations's status/detail shape."""
    if not findings:
        return "pass", "no roadmap drift detected"
    summary = "; ".join(f["detail"] for f in findings)
    return "warn", summary
