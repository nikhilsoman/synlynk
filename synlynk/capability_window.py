"""Dynamic 1% Attribution and Multi-Model Window Engine for Synlynk.

Calculates empirical SFIA task volume distribution, filters active disciplines meeting
the dynamic >= 1% attribution threshold, and tracks active vs. deprecated models across
commercial frontiers and local harnesses within a sliding window (default 30 days).
"""

from __future__ import annotations

import datetime
import sqlite3
from typing import Any

from synlynk.sfia import (
    SFIA_TAXONOMY,
    classify_task_sfia,
    get_sfia_domain,
    get_sfia_name,
)


def calculate_sfia_volume_distribution(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Analyze all completed/done tasks in state.db and calculate SFIA discipline volume.

    Returns:
        dict[str, dict]: Mapping of SFIA code -> {count, percentage, name, domain}
    """
    tasks: list[str] = []

    # Check daemon_jobs first
    try:
        rows = conn.execute(
            "SELECT task FROM daemon_jobs WHERE status IN ('done', 'completed', 'completed_without_changes', 'succeeded_gh_write_failed')"
        ).fetchall()
        for r in rows:
            if r[0]:
                tasks.append(str(r[0]))
    except sqlite3.OperationalError:
        pass

    # If daemon_jobs is empty, check stories
    if not tasks:
        try:
            rows = conn.execute("SELECT title FROM stories WHERE title IS NOT NULL").fetchall()
            for r in rows:
                if r[0]:
                    tasks.append(str(r[0]))
        except sqlite3.OperationalError:
            pass

    counts: dict[str, int] = {code: 0 for code in SFIA_TAXONOMY}
    total_tasks = len(tasks)

    for task_text in tasks:
        code, _, _ = classify_task_sfia(task_text)
        counts[code] = counts.get(code, 0) + 1

    distribution: dict[str, dict[str, Any]] = {}
    for code, count in counts.items():
        percentage = round(count / total_tasks, 4) if total_tasks > 0 else 0.0
        distribution[code] = {
            "code": code,
            "count": count,
            "percentage": percentage,
            "name": get_sfia_name(code),
            "domain": get_sfia_domain(code),
            "total_evaluated_tasks": total_tasks,
        }

    return distribution


def get_active_sfia_disciplines(conn: sqlite3.Connection, threshold: float = 0.01) -> list[str]:
    """Return SFIA discipline codes accounting for >= threshold (default 1%) of task volume.

    Args:
        conn: SQLite database connection.
        threshold: Minimum fraction of volume required for active reporting (0.01 = 1%).

    Returns:
        list[str]: Sorted list of qualifying SFIA codes.
    """
    distribution = calculate_sfia_volume_distribution(conn)
    active = [
        code for code, data in distribution.items()
        if data["percentage"] >= threshold and data["count"] > 0
    ]
    return sorted(active)


def sync_harness_models_window(
    conn: sqlite3.Connection,
    lookback_days: int = 30,
) -> list[dict[str, Any]]:
    """Update harness_models sliding window status based on recent execution activity.

    - Models with activity within lookback_days are marked 'active'.
    - Models with no activity within lookback_days are marked 'deprecated'.
    - New models observed in cost_entries or daemon_jobs are automatically registered.

    Returns:
        list[dict]: List of updated model records.
    """
    # 1. Discover models from cost_entries
    try:
        cost_rows = conn.execute("""
            SELECT agent, model, MIN(recorded_at), MAX(recorded_at)
            FROM cost_entries
            WHERE agent IS NOT NULL AND model IS NOT NULL AND model != ''
            GROUP BY agent, model
        """).fetchall()
    except sqlite3.OperationalError:
        cost_rows = []

    # 2. Discover models from daemon_jobs
    try:
        job_rows = conn.execute("""
            SELECT agent, resolved_model, MIN(completed_at), MAX(completed_at)
            FROM daemon_jobs
            WHERE agent IS NOT NULL AND resolved_model IS NOT NULL AND resolved_model != ''
            GROUP BY agent, resolved_model
        """).fetchall()
    except sqlite3.OperationalError:
        job_rows = []

    observed: dict[tuple[str, str], tuple[str, str]] = {}
    for agent, model, first_seen, last_seen in cost_rows + job_rows:
        key = (str(agent).strip(), str(model).strip())
        fs = str(first_seen or datetime.datetime.now(datetime.timezone.utc).isoformat())
        ls = str(last_seen or fs)
        if key not in observed:
            observed[key] = (fs, ls)
        else:
            old_fs, old_ls = observed[key]
            observed[key] = (min(old_fs, fs), max(old_ls, ls))

    # Insert newly observed models into harness_models
    for (harness, model), (first_seen, last_seen) in observed.items():
        try:
            conn.execute("""
                INSERT INTO harness_models (
                    harness_name, model_id, first_seen_at, last_seen_at, status, discovery_source
                ) VALUES (?, ?, ?, ?, 'active', 'execution_log')
                ON CONFLICT(harness_name, model_id, provider) DO UPDATE SET
                    last_seen_at = MAX(harness_models.last_seen_at, excluded.last_seen_at)
            """, (harness, model, first_seen, last_seen))
        except sqlite3.OperationalError:
            pass

    # Update statuses based on lookback_days
    # SQLite datetime calculation
    conn.execute(
        f"UPDATE harness_models SET status = 'active' "
        f"WHERE last_seen_at >= datetime('now', '-{int(lookback_days)} days')"
    )
    conn.execute(
        f"UPDATE harness_models SET status = 'deprecated' "
        f"WHERE last_seen_at < datetime('now', '-{int(lookback_days)} days')"
    )
    conn.commit()

    rows = conn.execute("""
        SELECT harness_name, model_id, first_seen_at, last_seen_at, status
        FROM harness_models
        ORDER BY harness_name, model_id
    """).fetchall()

    return [
        {
            "harness_name": r[0],
            "model_id": r[1],
            "first_seen_at": r[2],
            "last_seen_at": r[3],
            "status": r[4],
        }
        for r in rows
    ]
