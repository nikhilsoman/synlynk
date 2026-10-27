"""Report graph symbols nothing else calls. Story filing does not edit todo.md."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from synlynk.graph_cache import write_traversal_cache

_SYMBOL_KINDS = {"function", "class", "method"}


def _get_db():
    from synlynk import _get_db as open_db
    return open_db()


def find_orphan_symbols(repo_root: str) -> list[dict[str, Any]]:
    """Functions and classes with in-degree 0, outside entrypoints, tests, and dunders."""
    graph_path = os.path.join(repo_root, ".synlynk", "graphify-out", "graph.json")
    if not os.path.isfile(graph_path):
        return []
    try:
        with open(graph_path, encoding="utf-8") as handle:
            graph = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    nodes = [node for node in (graph.get("nodes") or []) if isinstance(node, dict)]
    edges = [edge for edge in (graph.get("edges") or []) if isinstance(edge, dict)]
    if not nodes:
        return []

    cache_path = os.path.join(repo_root, ".synlynk", "graph-cache", "traversals.json")
    if not os.path.isfile(cache_path):
        write_traversal_cache(repo_root)
    excluded = _entrypoint_ids(cache_path)
    indegree: dict[str, int] = {}
    for edge in edges:
        target = str(edge.get("target") or "")
        if target:
            indegree[target] = indegree.get(target, 0) + 1

    orphans = []
    for node in nodes:
        kind = str(node.get("kind") or "")
        if kind not in _SYMBOL_KINDS:
            continue
        node_id = str(node.get("id") or "")
        label = str(node.get("label") or "")
        file_path = str(node.get("file") or "").replace("\\", "/")
        if not node_id or not label:
            continue
        if indegree.get(node_id, 0) != 0:
            continue
        if node_id in excluded:
            continue
        if label.startswith("__") and label.endswith("__"):
            continue
        if file_path.startswith("tests/test_") and file_path.endswith(".py"):
            continue
        orphans.append({
            "id": node_id,
            "label": label,
            "file": file_path,
            "kind": kind,
        })
    return orphans


def _entrypoint_ids(cache_path: str) -> set[str]:
    if not os.path.isfile(cache_path):
        return set()
    try:
        with open(cache_path, encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return set()
    found = set()
    for path in cache.get("paths") or []:
        if not isinstance(path, dict) or path.get("kind") != "entrypoint":
            continue
        for node in path.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                found.add(str(node.get("id")))
    return found


def create_orphan_stories(orphans: list[dict[str, Any]]) -> list[str]:
    """Insert stories directly. Do not call story create or regenerate todo.md."""
    if not orphans:
        return []
    conn = _get_db()
    created = []
    for orphan in orphans:
        story_id = f"story-orphan-{uuid.uuid4().hex[:8]}"
        title = f"Orphan symbol {orphan['label']}"
        description = (
            f"{orphan['kind']} `{orphan['label']}` in `{orphan['file']}` "
            f"has in-degree 0 and is outside entrypoint chains."
        )
        criteria = f"- Decide whether `{orphan['label']}` stays, or remove the dead symbol."
        conn.execute(
            "INSERT INTO stories (story_id, title, description, criteria, status, priority) "
            "VALUES (?, ?, ?, ?, 'ready', 'p2')",
            (story_id, title, description, criteria),
        )
        created.append(story_id)
    conn.commit()
    return created


def cmd_heal_orphans(args) -> int:
    repo_root = getattr(args, "repo_root", ".") or "."
    orphans = find_orphan_symbols(repo_root)
    if not orphans:
        print("No orphan symbols.")
        return 0
    print(f"Orphan symbols: {len(orphans)}")
    for orphan in orphans:
        print(f"  {orphan['kind']} {orphan['label']} [{orphan['file']}]")
    if getattr(args, "stories", False):
        created = create_orphan_stories(orphans)
        for story_id in created:
            print(f"  story {story_id}")
    return 0
