"""Deterministic GOVERNS Goal and Lifecycle Auto-Resolver.

Resolves parent goal_id and governs_stage for stories, specs, plans, decisions,
and GitHub issues without requiring manual ceremony.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Optional, Tuple

DEFAULT_MASTER_GOAL = "goal-eacab0dc"  # Universal GOVERNS enforcement

_DOMAIN_GOAL_MAP = [
    # (Regex Pattern, Goal ID, Domain Label)
    (
        re.compile(r"(?:viz|vizor|canvas|hud|graphify|board|gantt|tube|logical|architect_map|lod|opportunity_radar|world_view)", re.I),
        "goal-e3840370",
        "vizor_control_plane",
    ),
    (
        re.compile(r"(?:docs[/-]book|manuscript|readership|book[_-]|book)", re.I),
        "goal-0c4e96ff",
        "book_manuscript",
    ),
    (
        re.compile(r"(?:testbed|acceptance|soak|isolated_vm|docker_runner)", re.I),
        "goal-9011307c",
        "qa_testbed",
    ),
    (
        re.compile(r"(?:models?\.json|quota|calibration|model_catalog|burn_rate)", re.I),
        "goal-c75ff209",
        "model_quota_catalog",
    ),
    (
        re.compile(r"(?:jev|deepseek|typesafe|dsh|cordis|strategic_expansion)", re.I),
        "goal-c7113f58",
        "strategic_expansion",
    ),
    (
        re.compile(r"(?:heal|parity|migration_engine|adoption_parity)", re.I),
        "goal-3b45a961",
        "fleet_parity",
    ),
    (
        re.compile(r"(?:unattended_merge|merge_oracle|trust_closure|job_truth)", re.I),
        "goal-d3333441",
        "trust_closure",
    ),
    (
        re.compile(r"(?:sentinel|doctor|platform_health|zombie|reap|stall)", re.I),
        "goal-8f64eff5",
        "platform_health",
    ),
]

_IN_BAND_GOAL_RE = re.compile(
    r"(?:linked|governing|parent|master)?\s*goals?[\s\*\*_:]+[`\*\[\(]*(goal-[a-z0-9-]+)",
    re.I,
)

_ISSUE_NUM_RE = re.compile(r"#(\d+)")
_STORY_ID_RE = re.compile(r"\b(story-[a-z0-9-]+)\b", re.I)


def extract_in_band_goal(text: str) -> Optional[str]:
    """Extract explicit parent goal ID from markdown frontmatter or header text."""
    if not text:
        return None
    for line in text.splitlines()[:50]:
        m = _IN_BAND_GOAL_RE.search(line)
        if m:
            candidate = m.group(1).strip("`*[]() ")
            if candidate.startswith("goal-") or len(candidate) >= 4:
                return candidate
    return None


def resolve_parent_goal(
    file_path: Optional[str] = None,
    story_id: Optional[str] = None,
    issue_number: Optional[int | str] = None,
    branch: Optional[str] = None,
    text_content: Optional[str] = None,
    explicit_goal: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
    repo_root: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve parent goal_id via a deterministic 5-level waterfall.

    Returns:
        tuple[goal_id, reason]
    """
    # Tier 1: Explicit Argument
    if explicit_goal and str(explicit_goal).strip():
        return str(explicit_goal).strip(), "explicit_argument"

    # Read top lines of file_path if provided and text_content is empty
    file_text = ""
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                file_text = "".join(fh.readline() for _ in range(50))
        except Exception:
            pass

    combined_text = (text_content or "") + "\n" + file_text

    # Tier 2: In-Band Header from file or text
    in_band_goal = extract_in_band_goal(combined_text)
    if in_band_goal:
        return in_band_goal, "in_band_header"

    # Tier 3: Parent Story or GitHub Issue Inheritance
    owns_conn = False
    if conn is None:
        try:
            from synlynk import _get_db
            conn = _get_db()
            owns_conn = True
        except Exception:
            conn = None

    try:
        if conn:
            # Check by story_id
            target_story = story_id
            if not target_story and combined_text:
                sm = _STORY_ID_RE.search(combined_text)
                if sm:
                    target_story = sm.group(1)

            if target_story:
                row = conn.execute(
                    "SELECT goal_id FROM stories WHERE story_id = ? AND goal_id IS NOT NULL AND goal_id != ''",
                    (target_story,),
                ).fetchone()
                if row and row[0]:
                    return row[0], "parent_story_link"

            # Check by issue_number
            target_issue = issue_number
            if not target_issue and combined_text:
                im = _ISSUE_NUM_RE.search(combined_text)
                if im:
                    target_issue = im.group(1)

            if target_issue:
                issue_str = str(target_issue).lstrip("#")
                row = conn.execute(
                    "SELECT goal_id FROM stories WHERE (gh_issue = ? OR gh_issue = ?) AND goal_id IS NOT NULL AND goal_id != ''",
                    (issue_str, f"#{issue_str}"),
                ).fetchone()
                if row and row[0]:
                    return row[0], "parent_story_link"
    finally:
        if owns_conn and conn:
            try:
                conn.close()
            except Exception:
                pass

    # Tier 4: Domain, Path & Branch Keyword Heuristics
    search_corpus = " ".join(
        str(x)
        for x in [file_path, branch, text_content, story_id, issue_number]
        if x
    )
    for pattern, goal_id, domain_label in _DOMAIN_GOAL_MAP:
        if pattern.search(search_corpus):
            return goal_id, f"domain_heuristic:{domain_label}"

    # Tier 5: Fallback to Master Loop Goal
    return DEFAULT_MASTER_GOAL, "master_loop_fallback"
