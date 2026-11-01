"""GOVERNS Lifecycle CLI & Fleet Sweep Reconciliation Engine.

Provides the `synlynk governs sweep` command to audit, reconcile, and backfill
100% GOVERNS goal linkages and lifecycle stage progressions across all workspace stories.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import hashlib
import time
from typing import Any, Dict, Optional

from synlynk import _CYAN, _GREEN, _RED, _RESET, _YELLOW
from synlynk.context import harvest_workspace_artifacts
from synlynk.governs_engine import scoped_goals


def cmd_governs_start(
    *,
    outcome: str,
    criterion: str,
    version: str | None = None,
    phase_title: str | None = None,
    deadline: str | None = None,
    role: str = "pm",
    kind: str = "feature",
    unplaced: bool = False,
    placement_reason: str | None = None,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[str, int | None]:
    """Create a GOVERNS goal and its phase as one transaction.

    The default path requires an existing roadmap arc and creates a phase.
    ``unplaced`` is an explicit escape hatch for strategic/speculative work;
    it always requires a reason and creates no phase.
    """
    from synlynk.policy import check_authority

    if not outcome or not criterion:
        raise ValueError("outcome and criterion are required")
    if unplaced:
        if version or phase_title:
            raise ValueError("unplaced goals cannot specify a roadmap phase")
        if not placement_reason:
            raise ValueError("unplaced goals require a reason")
    elif not version or not phase_title:
        raise ValueError("a goal must have a roadmap version and phase title")

    authority = check_authority("goal_create", role=role, repo_path=os.getcwd())
    if not authority.allowed:
        raise RuntimeError(f"Goal creation refused: role {role!r} is not authorized per policy.json.")

    owns_conn = conn is None
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
    goal_id = "goal-" + hashlib.md5(f"{outcome}{time.time()}".encode()).hexdigest()[:8]
    phase_id = None
    try:
        conn.execute("BEGIN")
        if unplaced:
            conn.execute(
                "INSERT INTO goals (goal_id, outcome, criterion, deadline, kind, placement_status, placement_reason) "
                "VALUES (?, ?, ?, ?, ?, 'unplaced', ?)",
                (goal_id, outcome, criterion, deadline, kind, placement_reason),
            )
        else:
            if not conn.execute("SELECT 1 FROM roadmap_arcs WHERE version=?", (version,)).fetchone():
                raise ValueError(f"no roadmap arc with version={version!r}")
            conn.execute(
                "INSERT INTO roadmap_phases (arc_version, phase_title, status, priority, notes) "
                "VALUES (?, ?, 'planned', 'P0', ?)",
                (version, phase_title, f"GOVERNS goal: {goal_id}"),
            )
            phase_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO goals (goal_id, outcome, criterion, deadline, kind, phase_id, placement_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'placed')",
                (goal_id, outcome, criterion, deadline, kind, phase_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()
    return goal_id, phase_id


def cmd_governs_audit(
    *, conn: Optional[sqlite3.Connection] = None, strict: bool = False
) -> dict[str, int | bool]:
    """Read-only audit of goal/phase coverage and orphaned roadmap state."""
    owns_conn = conn is None
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
    try:
        goals = conn.execute(
            "SELECT placement_status, phase_id FROM goals"
        ).fetchall()
        unplaced_goals = sum(1 for status, phase_id in goals if status != "placed" or not phase_id)
        missing_reasons = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE (placement_status!='placed' OR phase_id IS NULL) "
            "AND (placement_reason IS NULL OR TRIM(placement_reason)='')"
        ).fetchone()[0]
        phases_without_story = conn.execute(
            "SELECT COUNT(*) FROM roadmap_phases WHERE story_id IS NULL"
        ).fetchone()[0]
        active_without_goal = conn.execute(
            "SELECT COUNT(*) FROM stories "
            "WHERE status IN ('open','in_progress') "
            "AND (goal_id IS NULL OR TRIM(goal_id)='') "
            "AND (superseded_by IS NULL OR TRIM(superseded_by)='') "
            "AND COALESCE(source_type,'') != 'execution_artifact'"
        ).fetchone()[0]
        active_without_phase = conn.execute(
            "SELECT COUNT(*) FROM stories s LEFT JOIN goals g ON g.goal_id=s.goal_id "
            "WHERE s.status IN ('open','in_progress') "
            "AND (s.superseded_by IS NULL OR TRIM(s.superseded_by)='') "
            "AND COALESCE(s.source_type,'') != 'execution_artifact' "
            "AND (g.phase_id IS NULL OR g.placement_status != 'placed')"
        ).fetchone()[0]
        duplicate_active_issue_stories = conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT gh_issue FROM stories "
            "WHERE status IN ('open','in_progress') "
            "AND gh_issue IS NOT NULL AND TRIM(gh_issue)!='' "
            "AND (superseded_by IS NULL OR TRIM(superseded_by)='') "
            "AND COALESCE(source_type,'') != 'execution_artifact' "
            "GROUP BY gh_issue HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        placed_goals = len(goals) - unplaced_goals
        shadow_state_db = os.path.join(os.getcwd(), ".synlynk", "state.db")
        shadow_state_db_present = os.path.exists(shadow_state_db)
        passed = missing_reasons == 0 and not shadow_state_db_present
        result = {
            "goals": len(goals),
            "placed_goals": placed_goals,
            "unplaced_goals": unplaced_goals,
            "missing_placement_reasons": missing_reasons,
            "phases_without_story": phases_without_story,
            "active_stories_without_goal": active_without_goal,
            "active_stories_without_phase": active_without_phase,
            "duplicate_active_issue_stories": duplicate_active_issue_stories,
            "shadow_state_db_present": shadow_state_db_present,
            "passed": passed and not any((active_without_goal, active_without_phase, duplicate_active_issue_stories)),
        }
        if strict and missing_reasons:
            raise RuntimeError(
                f"GOVERNS audit failed: {missing_reasons} goals lack an explicit placement reason"
            )
        if strict and shadow_state_db_present:
            raise RuntimeError(f"GOVERNS audit failed: shadow state.db exists at {shadow_state_db}")
        if strict and active_without_goal:
            raise RuntimeError(f"GOVERNS audit failed: {active_without_goal} active stories lack a goal")
        if strict and active_without_phase:
            raise RuntimeError(f"GOVERNS audit failed: {active_without_phase} active stories lack a reachable roadmap phase")
        if strict and duplicate_active_issue_stories:
            raise RuntimeError(f"GOVERNS audit failed: {duplicate_active_issue_stories} active issue identities have multiple canonical stories")
        return result
    finally:
        if owns_conn:
            conn.close()


def cmd_governs_reconcile_unplaced(*, role: str = "pm", conn: Optional[sqlite3.Connection] = None) -> int:
    """Annotate legacy unplaced goals without guessing a roadmap phase."""
    from synlynk.policy import check_authority
    authority = check_authority("goal_create", role=role, repo_path=os.getcwd())
    if not authority.allowed:
        raise RuntimeError(f"Goal reconciliation refused: role {role!r} is not authorized per policy.json.")
    owns_conn = conn is None
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT g.goal_id, g.status, COUNT(s.story_id), "
            "SUM(CASE WHEN s.source_type='execution_artifact' THEN 1 ELSE 0 END) "
            "FROM goals g LEFT JOIN stories s ON s.goal_id=g.goal_id "
            "WHERE (g.placement_status!='placed' OR g.phase_id IS NULL) "
            "AND (g.placement_reason IS NULL OR TRIM(g.placement_reason)='') "
            "GROUP BY g.goal_id, g.status"
        ).fetchall()
        conn.execute("BEGIN")
        for goal_id, status, story_count, artifact_count in rows:
            if artifact_count and artifact_count == story_count:
                reason = f"classified execution-artifact lineage ({story_count} linked artifact stories); no roadmap phase inferred"
                classification = "unresolved"
            elif story_count:
                reason = f"classified legacy delivery goal ({story_count} linked stories); phase evidence requires explicit reconciliation"
                classification = "unresolved"
            else:
                reason = "unresolved historical goal with no linked delivery story; requires explicit evidence before placement"
                classification = "unresolved"
            if status in ("done", "superseded"):
                reason = f"classified historical {status} goal; no active roadmap phase inferred"
                classification = "unplaced"
            conn.execute("UPDATE goals SET placement_status=?, placement_reason=? WHERE goal_id=?", (classification, reason, goal_id))
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def cmd_governs_rephase(
    goal_id: str, phase_id: int, reason: str, *, role: str = "pm",
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Move a goal to a phase transactionally and record the audit reason."""
    from synlynk.policy import check_authority
    if not reason or not reason.strip():
        raise ValueError("re-phasing requires an audit reason")
    authority = check_authority("roadmap_edit", role=role, repo_path=os.getcwd())
    if not authority.allowed:
        raise RuntimeError(f"Re-phase refused: role {role!r} is not authorized per policy.json.")
    owns_conn = conn is None
    if conn is None:
        from synlynk import _get_db
        conn = _get_db()
    try:
        goal = conn.execute("SELECT phase_id FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        if not goal:
            raise ValueError(f"unknown goal {goal_id!r}")
        if not conn.execute("SELECT 1 FROM roadmap_phases WHERE id=?", (phase_id,)).fetchone():
            raise ValueError(f"unknown roadmap phase {phase_id!r}")
        conn.execute("BEGIN")
        old_phase_id = goal[0]
        conn.execute(
            "UPDATE goals SET phase_id=?, placement_status='placed', placement_reason=? WHERE goal_id=?",
            (phase_id, f"rephased: {reason.strip()}", goal_id),
        )
        import json
        import time
        conn.execute(
            "INSERT INTO events (event_type, payload_json, created_at, emitted_by, authority_scope) VALUES (?, ?, ?, ?, ?)",
            ("GOVERNS_REPHASE", json.dumps({"goal_id": goal_id, "old_phase_id": old_phase_id, "new_phase_id": phase_id, "reason": reason.strip()}), time.strftime("%Y-%m-%dT%H:%M:%S"), role, "roadmap_edit"),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


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
