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

    pr_ref_patterns = (
        re.compile(r"\bpr\s*#?\s*(\d+)\b", re.IGNORECASE),
        re.compile(r"\bpull\s+request\s*#?\s*(\d+)\b", re.IGNORECASE),
        re.compile(r"/pull/(\d+)\b", re.IGNORECASE),
    )

    def task_mentions_pr(task: str | None) -> bool:
        return any(
            match and int(match.group(1)) == int(pr_number)
            for pattern in pr_ref_patterns
            for match in [pattern.search(task or "")]
        )

    if "pr_number" in rating_cols:
        for _rating_id, story_id in conn.execute(
            "SELECT id, story_id FROM capability_ratings WHERE pr_number=?", (pr_number,)
        ).fetchall():
            if story_id:
                story_ids.add(story_id)
                rating_story_ids.add(story_id)

    job_metadata: dict[str, tuple[str | None, str | None, str | None]] = {}
    if "job_id" in jobs_cols:
        selected = "job_id, story_id"
        if "task" in jobs_cols:
            selected += ", task"
        if "gh_write_target" in jobs_cols:
            selected += ", gh_write_target"
        for row in conn.execute(f"SELECT {selected} FROM daemon_jobs").fetchall():
            job_id, story_id = row[:2]
            task = row[2] if "task" in jobs_cols else None
            target = row[3 if "task" in jobs_cols else 2] if "gh_write_target" in jobs_cols else None
            job_metadata[job_id] = (story_id, task, target)

    linked_issue_numbers: set[int] = set()
    for story_id in story_ids:
        match = re.search(r"\bstory-issue-(\d+)\b", story_id, re.IGNORECASE)
        if match:
            linked_issue_numbers.add(int(match.group(1)))
    story_cols = _table_columns(conn, "stories")
    if "gh_issue" in story_cols and story_ids:
        placeholders = ",".join("?" for _ in story_ids)
        for (gh_issue,) in conn.execute(
            f"SELECT gh_issue FROM stories WHERE story_id IN ({placeholders})",
            tuple(story_ids),
        ).fetchall():
            match = re.search(r"\d+", str(gh_issue or ""))
            if match:
                linked_issue_numbers.add(int(match.group(0)))

    issue_ref_pattern = re.compile(r"(?<![\w/])#(\d+)\b|\bissue:(\d+)\b", re.IGNORECASE)

    def referenced_issue_numbers(text: str | None) -> set[int]:
        return {
            int(match.group(1) or match.group(2))
            for match in issue_ref_pattern.finditer(text or "")
        }

    def job_attributable(
        story_id: str | None, task: str | None, target: str | None
    ) -> bool:
        own_text = " ".join(value for value in (task, target) if value)
        direct_pr_tie = target == f"pr:{pr_number}" or task_mentions_pr(task)
        direct_issue_tie = bool(referenced_issue_numbers(own_text) & linked_issue_numbers)
        if direct_pr_tie or direct_issue_tie:
            return True
        if story_id not in rating_story_ids:
            return False

        # A shared story is only a fallback attribution.  If the job names any
        # other PR or issue, the job's own provenance wins over the shared story.
        references_other_pr = any(
            match and int(match.group(1)) != int(pr_number)
            for pattern in pr_ref_patterns
            for match in [pattern.search(own_text)]
        )
        references_other_issue = bool(
            referenced_issue_numbers(own_text) - linked_issue_numbers
        )
        return not (references_other_pr or references_other_issue)

    if "job_id" in cost_cols:
        for job_id, cost_story_id in conn.execute(
            "SELECT job_id, story_id FROM cost_entries WHERE job_id IS NOT NULL"
        ).fetchall():
            job_story_id, task, target = job_metadata.get(job_id, (None, None, None))
            story_id = job_story_id or cost_story_id
            if job_attributable(story_id, task, target):
                records[job_id] = {"job_id": job_id, "story_id": story_id}

    return [
        {**record, **linkage}
        for record in records.values()
        if not (linkage := story_governs_linkage(conn, record.get("story_id")))["linked"]
    ]
