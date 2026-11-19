"""Persistent intent capture and semantic association."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

_COMMAND = re.compile(r"^/(?:approve|revise|drop|prioritize|hold)(?:\s|$)", re.I)
_WORDS = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return {word for word in _WORDS.findall(value.lower()) if len(word) > 2}


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intent_captures (
            intent_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            source TEXT NOT NULL,
            context_json TEXT NOT NULL DEFAULT '{}',
            associations_json TEXT NOT NULL DEFAULT '[]',
            resolution TEXT NOT NULL,
            proposal_status TEXT NOT NULL DEFAULT 'pending',
            external_id TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _database_candidates(conn: sqlite3.Connection) -> Iterable[dict[str, str]]:
    definitions = {
        "goals": ("goal", "goal_id", ("outcome", "criterion")),
        "stories": ("story", "story_id", ("title",)),
        "roadmap_phases": ("roadmap_phase", "id", ("phase_title", "notes")),
    }
    for table, (kind, id_col, text_cols) in definitions.items():
        if not _table_exists(conn, table):
            continue
        available = _columns(conn, table)
        selected = [column for column in text_cols if column in available]
        if id_col not in available or not selected:
            continue
        query = f"SELECT {id_col}, {', '.join(selected)} FROM {table}"
        for row in conn.execute(query):
            yield {"kind": kind, "id": str(row[0]), "text": " ".join(str(v or "") for v in row[1:])}


def _graph_candidates(root: Path) -> Iterable[dict[str, str]]:
    doc_path = root / ".synlynk" / "docgraph.json"
    try:
        nodes = json.loads(doc_path.read_text()).get("nodes", {})
        for node_id, node in nodes.items():
            if isinstance(node, dict):
                yield {
                    "kind": "document",
                    "id": str(node_id),
                    "text": " ".join([str(node.get("title", "")), *map(str, node.get("headers", []))]),
                }
    except (OSError, ValueError, TypeError):
        pass

    paths = (
        root / ".synlynk" / "graphify-out" / "graph.json",
        root / ".synlynk" / "graphify-out" / "graphify-out" / "graph.json",
    )
    for graph_path in paths:
        try:
            nodes = json.loads(graph_path.read_text()).get("nodes", [])
        except (OSError, ValueError, TypeError):
            continue
        for node in nodes:
            if isinstance(node, dict) and node.get("id"):
                yield {
                    "kind": "code",
                    "id": str(node["id"]),
                    "text": " ".join(str(node.get(key, "")) for key in ("label", "file", "id")),
                }
        break


def _associate(text: str, conn: sqlite3.Connection, root: Path) -> list[dict[str, Any]]:
    wanted = _tokens(text)
    matches = []
    for candidate in [*_database_candidates(conn), *_graph_candidates(root)]:
        overlap = wanted & _tokens(candidate["text"])
        if overlap:
            score = len(overlap) / max(1, len(wanted))
            matches.append({"kind": candidate["kind"], "id": candidate["id"], "score": round(score, 4)})
    return sorted(matches, key=lambda item: (-item["score"], item["kind"], item["id"]))[:10]


def _row(record: sqlite3.Row | tuple, columns: tuple[str, ...]) -> dict[str, Any]:
    item = dict(zip(columns, record))
    item["context"] = json.loads(item.pop("context_json"))
    item["associations"] = json.loads(item.pop("associations_json"))
    return item


def capture_intent(text, source="terminal", context=None, conn=None):
    """Capture intent and propose association without mutating goals."""
    normalized = str(text or "").strip()
    if not normalized:
        raise ValueError("intent text must not be blank")
    own_conn = conn is None
    if own_conn:
        from synlynk.db import _get_db
        conn = _get_db()
    context = dict(context or {})
    external_id = context.get("external_id")
    try:
        _ensure_schema(conn)
        if external_id:
            existing = conn.execute("SELECT intent_id FROM intent_captures WHERE external_id=?", (external_id,)).fetchone()
            if existing:
                return next(item for item in list_intents(conn) if item["intent_id"] == existing[0])
        root = Path(context.get("repo_path") or ".").resolve()
        associations = _associate(normalized, conn, root)
        resolution = "attach_existing" if any(a["kind"] in {"goal", "story"} for a in associations) else (
            "new_goal_candidate" if associations else "orphan_unclear"
        )
        intent_id = f"intent-{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO intent_captures (intent_id,text,source,context_json,associations_json,resolution,external_id) VALUES (?,?,?,?,?,?,?)",
            (intent_id, normalized, source, json.dumps(context, sort_keys=True), json.dumps(associations), resolution, external_id),
        )
        conn.commit()
        return next(item for item in list_intents(conn) if item["intent_id"] == intent_id)
    finally:
        if own_conn:
            conn.close()


def list_intents(conn=None):
    own_conn = conn is None
    if own_conn:
        from synlynk.db import _get_db
        conn = _get_db()
    try:
        _ensure_schema(conn)
        columns = ("intent_id", "text", "source", "context_json", "associations_json", "resolution", "proposal_status", "external_id", "created_at")
        rows = conn.execute(f"SELECT {', '.join(columns)} FROM intent_captures ORDER BY created_at DESC, rowid DESC").fetchall()
        return [_row(row, columns) for row in rows]
    finally:
        if own_conn:
            conn.close()


def capture_github_intents(events, conn=None):
    own_conn = conn is None
    if own_conn:
        from synlynk.db import _get_db
        conn = _get_db()
    result = {"captured": 0, "skipped": 0, "duplicates": 0}
    try:
        _ensure_schema(conn)
        for event in events:
            text = str(event.get("text") or "").strip()
            if not text or _COMMAND.match(text):
                result["skipped"] += 1
                continue
            external_id = str(event.get("id") or "")
            if external_id and conn.execute("SELECT 1 FROM intent_captures WHERE external_id=?", (external_id,)).fetchone():
                result["duplicates"] += 1
                continue
            capture_intent(text, source="github", context={**event, "external_id": external_id}, conn=conn)
            result["captured"] += 1
        return result
    finally:
        if own_conn:
            conn.close()
