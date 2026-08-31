"""GOVERNS Backlog Automation — Auto-associate discovered and planned work.

See docs/superpowers/specs/2026-08-31-governs-backlog-automation-design.md.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import time
from typing import Optional


def compute_fingerprint(title: str, source_ref: str = "") -> str:
    """Compute a deterministic SHA-256 fingerprint for a discovered item."""
    normalized_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    norm_source = (source_ref or "").strip().lower()
    payload = f"{normalized_title}:{norm_source}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _get_connection(db_conn=None):
    if db_conn is not None:
        if isinstance(db_conn, sqlite3.Connection):
            return db_conn
        if callable(db_conn):
            try:
                return db_conn()
            except TypeError:
                return db_conn
        return db_conn
    from synlynk import _get_db
    return _get_db()


def _query_github_open_issues() -> list[dict]:
    """Query open GitHub issues for deduplication."""
    try:
        res = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "100", "--json", "number,title,labels"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(res.stdout.strip() or "[]")
    except Exception:
        return []


def _check_github_duplicate(title: str, gh_issues: Optional[list[dict]] = None) -> Optional[int]:
    """Check if an open GitHub issue with matching normalized title already exists."""
    if not title:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    issues = gh_issues if gh_issues is not None else _query_github_open_issues()
    for iss in issues:
        iss_title = iss.get("title", "")
        norm_iss = re.sub(r"[^a-z0-9]+", " ", iss_title.lower()).strip()
        if norm_iss == normalized:
            return iss.get("number")
    return None


def check_duplicate(title: str, fingerprint: str = None, db_conn=None, check_gh: bool = False) -> bool:
    """Check whether a work item with this title or fingerprint already exists in state.db or GitHub."""
    conn = _get_connection(db_conn)
    fp = fingerprint or compute_fingerprint(title)
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT 1 FROM stories WHERE fingerprint = ? LIMIT 1", (fp,)
            ).fetchone()
            if row:
                return True

            normalized_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
            rows = conn.execute("SELECT title FROM stories WHERE title IS NOT NULL").fetchall()
            for (existing_title,) in rows:
                if re.sub(r"[^a-z0-9]+", " ", (existing_title or "").lower()).strip() == normalized_title:
                    return True
        except Exception:
            pass

    if check_gh:
        if _check_github_duplicate(title) is not None:
            return True

    return False


def _create_github_issue(
    title: str,
    description: str,
    stage: str = "open",
    role: str = "dev",
    source_type: str = "manual",
    parent_issue: Optional[int] = None,
) -> Optional[int]:
    """Create a GitHub issue with GOVERNS labels and optional parent association."""
    labels = [f"governs:{stage}", f"role:{role}"]
    if source_type in ("doctor", "sentinel"):
        labels.append("tech-debt")

    body = description or title
    if parent_issue:
        body = f"Part of #{parent_issue}.\n\n{body}"

    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
    ]
    for label in labels:
        cmd.extend(["--label", label])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        match = re.search(r"/issues/(\d+)", out)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def stage_discovered_work(
    title: str,
    description: str = "",
    role: str = "dev",
    stage: str = "open",
    source_type: str = "manual",
    source_ref: str = "",
    priority: int = 5,
    db_conn=None,
    sync_gh: bool = False,
    parent_issue: Optional[int] = None,
) -> dict:
    """Stage a newly discovered work item into state.db stories table with deduplication."""
    if not title or not title.strip():
        return {"staged": False, "reason": "empty_title"}

    title = title.strip()
    conn = _get_connection(db_conn)
    fp = compute_fingerprint(title, source_ref)

    if check_duplicate(title, fingerprint=fp, db_conn=conn):
        return {"staged": False, "reason": "duplicate", "fingerprint": fp, "title": title}

    story_seed = f"{title}:{time.time()}"
    story_id = f"story-{hashlib.md5(story_seed.encode()).hexdigest()[:8]}"

    gh_issue_num = None
    if sync_gh:
        gh_issue_num = _create_github_issue(
            title=title,
            description=description,
            stage=stage,
            role=role,
            source_type=source_type,
            parent_issue=parent_issue,
        )

    if conn is not None:
        try:
            conn.execute(
                """INSERT INTO stories (
                    story_id, title, role, stage, governs_stage, status,
                    priority, fingerprint, source_type, source_ref, gh_issue
                ) VALUES (?, ?, ?, ?, ?, 'discovered', ?, ?, ?, ?, ?)""",
                (
                    story_id,
                    title,
                    role,
                    stage,
                    stage,
                    priority,
                    fp,
                    source_type,
                    source_ref,
                    str(gh_issue_num) if gh_issue_num else None,
                ),
            )
            conn.commit()
        except Exception as exc:
            return {"staged": False, "reason": str(exc), "fingerprint": fp}

    return {
        "staged": True,
        "story_id": story_id,
        "fingerprint": fp,
        "title": title,
        "role": role,
        "stage": stage,
        "source_type": source_type,
        "source_ref": source_ref,
        "gh_issue": gh_issue_num,
    }


def list_staged_backlog(
    db_conn=None,
    stage: Optional[str] = None,
    unfiled_only: bool = False,
) -> list[dict]:
    """Retrieve staged and discovered work items from state.db."""
    conn = _get_connection(db_conn)
    if conn is None:
        return []

    query = """
        SELECT story_id, title, role, governs_stage, status, priority,
               fingerprint, source_type, source_ref, gh_issue, created_at
        FROM stories
        WHERE (status = 'discovered' OR status = 'open')
    """
    params = []
    if stage:
        query += " AND governs_stage = ?"
        params.append(stage)
    if unfiled_only:
        query += " AND (gh_issue IS NULL OR gh_issue = '')"

    query += " ORDER BY id DESC"

    try:
        rows = conn.execute(query, tuple(params)).fetchall()
        results = []
        for r in rows:
            results.append({
                "story_id": r[0],
                "title": r[1],
                "role": r[2],
                "stage": r[3] or "open",
                "status": r[4],
                "priority": r[5],
                "fingerprint": r[6],
                "source_type": r[7],
                "source_ref": r[8],
                "gh_issue": r[9],
                "created_at": r[10],
            })
        return results
    except Exception:
        return []


def sync_backlog_to_github(
    db_conn=None,
    dry_run: bool = False,
    parent_issue: Optional[int] = None,
    stage: Optional[str] = None,
) -> list[dict]:
    """Synchronize unfiled staged backlog stories to GitHub issues."""
    conn = _get_connection(db_conn)
    unfiled = list_staged_backlog(db_conn=conn, stage=stage, unfiled_only=True)
    synced = []
    gh_issues_cache = _query_github_open_issues()

    for item in unfiled:
        if dry_run:
            synced.append({**item, "action": "dry_run_sync"})
            continue

        existing_issue_num = _check_github_duplicate(item["title"], gh_issues=gh_issues_cache)
        if existing_issue_num:
            if conn is not None:
                try:
                    conn.execute(
                        "UPDATE stories SET gh_issue = ? WHERE story_id = ?",
                        (str(existing_issue_num), item["story_id"]),
                    )
                    conn.commit()
                except Exception:
                    pass
            synced.append({**item, "gh_issue": existing_issue_num, "action": "linked_existing_issue"})
            continue

        issue_num = _create_github_issue(
            title=item["title"],
            description=f"Auto-created from discovered work ({item.get('source_type', 'manual')}: {item.get('source_ref', '')}).",
            stage=item["stage"],
            role=item["role"],
            source_type=item["source_type"],
            parent_issue=parent_issue,
        )
        if issue_num and conn is not None:
            try:
                conn.execute(
                    "UPDATE stories SET gh_issue = ? WHERE story_id = ?",
                    (str(issue_num), item["story_id"]),
                )
                conn.commit()
                synced.append({**item, "gh_issue": issue_num, "action": "created_issue"})
            except Exception:
                pass
        else:
            synced.append({**item, "action": "sync_failed"})

    return synced
