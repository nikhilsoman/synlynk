"""Underused-feature banner derived from the workspace snapshot."""
from typing import Optional
def _compute_underused_feature_banner(data: dict) -> Optional[str]:
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or len(jobs) < 10:
        return None

    # approve/kill is useful only while a user has an approvable PR. Workspaces
    # that delegate review/merge work to a reviewer job should not be prompted
    # to take that manual path.
    pending_prs = data.get("pending_approvable_prs")
    if not pending_prs or data.get("reviewer_dispatch"):
        return None

    approve_kill_used = any(
        isinstance(job, dict)
        and str(job.get("status") or "").strip().lower() in {"approved", "killed"}
        for job in jobs
    )
    if not approve_kill_used:
        for action in data.get("actions", []):
            if not isinstance(action, dict):
                continue
            if action.get("action") not in {"approve_pr", "kill_job"}:
                continue
            result = action.get("result")
            if not isinstance(result, dict) or result.get("ok", True):
                approve_kill_used = True
                break
    if approve_kill_used:
        return None
    return f"You've dispatched {len(jobs)} jobs but never used approve/kill -- try it"

