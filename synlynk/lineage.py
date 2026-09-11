"""Multi-Task Lineage Tracking Engine (#1347).

Maintains task lineage relationships across chained, re-dispatched, or split tasks.
Updates SQLite state and active context to track `superseded_by` pointers.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Optional


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    cand1 = os.path.join(os.getcwd(), ".synlynk", "state.db")
    if os.path.exists(cand1):
        return cand1
    cand2 = os.path.join(os.getcwd(), "state.db")
    if os.path.exists(cand2):
        return cand2
    return cand1


def ensure_lineage_schema(conn: sqlite3.Connection) -> None:
    """Ensures superseded_by and lineage_root columns exist in daemon_jobs and stories tables."""
    # Check daemon_jobs
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(daemon_jobs)")}
        if cols:
            if "superseded_by" not in cols:
                conn.execute("ALTER TABLE daemon_jobs ADD COLUMN superseded_by TEXT DEFAULT NULL")
            if "lineage_root" not in cols:
                conn.execute("ALTER TABLE daemon_jobs ADD COLUMN lineage_root TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    # Check jobs (if a jobs table exists)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        if cols:
            if "superseded_by" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN superseded_by TEXT DEFAULT NULL")
            if "lineage_root" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN lineage_root TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    # Check stories
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
        if cols and "superseded_by" not in cols:
            conn.execute("ALTER TABLE stories ADD COLUMN superseded_by TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass


def record_job_superseded(
    old_job_id: str,
    new_job_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Marks old_job_id as superseded by new_job_id in the database."""
    db_file = _resolve_db_path(db_path)
    if not os.path.exists(db_file):
        return False

    try:
        conn = sqlite3.connect(db_file)
        with conn:
            ensure_lineage_schema(conn)

            # Check if old job has an existing lineage_root
            root_row = conn.execute(
                "SELECT lineage_root FROM daemon_jobs WHERE job_id = ?",
                (old_job_id,),
            ).fetchone()
            root_id = (root_row[0] if root_row and root_row[0] else None) or old_job_id

            # Update old job
            conn.execute(
                "UPDATE daemon_jobs SET superseded_by = ?, status = 'superseded' WHERE job_id = ?",
                (new_job_id, old_job_id),
            )

            # Set lineage_root on new job
            conn.execute(
                "UPDATE daemon_jobs SET lineage_root = ? WHERE job_id = ?",
                (root_id, new_job_id),
            )
        conn.close()
        return True
    except Exception:
        return False


def record_story_superseded(
    old_story_id: str,
    new_story_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Marks old_story_id as superseded by new_story_id in the database."""
    db_file = _resolve_db_path(db_path)
    if not os.path.exists(db_file):
        return False

    try:
        conn = sqlite3.connect(db_file)
        with conn:
            ensure_lineage_schema(conn)
            conn.execute(
                "UPDATE stories SET superseded_by = ? WHERE story_id = ?",
                (new_story_id, old_story_id),
            )
        conn.close()
        return True
    except Exception:
        return False


def get_job_lineage(job_id: str, db_path: Optional[str] = None) -> List[Dict[str, Optional[str]]]:
    """Traverses the superseded_by lineage starting from the ancestor root of job_id down to tip."""
    db_file = _resolve_db_path(db_path)
    if not os.path.exists(db_file):
        return []

    try:
        conn = sqlite3.connect(db_file)
        ensure_lineage_schema(conn)

        # 1. Find the root: walk backwards if any job points to job_id as superseded_by
        curr = job_id
        visited_back = set()
        while curr and curr not in visited_back:
            visited_back.add(curr)
            parent = conn.execute(
                "SELECT job_id FROM daemon_jobs WHERE superseded_by = ?",
                (curr,),
            ).fetchone()
            if parent and parent[0]:
                curr = parent[0]
            else:
                break

        root = curr

        # 2. Walk forward from root
        chain: List[Dict[str, Optional[str]]] = []
        curr = root
        visited_forward = set()
        while curr and curr not in visited_forward:
            visited_forward.add(curr)
            row = conn.execute(
                "SELECT job_id, status, superseded_by, lineage_root FROM daemon_jobs WHERE job_id = ?",
                (curr,),
            ).fetchone()
            if not row:
                break
            chain.append({
                "job_id": row[0],
                "status": row[1],
                "superseded_by": row[2],
                "lineage_root": row[3],
            })
            curr = row[2]

        conn.close()
        return chain
    except Exception:
        return []
