"""Slim community slice for the Logical view expand fetch.

First paint stays a projection. This module is the detail-on-expand read:
ids, labels, kinds, source files, and integer edge indexes. It never returns
attrs_json or the rest of the graph row.
"""
import json
import os
import sqlite3

NODE_CAP = 500
EDGE_CAP = 1000


def node_community(node: dict):
    """Community id from a logical node, including attrs_json when that is the only copy."""
    if not isinstance(node, dict):
        return None
    if node.get("community") is not None:
        return node.get("community")
    return _parsed_attrs(node).get("community")


def node_source_file(node: dict) -> str:
    if not isinstance(node, dict):
        return ""
    for key in ("source_file", "source_path", "file", "path"):
        value = node.get(key)
        if value:
            return str(value)
    attrs = _parsed_attrs(node)
    for key in ("source_file", "source_path", "file", "path"):
        value = attrs.get(key)
        if value:
            return str(value)
    return ""


def logical_community_payload(nodes, edges, community: str) -> dict:
    """Return {nodes, edges, community, truncated?} for one community id."""
    query = str(community)
    matched = [node for node in (nodes or []) if _same_community(node_community(node), query)]
    node_truncated = len(matched) > NODE_CAP
    index = {}
    slim_nodes = []
    for node in matched[:NODE_CAP]:
        node_id = node.get("id")
        if node_id is None or str(node_id) in index:
            continue
        index[str(node_id)] = len(slim_nodes)
        slim_nodes.append({
            "id": node_id,
            "label": node.get("label"),
            "kind": node.get("kind"),
            "source_file": node_source_file(node),
            "community": node_community(node),
        })

    slim_edges = []
    eligible = 0
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        src, dst = _edge_ends(edge)
        if src is None or dst is None:
            continue
        src_i = index.get(str(src))
        dst_i = index.get(str(dst))
        if src_i is None or dst_i is None:
            continue
        eligible += 1
        if len(slim_edges) >= EDGE_CAP:
            continue
        item = {"from": src_i, "to": dst_i}
        kind = edge.get("kind")
        if kind is None:
            kind = edge.get("type")
        if kind:
            item["kind"] = kind
        slim_edges.append(item)

    payload = {
        "nodes": slim_nodes,
        "edges": slim_edges,
        "community": query,
    }
    if node_truncated or eligible > EDGE_CAP:
        payload["truncated"] = True
    return payload


def load_logical_graph(repo_path, db_path=None):
    """Load logical nodes and edges from graph.json, then the projection tables."""
    nodes, edges = _load_graph_json(repo_path)
    if nodes:
        return nodes, edges
    return _load_sqlite(db_path)


def _parsed_attrs(node: dict) -> dict:
    raw = node.get("attrs_json")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _same_community(value, query: str) -> bool:
    if value is None:
        return False
    return str(value) == query


def _edge_ends(edge: dict):
    src = edge.get("from_id")
    if src is None:
        src = edge.get("source")
    if src is None and "from" in edge:
        src = edge.get("from")
    dst = edge.get("to_id")
    if dst is None:
        dst = edge.get("target")
    if dst is None and "to" in edge:
        dst = edge.get("to")
    return src, dst


def _load_graph_json(repo_path):
    path = os.path.join(str(repo_path), ".synlynk", "graphify-out", "graph.json")
    if not os.path.isfile(path):
        return [], []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return [], []
    if not isinstance(loaded, dict):
        return [], []
    raw_nodes = loaded.get("nodes")
    nodes = [node for node in raw_nodes if isinstance(node, dict)] if isinstance(raw_nodes, list) else []
    raw_edges = loaded.get("edges")
    if not isinstance(raw_edges, list):
        raw_edges = loaded.get("links")
    edges = [edge for edge in raw_edges if isinstance(edge, dict)] if isinstance(raw_edges, list) else []
    return nodes, edges


def _load_sqlite(db_path):
    if not db_path or not os.path.isfile(str(db_path)):
        return [], []
    uri = "file:" + os.path.abspath(str(db_path)) + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return [], []
    try:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, label, kind, source_path, attrs_json "
                "FROM workspace_view_nodes WHERE view = 'logical'"
            ).fetchall()
            edge_rows = conn.execute(
                "SELECT from_id, to_id, kind FROM workspace_view_edges WHERE view = 'logical'"
            ).fetchall()
        except sqlite3.Error:
            return [], []
    finally:
        conn.close()
    nodes = [
        {
            "id": row["id"],
            "label": row["label"],
            "kind": row["kind"],
            "source_file": row["source_path"] or "",
            "attrs_json": row["attrs_json"] or "{}",
        }
        for row in rows
    ]
    edges = [
        {"from_id": row["from_id"], "to_id": row["to_id"], "kind": row["kind"]}
        for row in edge_rows
    ]
    return nodes, edges
