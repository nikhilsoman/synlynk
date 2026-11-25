"""Backfill: replace estimated_manual native rows with transcript-derived truth (gh:#5503)."""
from dataclasses import dataclass


@dataclass
class Change:
    row_id: int
    session_date: str
    old_basis: object
    action: str   # 'supersede' | 'relabel_unverified'


def plan_backfill(conn) -> list:
    derived_days = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(session_date,1,10) FROM cost_entries WHERE cost_source='transcript_derived'")}
    out = []
    for rid, day, basis in conn.execute(
        "SELECT id, substr(session_date,1,10), estimate_basis FROM cost_entries "
        "WHERE cost_source='estimated_manual' AND harness='claude' AND job_id IS NULL "
        "AND COALESCE(estimate_basis,'') NOT IN ('superseded_by_transcript','unverified_estimate') ORDER BY id"):
        out.append(Change(rid, day, basis, "supersede" if day in derived_days else "relabel_unverified"))
    return out


def apply_backfill(conn) -> list:
    plan = plan_backfill(conn)
    with conn:
        for c in plan:
            new = "superseded_by_transcript" if c.action == "supersede" else "unverified_estimate"
            conn.execute("UPDATE cost_entries SET estimate_basis=? WHERE id=?", (new, c.row_id))
    return plan
