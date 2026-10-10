"""Product-scoped Vizor Board read/write operations.

The board is a view over the product graph.  It deliberately contains no
tracker clients: stored pointers are rendered as optional deep links and all
status changes are written to the product ``state.db``.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from synlynk import _get_db
from synlynk.product_store import identity_slug_from_config, repos_path, state_db_path
from synlynk.state_registry import canonical_path

try:
    from synlynk.vizor_daemon import WorkspaceContext
except ImportError:  # pragma: no cover
    WorkspaceContext = Any  # type: ignore[misc,assignment]

BOARD_STATUSES = ("open", "ready", "in_progress", "blocked", "done")
GOVERNS_STAGES = ("goal", "open", "visualize", "execute", "release", "notify", "sustain")
_NWO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _json_object(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _repo_names(slug: str) -> dict[str, str]:
    try:
        payload = json.loads(repos_path(slug).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(row.get("repo_id")): str(row.get("nwo"))
        for row in payload.get("repos", [])
        if isinstance(row, dict) and row.get("repo_id") and row.get("nwo")
    }


def _pointer(story: dict, repo_names: dict[str, str]) -> Optional[dict]:
    pointer = _json_object(story.get("source_ref"))
    if not pointer and story.get("source_type") and story.get("source_ref"):
        pointer = {
            "tracker": story.get("source_type"),
            "id": story.get("source_ref"),
            "container": repo_names.get(str(story.get("repo_id")), ""),
        }
    if not pointer:
        return None
    tracker = str(pointer.get("tracker") or pointer.get("surface") or "").strip().lower()
    container = str(pointer.get("container") or "").strip()
    object_id = str(pointer.get("id") or "").strip()
    if not tracker or not container or not object_id or not _ID_RE.fullmatch(object_id):
        return {"tracker": tracker, "container": container, "id": object_id, "url": None}
    url = None
    if tracker in {"github", "github_issue", "issues"} and _NWO_RE.fullmatch(container):
        url = f"https://github.com/{container}/issues/{quote(object_id, safe='.-_:')}"
    elif tracker == "linear" and re.fullmatch(r"[A-Za-z0-9_.-]+", container):
        url = f"https://linear.app/{container}/issue/{quote(object_id, safe='.-_:')}"
    return {"tracker": tracker, "container": container, "id": object_id, "url": url}


def _open_product_db(
    repo_path: str = ".", *, read_only: bool = False, migrate: bool = True
) -> tuple[sqlite3.Connection, str]:
    slug = identity_slug_from_config(repo_path)
    path = canonical_path(slug, state_db_path(slug))
    if not path.is_file():
        raise FileNotFoundError(f"product state.db not found for identity_slug={slug!r}")
    conn = _get_db(db_path=str(Path(path)), read_only=read_only, migrate=migrate and not read_only)
    conn.row_factory = sqlite3.Row
    return conn, slug


def board_data(
    repo_path: str = ".",
    *,
    repo_id: Optional[str] = None,
    type_id: Optional[str] = None,
    goal_id: Optional[str] = None,
) -> dict:
    """Return product-scoped board cards and deterministic filter options."""
    conn, slug = _open_product_db(repo_path, read_only=True)
    try:
        story_cols = _columns(conn, "stories")
        if not {"story_id", "title", "status"}.issubset(story_cols):
            return {
                "identity_slug": slug,
                "cards": [],
                "filters": {"repos": [], "types": [], "goals": []},
                "statuses": list(BOARD_STATUSES),
                "governs_stages": list(GOVERNS_STAGES),
            }
        selected = ["story_id", "title", "status"]
        for column in ("repo_id", "type_id", "goal_id", "source_type", "source_ref", "gh_issue", "pr_number", "updated_at", "stage", "governs_stage"):
            if column in story_cols:
                selected.append(column)
        rows = conn.execute(f"SELECT {', '.join(selected)} FROM stories ORDER BY created_at, story_id").fetchall()
        repo_names = _repo_names(slug)
        cards = []
        for row in rows:
            item = dict(row)
            item.setdefault("repo_id", None)
            item.setdefault("type_id", None)
            item.setdefault("goal_id", None)
            raw_stage = str(item.get("governs_stage") or item.get("stage") or "open").strip().lower()
            item["governs_stage"] = raw_stage if raw_stage in GOVERNS_STAGES else "open"
            if repo_id and item.get("repo_id") != repo_id:
                continue
            if type_id and item.get("type_id") != type_id:
                continue
            if goal_id and item.get("goal_id") != goal_id:
                continue
            item["repo_name"] = repo_names.get(str(item.get("repo_id")), item.get("repo_id"))
            item["tracker"] = _pointer(item, repo_names)
            item["pr_url"] = None
            if item.get("pr_number") and item.get("repo_id") in repo_names:
                nwo = repo_names[item["repo_id"]]
                if _NWO_RE.fullmatch(nwo):
                    item["pr_url"] = f"https://github.com/{nwo}/pull/{quote(str(item['pr_number']), safe='.-_:')}"
            cards.append(item)
        all_rows = [dict(row) for row in rows]
        filters = {
            "repos": sorted({row.get("repo_id") for row in all_rows if row.get("repo_id")}),
            "types": sorted({row.get("type_id") for row in all_rows if row.get("type_id")}),
            "goals": sorted({row.get("goal_id") for row in all_rows if row.get("goal_id")}),
        }
        return {
            "identity_slug": slug,
            "cards": cards,
            "filters": filters,
            "statuses": list(BOARD_STATUSES),
            "governs_stages": list(GOVERNS_STAGES),
        }
    finally:
        conn.close()


def update_status(story_id: str, status: str, repo_path: str = ".") -> dict:
    """Update one product story status without contacting a tracker."""
    story_id = str(story_id or "").strip()
    status = str(status or "").strip().lower()
    if not story_id:
        raise ValueError("story_id is required")
    if status not in BOARD_STATUSES:
        raise ValueError(f"unknown board status: {status}")
    conn, _slug = _open_product_db(repo_path, migrate=False)
    try:
        story_cols = _columns(conn, "stories")
        if not story_cols:
            raise KeyError(f"story not found: {story_id}")
        row = conn.execute("SELECT story_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
        if row is None:
            raise KeyError(f"story not found: {story_id}")
        updated_at = ", updated_at=CURRENT_TIMESTAMP" if "updated_at" in story_cols else ""
        conn.execute(f"UPDATE stories SET status=?{updated_at} WHERE story_id=?", (status, story_id))
        conn.commit()
        return {"ok": True, "story_id": story_id, "status": status}
    finally:
        conn.close()


def update_stage(story_id: str, stage: str, repo_path: str = ".") -> dict:
    """Update one product story GOVERNS stage without contacting a tracker."""
    story_id = str(story_id or "").strip()
    stage = str(stage or "").strip().lower()
    if not story_id:
        raise ValueError("story_id is required")
    if stage not in GOVERNS_STAGES:
        raise ValueError(f"unknown GOVERNS stage: {stage}")
    conn, _slug = _open_product_db(repo_path, migrate=False)
    try:
        story_cols = _columns(conn, "stories")
        if not story_cols:
            raise KeyError(f"story not found: {story_id}")
        row = conn.execute("SELECT story_id FROM stories WHERE story_id=?", (story_id,)).fetchone()
        if row is None:
            raise KeyError(f"story not found: {story_id}")
        updated_at = ", updated_at=CURRENT_TIMESTAMP" if "updated_at" in story_cols else ""
        updates = []
        params = []
        if "governs_stage" in story_cols:
            updates.append("governs_stage=?")
            params.append(stage)
        if "stage" in story_cols:
            updates.append("stage=?")
            params.append(stage)
        if not updates:
            return {"ok": True, "story_id": story_id, "stage": stage}
        params.append(story_id)
        conn.execute(f"UPDATE stories SET {', '.join(updates)}{updated_at} WHERE story_id=?", params)
        conn.commit()
        return {"ok": True, "story_id": story_id, "stage": stage}
    finally:
        conn.close()


def board_data_for_context(
    ctx: WorkspaceContext,
    *,
    repo_id: Optional[str] = None,
    type_id: Optional[str] = None,
    goal_id: Optional[str] = None,
) -> dict:
    """Return product-scoped board cards using explicit WorkspaceContext."""
    conn = _get_db(db_path=str(ctx.db_path), read_only=True, migrate=False)
    conn.row_factory = sqlite3.Row
    try:
        story_cols = _columns(conn, "stories")
        if not story_cols:
            return {
                "identity_slug": ctx.slug,
                "cards": [],
                "filters": {"repos": [], "types": [], "goals": []},
                "statuses": list(BOARD_STATUSES),
                "governs_stages": list(GOVERNS_STAGES),
            }

        repo_names = _repo_names(ctx.slug)
        has_governs_stage = "governs_stage" in story_cols
        has_goal = "goal_id" in story_cols
        has_repo = "repo_id" in story_cols
        has_type = "type_id" in story_cols

        clauses, params = [], []
        if repo_id and has_repo:
            clauses.append("repo_id = ?")
            params.append(repo_id)
        if type_id and has_type:
            clauses.append("type_id = ?")
            params.append(type_id)
        if goal_id and has_goal:
            clauses.append("goal_id = ?")
            params.append(goal_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM stories {where} ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()

        cards = []
        repos, types, goals = set(), set(), set()
        for r in rows:
            item = dict(r)
            raw_stage = str(item.get("governs_stage") or item.get("stage") or "open").strip().lower()
            stage = raw_stage if raw_stage in GOVERNS_STAGES else "open"
            raw_status = str(item.get("status") or "open").strip().lower()
            status = raw_status if raw_status in BOARD_STATUSES else "open"
            gid = item.get("goal_id")
            rid = item.get("repo_id")
            tid = item.get("type_id")
            if gid:
                goals.add(gid)
            if rid:
                repos.add(rid)
            if tid:
                types.add(tid)

            cards.append({
                "story_id": item.get("story_id"),
                "title": item.get("title"),
                "status": status,
                "stage": stage,
                "governs_stage": stage,
                "goal_id": gid,
                "repo_id": rid,
                "type_id": tid,
                "repo_name": repo_names.get(str(rid or "")),
                "tracker": _pointer(item, repo_names),
                "pr_url": None,
            })

        return {
            "identity_slug": ctx.slug,
            "cards": cards,
            "filters": {
                "repos": sorted(list(repos)),
                "types": sorted(list(types)),
                "goals": sorted(list(goals)),
            },
            "statuses": list(BOARD_STATUSES),
            "governs_stages": list(GOVERNS_STAGES),
        }
    finally:
        conn.close()


def update_stage_for_context(ctx: WorkspaceContext, story_id: str, stage: str) -> bool:
    stage_val = stage.strip().lower()
    if stage_val not in GOVERNS_STAGES:
        raise ValueError(f"invalid stage: {stage!r}")
    conn = _get_db(db_path=str(ctx.db_path), read_only=False, migrate=False)
    try:
        story_cols = _columns(conn, "stories")
        updates = ["stage=?"]
        params = [stage_val]
        if "governs_stage" in story_cols:
            updates.append("governs_stage=?")
            params.append(stage_val)
        params.append(story_id)
        cur = conn.execute(f"UPDATE stories SET {', '.join(updates)} WHERE story_id = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_status_for_context(ctx: WorkspaceContext, story_id: str, status: str) -> bool:
    status_val = status.strip().lower()
    if status_val not in BOARD_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    conn = _get_db(db_path=str(ctx.db_path), read_only=False, migrate=False)
    try:
        cur = conn.execute("UPDATE stories SET status = ? WHERE story_id = ?", (status_val, story_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

