"""Detect drift between decisions, goals, and roadmap arcs (gh:#5020-adjacent)."""

from __future__ import annotations

import itertools
import os
import re
from typing import Any

# Matches a goal_id token regardless of markdown wrapping (backticks, link
# brackets): goal-xxxxxxxx, arc-goal-XXXXXXXX, or phase-goal-XXXXXXXX.
_GOAL_ID_TOKEN_RE = re.compile(r"(?:arc-goal|phase-goal|goal)-[0-9a-fA-F]{6,8}")
_GOVERNING_GOAL_LINE_RE = re.compile(r"Governing Goals?:", re.IGNORECASE)

# Header fields are always near the top of a spec/plan; avoid false positives
# from goal_id tokens appearing deep in prose or examples later in the file.
_HEADER_SCAN_LINES = 40


def find_spec_goal_drift(
    conn, repo_root: str = ".", search_dirs: list[str] | None = None
) -> list[dict[str, Any]]:
    """Flag a spec/plan's 'Governing Goal(s):' header naming a goal_id that
    doesn't exist in goals — a stale reference left behind when a goal was
    renamed, consolidated, or never actually created (see gh:#5373, where a
    spec's header named goal-d5323df6 and that id was never inserted into
    goals at all).

    One finding kind: SPEC_GOVERNING_GOAL_MISSING.
    """
    findings: list[dict[str, Any]] = []

    try:
        has_goals = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name='goals'"
        ).fetchone()
        if not has_goals:
            return []
        count = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        if count == 0:
            return []
    except Exception:
        return []

    dirs = search_dirs or [
        os.path.join(repo_root, "docs", "superpowers", "specs"),
        os.path.join(repo_root, "docs", "superpowers", "plans"),
    ]
    for sdir in dirs:
        if not os.path.isdir(sdir):
            continue
        for fname in sorted(os.listdir(sdir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(sdir, fname)
            rel_path = os.path.relpath(fpath, repo_root)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    header_lines = list(itertools.islice(f, _HEADER_SCAN_LINES))
            except Exception:
                continue

            for line in header_lines:
                if not _GOVERNING_GOAL_LINE_RE.search(line):
                    continue
                # Strip parenthetical asides first: a header line may
                # mention a prior/stale goal_id in explanatory prose (e.g.
                # "corrected from a stale `goal-xxx` reference"), which is
                # not itself a claim that goal_id governs this doc.
                stripped = re.sub(r"\([^)]*\)", "", line)
                for goal_id in _GOAL_ID_TOKEN_RE.findall(stripped):
                    row = conn.execute(
                        "SELECT 1 FROM goals WHERE goal_id=?", (goal_id,)
                    ).fetchone()
                    if row is None:
                        findings.append(
                            {
                                "kind": "SPEC_GOVERNING_GOAL_MISSING",
                                "path": rel_path,
                                "goal_id": goal_id,
                                "detail": (
                                    f"{rel_path} names Governing Goal {goal_id}, which "
                                    f"does not exist in goals (stale/renamed/never-created "
                                    f"reference)"
                                ),
                            }
                        )

    return findings


def find_roadmap_drift(conn) -> list[dict[str, Any]]:
    """Return a list of drift findings across decisions/goals/roadmap_arcs.

    Three finding kinds:
    - DECISION_GOAL_UNPLACED: an approved decision links a goal whose
      placement_status is not 'placed' (the goal was never actually put
      on the roadmap)
    - ARC_NO_DECISION: a roadmap arc claims a goal_id with no backing
      approved decision (the arc's authority is unverifiable)
    - DECISION_GOAL_MISSING: a decision's goal_id does not resolve in
      goals at all. The decisions.goal_id foreign key normally prevents
      this, but it is checked defensively in case FK enforcement was
      bypassed for a sentinel write (see synlynk/db.py's
      _record_goal_link_status).
    - SPEC_GOVERNING_GOAL_MISSING: a committed spec/plan's 'Governing
      Goal(s):' header names a goal_id that doesn't exist in goals (see
      find_spec_goal_drift; gh:#5373). Scanned relative to the current
      working directory, so this finding is silently skipped (not
      reported as an error) when run outside a repo checkout.
    """
    findings: list[dict[str, Any]] = []

    try:
        has_goals = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name='goals'"
        ).fetchone()
        if not has_goals:
            return []
        count = conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        if count == 0:
            return []
    except Exception:
        return []

    unplaced_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id, g.placement_status "
        "FROM decisions d JOIN goals g ON g.goal_id = d.goal_id "
        "WHERE d.goal_id IS NOT NULL AND g.placement_status != 'placed'"
    ).fetchall()
    for decision_id, goal_id, placement_status in unplaced_rows:
        findings.append(
            {
                "kind": "DECISION_GOAL_UNPLACED",
                "decision_id": decision_id,
                "goal_id": goal_id,
                "detail": (
                    f"decision {decision_id} links goal {goal_id}, but that goal's "
                    f"placement_status is {placement_status!r} (not 'placed')"
                ),
            }
        )

    no_decision_rows = conn.execute(
        "SELECT ra.version, ra.goal_id FROM roadmap_arcs ra "
        "WHERE ra.goal_id IS NOT NULL "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM decisions d WHERE d.goal_id = ra.goal_id AND d.status = 'approved'"
        ")"
    ).fetchall()
    for arc_version, goal_id in no_decision_rows:
        findings.append(
            {
                "kind": "ARC_NO_DECISION",
                "arc_version": arc_version,
                "goal_id": goal_id,
                "detail": (
                    f"roadmap arc {arc_version} claims goal {goal_id}, but no approved "
                    f"decision links that goal"
                ),
            }
        )

    missing_rows = conn.execute(
        "SELECT d.decision_id, d.goal_id FROM decisions d "
        "WHERE d.goal_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM goals g WHERE g.goal_id = d.goal_id)"
    ).fetchall()
    for decision_id, goal_id in missing_rows:
        findings.append(
            {
                "kind": "DECISION_GOAL_MISSING",
                "decision_id": decision_id,
                "goal_id": goal_id,
                "detail": (
                    f"decision {decision_id} references goal_id {goal_id}, which does "
                    f"not exist in goals"
                ),
            }
        )

    try:
        findings.extend(find_spec_goal_drift(conn))
    except Exception:
        pass

    return findings


def classify_roadmap_drift(
    findings: list[dict[str, Any]],
) -> tuple[str, str]:
    """Mirror policy_gates.classify_governs_violations's status/detail shape."""
    if not findings:
        return "pass", "no roadmap drift detected"
    summary = "; ".join(f["detail"] for f in findings)
    return "warn", summary
