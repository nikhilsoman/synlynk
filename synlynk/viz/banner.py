"""Underused-feature banner derived from the workspace snapshot."""
from typing import Optional
def _compute_underused_feature_banner(data: dict) -> Optional[str]:
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list) or len(jobs) < 10:
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

