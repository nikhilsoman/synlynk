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
from synlynk.governs_resolver import DEFAULT_MASTER_GOAL, resolve_parent_goal


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

        story_updates = []
        for story in stories:
            sid, title, gid, g_stage, status, gh_issue = story[0], story[1] or "", story[2], story[3] or "open", story[4] or "open", story[5]
            if gid and gid.strip():
                stats["initially_linked"] += 1
                resolved_gid = gid
            else:
                stats["initially_unlinked"] += 1
                resolved_gid, reason = resolve_parent_goal(
                    story_id=sid,
                    text_content=title,
                    issue_number=gh_issue,
                    conn=conn,
                )
                if resolved_gid:
                    stats["linked_updated"] += 1
                    if verbose:
                        print(f"    {_GREEN}✓{_RESET} Linked {sid} -> {resolved_gid} ({reason})")
                else:
                    stats["unresolved_count"] += 1

            # Check stage advancement for completed work
            new_stage = g_stage
            if status == "done" and g_stage in ("open", "visualize", "execute"):
                new_stage = "sustain"
                stats["stages_advanced"] += 1
            elif not g_stage or g_stage == "":
                new_stage = "open"

            if resolved_gid != gid or new_stage != g_stage:
                story_updates.append((resolved_gid, new_stage, sid))

        # 2. Harvest Workspace Artifacts
        artifacts = harvest_workspace_artifacts(repo_root=root, conn=conn)
        stats["artifacts_harvested"] = len(artifacts)

        # 3. Apply updates if not dry run
        if not dry_run and story_updates:
            for r_gid, n_stage, s_id in story_updates:
                if r_gid:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO goals (goal_id, outcome, criterion) VALUES (?, ?, ?)",
                            (r_gid, f"GOVERNS Goal: {r_gid}", "Auto-reconciled during GOVERNS sweep"),
                        )
                    except Exception:
                        pass
                if has_governs_stage:
                    conn.execute(
                        "UPDATE stories SET goal_id = ?, governs_stage = ?, stage = ? WHERE story_id = ?",
                        (r_gid, n_stage, n_stage, s_id),
                    )
                else:
                    conn.execute(
                        "UPDATE stories SET goal_id = ? WHERE story_id = ?",
                        (r_gid, s_id),
                    )
            conn.commit()

        # 4. Print Summary
        final_linked = stats["initially_linked"] + (stats["linked_updated"] if not dry_run else 0)
        coverage_pct = (final_linked / max(1, stats["total_stories"])) * 100

        print(f"\n  {_GREEN}✓{_RESET} GOVERNS Fleet Sweep Complete:")
        print(f"    • Total Stories Scanned:      {stats['total_stories']}")
        print(f"    • Stories Reconciled/Linked:  {stats['linked_updated']}")
        print(f"    • Stages Auto-Advanced:       {stats['stages_advanced']}")
        print(f"    • Session Artifacts Indexed:  {stats['artifacts_harvested']}")
        print(f"    • Workspace Goal Coverage:    {coverage_pct:.1f}%\n")

        if strict and stats["unresolved_count"] > 0:
            raise RuntimeError(f"GOVERNS strict sweep failed: {stats['unresolved_count']} unlinked stories remain.")

        return stats
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                pass
