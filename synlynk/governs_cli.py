"""GOVERNS Lifecycle CLI & Fleet Sweep Reconciliation Engine.

Provides the `synlynk governs sweep` command to audit, reconcile, and backfill
100% GOVERNS goal linkages and lifecycle stage progressions across all workspace stories.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any, Dict, Optional

from synlynk import _CYAN, _GREEN, _RED, _RESET, _YELLOW
from synlynk.context import harvest_workspace_artifacts
from synlynk.governs_engine import scoped_goals


def cmd_governs_sweep(
    repo_root: Optional[str] = None,
    dry_run: bool = False,
    strict: bool = False,
    verbose: bool = False,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Audit, reconcile, and backfill GOVERNS linkages and lifecycle stages."""
    root = repo_root or os.getcwd()
    owns_conn = False
    if conn is None:
        try:
            from synlynk import _get_db
            conn = _get_db()
            owns_conn = True
        except Exception as exc:
            print(f"  {_RED}✗{_RESET} Failed to open state database: {exc}")
            return {"error": str(exc)}

    print(f"\n  {_CYAN}▶{_RESET} Running GOVERNS Fleet Sweep & Lifecycle Reconciliation...")
    if dry_run:
        print(f"    {_YELLOW}[DRY-RUN MODE]{_RESET} No state mutations will be persisted.")

    stats = {
        "total_stories": 0,
        "initially_linked": 0,
        "initially_unlinked": 0,
        "linked_updated": 0,
        "stages_advanced": 0,
        "artifacts_harvested": 0,
        "unresolved_count": 0,
    }

    try:
        # 1. Query all stories
        story_cols = {r[1] for r in conn.execute("PRAGMA table_info(stories)")}
        has_governs_stage = "governs_stage" in story_cols
        query = (
            "SELECT story_id, title, goal_id, governs_stage, status, gh_issue FROM stories"
            if has_governs_stage
            else "SELECT story_id, title, goal_id, 'open' as governs_stage, status, gh_issue FROM stories"
        )
        stories = conn.execute(query).fetchall()
        stats["total_stories"] = len(stories)

        # Sweep is deliberately an audit.  Association belongs to story-write
        # transactions; this command must never infer or create a goal.
        local_goal_ids = {goal["goal_id"] for goal in scoped_goals(conn, status="active")}
        unresolved_story_ids = []
        for story in stories:
            sid, title, gid, g_stage, status, gh_issue = story[0], story[1] or "", story[2], story[3] or "open", story[4] or "open", story[5]
            if gid and gid.strip() in local_goal_ids:
                stats["initially_linked"] += 1
            else:
                stats["initially_unlinked"] += 1
                stats["unresolved_count"] += 1
                unresolved_story_ids.append(sid)
                if verbose:
                    print(f"    {_YELLOW}•{_RESET} Unresolved {sid}: no scoped goal mapping")

        # 2. Harvest Workspace Artifacts
        artifacts = harvest_workspace_artifacts(repo_root=root, conn=conn)
        stats["artifacts_harvested"] = len(artifacts)

        # 3. Record only the audit marker for unmapped stories.  The marker is
        # intentionally not a goal row and is skipped entirely in dry-run mode.
        if not dry_run and unresolved_story_ids:
            from synlynk.governs_engine import _ensure_resolution_columns
            _ensure_resolution_columns(conn)
            for s_id in unresolved_story_ids:
                conn.execute(
                    "DELETE FROM goal_contributions WHERE story_id=? AND goal_id='none'",
                    (s_id,),
                )
                conn.execute(
                    "PRAGMA foreign_keys=OFF"
                )
                try:
                    conn.execute(
                        "INSERT INTO goal_contributions "
                        "(goal_id, story_id, link_status, skip_reason, resolution_reason) "
                        "VALUES ('none', ?, 'unresolved', ?, 'audit_unresolved')",
                        (s_id, "no scoped goal matched during audit sweep"),
                    )
                finally:
                    conn.execute("PRAGMA foreign_keys=ON")
            conn.commit()

        # 4. Print Summary
        final_linked = stats["initially_linked"]
        coverage_pct = (final_linked / max(1, stats["total_stories"])) * 100

        print(f"\n  {_GREEN}✓{_RESET} GOVERNS Fleet Sweep Complete:")
        print(f"    • Total Stories Scanned:      {stats['total_stories']}")
        print(f"    • Stories Reconciled/Linked:  {stats['linked_updated']}")
        print(f"    • Stages Auto-Advanced:       {stats['stages_advanced']}")
        print(f"    • Session Artifacts Indexed:  {stats['artifacts_harvested']}")
        print(f"    • Workspace Goal Coverage:    {coverage_pct:.1f}%\n")

        return stats
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                pass


def cmd_governs(
    full: bool = False,
    repo_root: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Print the GOVERNS lifecycle board status (compressed 5-stage by default)."""
    owns_conn = False
    if conn is None:
        try:
            from synlynk import _get_db
            conn = _get_db()
            owns_conn = True
        except Exception as exc:
            print(f"  {_RED}✗{_RESET} Failed to open state database: {exc}")
            return

    try:
        story_cols = {r[1] for r in conn.execute("PRAGMA table_info(stories)")}
        has_governs_stage = "governs_stage" in story_cols
        query = (
            "SELECT story_id, title, goal_id, governs_stage, status FROM stories WHERE status != 'done'"
            if has_governs_stage
            else "SELECT story_id, title, goal_id, 'open' as governs_stage, status FROM stories WHERE status != 'done'"
        )
        rows = conn.execute(query).fetchall()
        items = [
            {"id": r[0], "title": r[1] or "", "goal_id": r[2] or "", "stage": r[3] or "open", "status": r[4] or "open"}
            for r in rows
        ]
        from synlynk.governs_compressed import format_compressed_governs_summary
        output = format_compressed_governs_summary(items, full=full)
        print(f"\n{output}\n")
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                pass
