"""Workspace-scoped GOVERNS goal resolution and story association."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class GoalResolution:
    goal_id: Optional[str]
    reason: str
    confidence: str = "unresolved"


def workspace_product_id(conn) -> Optional[str]:
    """Return the product identity for the ledger owning *conn*."""
    try:
        row = conn.execute(
            "SELECT product_id FROM state_identity WHERE product_id IS NOT NULL "
            "ORDER BY rowid LIMIT 1"
        ).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None


def _workspace_root(repo_root: Optional[str] = None) -> str:
    return os.path.abspath(repo_root or os.getcwd())


def _config_aliases(repo_root: Optional[str] = None) -> dict[str, list[str]]:
    path = os.path.join(_workspace_root(repo_root), ".synlynk", "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}

    raw = config.get("goal_aliases", config.get("governs", {}).get("goal_aliases", {}))
    result: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for goal_id, patterns in raw.items():
            if isinstance(patterns, str):
                patterns = [patterns]
            if isinstance(patterns, list):
                result[str(goal_id)] = [str(p) for p in patterns if str(p).strip()]
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not item.get("goal_id"):
                continue
            patterns = item.get("patterns", item.get("pattern", []))
            if isinstance(patterns, str):
                patterns = [patterns]
            result.setdefault(str(item["goal_id"]), []).extend(
                str(p) for p in patterns if str(p).strip()
            )
    return result


def scoped_goals(conn, status: str = "active", repo_root: Optional[str] = None) -> list[dict[str, Any]]:
    """Return only goals belonging to this workspace, plus their aliases."""
    product_id = workspace_product_id(conn)
    if product_id is None:
        return []
    rows = conn.execute(
        "SELECT goal_id, product_id, outcome, criterion, deadline, status, kind "
        "FROM goals WHERE status=? AND (product_id=? OR product_id IS NULL) "
        "ORDER BY created_at, goal_id",
        (status, product_id),
    ).fetchall()
    aliases: dict[str, list[str]] = {}
    try:
        for goal_id, pattern in conn.execute(
            "SELECT goal_id, pattern FROM goal_aliases WHERE product_id=?", (product_id,)
        ).fetchall():
            aliases.setdefault(goal_id, []).append(pattern)
    except Exception:
        pass
    for goal_id, patterns in _config_aliases(repo_root).items():
        aliases.setdefault(goal_id, []).extend(patterns)
    columns = ("goal_id", "product_id", "outcome", "criterion", "deadline", "status", "kind")
    return [{**dict(zip(columns, row)), "aliases": aliases.get(row[0], [])} for row in rows]


def _ensure_resolution_columns(conn) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    if "link_status" not in columns:
        conn.execute("ALTER TABLE goal_contributions ADD COLUMN link_status TEXT NOT NULL DEFAULT 'linked'")
    if "skip_reason" not in columns:
        conn.execute("ALTER TABLE goal_contributions ADD COLUMN skip_reason TEXT")
    if "resolution_reason" not in columns:
        conn.execute("ALTER TABLE goal_contributions ADD COLUMN resolution_reason TEXT")
    if "resolved_at" not in columns:
        conn.execute("ALTER TABLE goal_contributions ADD COLUMN resolved_at TIMESTAMP")


def _words(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[a-z0-9][a-z0-9_-]+", text or "", re.I)}


def _alias_match(text: str, goal: dict[str, Any]) -> Optional[int]:
    best = 0
    for pattern in goal.get("aliases", []):
        try:
            matched = re.search(pattern, text, re.I)
        except re.error:
            matched = re.search(re.escape(pattern), text, re.I)
        if matched:
            best = max(best, len(matched.group(0)))
    return best or None


def resolve_goal_for_story(
    conn,
    *,
    title: str = "",
    explicit_goal: Optional[str] = None,
    story_id: Optional[str] = None,
    issue_number: Optional[int | str] = None,
    text_content: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> GoalResolution:
    goals = scoped_goals(conn, repo_root=repo_root)
    by_id = {goal["goal_id"]: goal for goal in goals}
    if explicit_goal:
        goal_id = str(explicit_goal).strip()
        if goal_id not in by_id:
            raise RuntimeError(f"goal {goal_id!r} is outside the current workspace")
        return GoalResolution(goal_id, "explicit_argument", "explicit")

    corpus = "\n".join(filter(None, (title, text_content)))
    from synlynk.governs_resolver import extract_in_band_goal

    header_goal = extract_in_band_goal(corpus)
    if header_goal:
        if header_goal not in by_id:
            raise RuntimeError(f"goal {header_goal!r} is outside the current workspace")
        return GoalResolution(header_goal, "in_band_header", "explicit")

    if story_id:
        row = conn.execute(
            "SELECT goal_id FROM stories WHERE story_id=? AND goal_id IS NOT NULL AND goal_id!=''",
            (story_id,),
        ).fetchone()
        if row and row[0] in by_id:
            return GoalResolution(row[0], "parent_story_link", "inherited")
    if issue_number is not None:
        issue = str(issue_number).lstrip("#")
        row = conn.execute(
            "SELECT goal_id FROM stories WHERE (gh_issue=? OR gh_issue=?) "
            "AND goal_id IS NOT NULL AND goal_id!=''", (issue, f"#{issue}"),
        ).fetchone()
        if row and row[0] in by_id:
            return GoalResolution(row[0], "parent_story_link", "inherited")

    alias_hits = [(match, goal["goal_id"]) for goal in goals if (match := _alias_match(corpus, goal))]
    if alias_hits:
        _, goal_id = max(alias_hits, key=lambda item: (item[0], item[1]))
        return GoalResolution(goal_id, "workspace_alias", "inferred")

    corpus_words = _words(corpus)
    keyword_hits = []
    for goal in goals:
        hits = corpus_words & (_words(goal.get("outcome", "")) | _words(goal.get("criterion", "")))
        if len(hits) >= 2:
            keyword_hits.append((len(hits), goal["goal_id"]))
    if keyword_hits:
        _, goal_id = max(keyword_hits, key=lambda item: (item[0], item[1]))
        return GoalResolution(goal_id, "derived_keyword", "inferred")

    masters = [goal for goal in goals if str(goal.get("kind") or "").lower() == "master"]
    if len(masters) == 1:
        return GoalResolution(masters[0]["goal_id"], "workspace_default", "default")
    return GoalResolution(None, "unresolved", "unresolved")


def associate_story(conn, story_id: str, *, title: str = "", explicit_goal: Optional[str] = None,
                    issue_number: Optional[int | str] = None, text_content: Optional[str] = None,
                    repo_root: Optional[str] = None, emit: bool = True) -> GoalResolution:
    """Resolve and associate a story without committing the caller's transaction."""
    resolution = resolve_goal_for_story(
        conn, title=title, explicit_goal=explicit_goal, story_id=story_id,
        issue_number=issue_number, text_content=text_content, repo_root=repo_root,
    )
    _ensure_resolution_columns(conn)
    timestamp = datetime.now(timezone.utc).isoformat()
    if resolution.goal_id:
        conn.execute("UPDATE stories SET goal_id=? WHERE story_id=?", (resolution.goal_id, story_id))
        conn.execute(
            "INSERT INTO goal_contributions "
            "(goal_id, story_id, link_status, resolution_reason, resolved_at) VALUES (?, ?, 'linked', ?, ?) "
            "ON CONFLICT(goal_id, story_id) DO UPDATE SET link_status='linked', resolution_reason=excluded.resolution_reason, resolved_at=excluded.resolved_at",
            (resolution.goal_id, story_id, resolution.reason, timestamp),
        )
    else:
        conn.execute("UPDATE stories SET goal_id=NULL WHERE story_id=?", (story_id,))
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute(
                "INSERT INTO goal_contributions "
                "(goal_id, story_id, link_status, skip_reason, resolution_reason, resolved_at) "
                "VALUES ('none', ?, 'unresolved', 'no scoped goal matched', ?, ?)",
                (story_id, resolution.reason, timestamp),
            )
        except Exception:
            conn.execute("DELETE FROM goal_contributions WHERE story_id=? AND goal_id='none'", (story_id,))
            conn.execute(
                "INSERT OR REPLACE INTO goal_contributions "
                "(goal_id, story_id, link_status, skip_reason, resolution_reason, resolved_at) "
                "VALUES ('none', ?, 'unresolved', 'no scoped goal matched', ?, ?)",
                (story_id, resolution.reason, timestamp),
            )
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
    if emit:
        try:
            from synlynk.events import emit_event
            emit_event("goal_realigned", {"story_id": story_id, "goal_id": resolution.goal_id})
        except Exception:
            pass
    return resolution
