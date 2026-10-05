"""Fail-closed GOVERNS linkage checks for dispatch and PR review."""

from __future__ import annotations

import re
from typing import Any


def _table_columns(conn, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def story_governs_linkage(conn, story_id: str | None) -> dict[str, Any]:
    """Return whether *story_id* has a real GOVERNS goal association."""
    if not story_id:
        return {"linked": False, "story_id": story_id, "goal_id": None, "reason": "missing story_id"}
    try:
        row = conn.execute("SELECT goal_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
    except Exception as exc:
        return {"linked": False, "story_id": story_id, "goal_id": None, "reason": str(exc)}
    if not row:
        return {"linked": False, "story_id": story_id, "goal_id": None, "reason": "story not found"}
    goal_id = row[0]
    if goal_id and goal_id != "none":
        return {"linked": True, "story_id": story_id, "goal_id": goal_id, "reason": None}
    try:
        contribution = conn.execute(
            "SELECT goal_id FROM goal_contributions "
            "WHERE story_id=? AND link_status='linked' AND goal_id IS NOT NULL AND goal_id!='none' LIMIT 1",
            (story_id,),
        ).fetchone()
    except Exception:
        contribution = None
    if contribution:
        return {"linked": True, "story_id": story_id, "goal_id": contribution[0], "reason": None}
    return {"linked": False, "story_id": story_id, "goal_id": None, "reason": "no linked GOVERNS goal"}


def dispatch_governs_linkage(conn, story_id: str | None) -> dict[str, Any]:
    """Preflight contract for a dispatch: a story and goal are mandatory."""
    result = story_governs_linkage(conn, story_id)
    if result["linked"]:
        return {"passed": True, **result}
    return {
        "passed": False,
        "sentinel": "GOVERNS_LINKAGE_MISSING",
        "reason": f"Dispatch requires a linked GOVERNS story/goal ({result['reason']}; story={story_id or 'none'})",
        **result,
    }


def pr_governs_linkage_violations(conn, pr_number: int | None) -> list[dict[str, Any]]:
    """Find dispatched PR jobs that lack a linked GOVERNS story/goal."""
    if pr_number is None:
        return []
    jobs_cols = _table_columns(conn, "daemon_jobs")
    cost_cols = _table_columns(conn, "cost_entries")
    rating_cols = _table_columns(conn, "capability_ratings")
    records: dict[str, dict[str, Any]] = {}
    story_ids: set[str] = set()
    rating_story_ids: set[str] = set()
    job_metadata: dict[str, tuple[str | None, str | None]] = {}

    # Only exact PR references are attributable.  In particular, do not treat
    # an issue target (``issue:123``) or an unrelated ``#123`` mention as work
    # for PR #123; that would leak jobs from neighbouring PRs into this gate.
    pr_ref_patterns = (
        re.compile(r"\bpr\s*#?\s*(\d+)\b", re.IGNORECASE),
        re.compile(r"\bpull\s+request\s*#?\s*(\d+)\b", re.IGNORECASE),
        re.compile(r"/pull/(\d+)\b", re.IGNORECASE),
    )

    def task_mentions_pr(task: str | None) -> bool:
        text = task or ""
        return any(
            match and int(match.group(1)) == int(pr_number)
            for pattern in pr_ref_patterns
            for match in [pattern.search(text)]
        )

    if "pr_number" in rating_cols:
        for _rating_id, story_id in conn.execute(
            "SELECT id, story_id FROM capability_ratings WHERE pr_number=?", (pr_number,)
        ).fetchall():
            story_ids.add(story_id or "")
            rating_story_ids.add(story_id or "")

    if "job_id" in jobs_cols:
        selected = "job_id, story_id"
        if "task" in jobs_cols:
            selected += ", task"
        if "gh_write_target" in jobs_cols:
            selected += ", gh_write_target"
        query = f"SELECT {selected} FROM daemon_jobs"
        rows = conn.execute(query).fetchall()
        for row in rows:
            job_id, story_id = row[:2]
            task = row[2] if "task" in jobs_cols else None
            target = row[3 if "task" in jobs_cols else 2] if "gh_write_target" in jobs_cols else None
            job_metadata[job_id] = (task, target)
            if (
                story_id not in rating_story_ids
                and target != f"pr:{pr_number}"
                and not task_mentions_pr(task)
            ):
                continue
            records[job_id] = {"job_id": job_id, "story_id": story_id}
            story_ids.add(story_id or "")

    if "job_id" in cost_cols:
        for job_id, story_id in conn.execute(
            "SELECT job_id, story_id FROM cost_entries WHERE job_id IS NOT NULL"
        ).fetchall():
            if job_id in records or story_id in rating_story_ids:
                records.setdefault(job_id, {"job_id": job_id, "story_id": story_id})
                if not records[job_id].get("story_id"):
                    records[job_id]["story_id"] = story_id
            elif job_id in job_metadata:
                task, target = job_metadata[job_id]
                if target is None and not task_mentions_pr(task):
                    records[job_id] = {"job_id": job_id, "story_id": story_id}

    return [
        {**record, **linkage}
        for record in records.values()
        if not (linkage := story_governs_linkage(conn, record.get("story_id")))["linked"]
    ]
