"""Warm traversal cache over an existing Graphify code graph.

The cache stores short chains already present in graph.json. It does not
call graphify and it does not invent symbols.
"""

import json
import os
import re

_MAX_PATHS = 40
_MAX_NODES = 8
_MAX_TEST_CLOSURES = 15
_MAX_GODS = 10
_MAX_KEYWORDS = 12
_ENTRY_FILES = {"cli.py", "__main__.py", "main.py"}
_HTTP_VERBS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "when",
    "during", "after", "before", "into", "does", "what", "where", "which",
}


def write_traversal_cache(repo_root: str) -> dict:
    """Rebuild .synlynk/graph-cache/traversals.json from the current graph."""
    graph = _read_json(os.path.join(repo_root, ".synlynk", "graphify-out", "graph.json"))
    manifest = _read_json(os.path.join(repo_root, ".synlynk", "graphify-out", "manifest.json"))
    nodes = [node for node in (graph.get("nodes") or []) if isinstance(node, dict) and node.get("id")]
    edges = [edge for edge in (graph.get("edges") or graph.get("links") or []) if isinstance(edge, dict)]
    lifecycle = manifest.get("lifecycle")
    if lifecycle not in ("greenfield", "brownfield"):
        lifecycle = "greenfield" if not nodes else "brownfield"
    cache = {
        "schema": 1,
        "built_at_commit": str(manifest.get("built_at_commit") or ""),
        "lifecycle": lifecycle,
        "paths": _build_paths(nodes, edges) if nodes else [],
    }
    cache_dir = os.path.join(repo_root, ".synlynk", "graph-cache")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "traversals.json"), "w", encoding="utf-8") as handle:
        json.dump(cache, handle)
    return cache


def god_neighborhood_ids(repo_root: str) -> set[str]:
    """Ids stored on god-neighborhood chains. Empty when the cache is absent."""
    cache = _read_json(os.path.join(repo_root, ".synlynk", "graph-cache", "traversals.json"))
    found = set()
    for path in cache.get("paths") or []:
        if not isinstance(path, dict) or path.get("kind") != "god_neighborhood":
            continue
        for node in path.get("nodes") or []:
            if isinstance(node, dict) and node.get("id"):
                found.add(str(node.get("id")))
    return found


def lookup_traversal(repo_root: str, keywords) -> dict | None:
    """Return the best cached path, or None when the cache cannot be used."""
    cache = _read_json(os.path.join(repo_root, ".synlynk", "graph-cache", "traversals.json"))
    if cache.get("schema") != 1:
        return None
    manifest = _read_json(os.path.join(repo_root, ".synlynk", "graphify-out", "manifest.json"))
    if str(cache.get("built_at_commit") or "") != str(manifest.get("built_at_commit") or ""):
        return None
    query = {str(word).lower() for word in keywords if str(word).strip()}
    best = None
    best_rank = None
    for path in cache.get("paths") or []:
        if not isinstance(path, dict):
            continue
        path_words = [str(word).lower() for word in (path.get("keywords") or [])]
        hits = sum(1 for word in path_words if word in query)
        if hits < 2:
            continue
        rank = (-hits, len(path.get("nodes") or []))
        if best_rank is None or rank < best_rank:
            best = path
            best_rank = rank
    return best


def render_cached_pack(path: dict, token_budget: int = 1500) -> str:
    """Render one cached chain with the pack token cutter."""
    from synlynk.pack import _cut_to_token_budget

    lines = [
        "## Task Context Pack (Generated via AST Knowledge Graph)",
        "",
        "### Target Symbols & Interfaces",
    ]
    for node in path.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        shown = node.get("signature") or node.get("label") or node.get("id")
        file_str = node.get("file") or ""
        suffix = f" [{file_str}]" if file_str else ""
        lines.append(f"- `{shown}`{suffix}")
    return _cut_to_token_budget("\n".join(lines), token_budget=token_budget)


def _build_paths(nodes: list, edges: list) -> list:
    by_id = {str(node.get("id")): node for node in nodes}
    outbound: dict[str, list[str]] = {}
    inbound: dict[str, list[str]] = {}
    degree: dict[str, int] = {node_id: 0 for node_id in by_id}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in by_id and target in by_id:
            outbound.setdefault(source, []).append(target)
            inbound.setdefault(target, []).append(source)
            degree[source] = degree.get(source, 0) + 1
            degree[target] = degree.get(target, 0) + 1

    paths = []
    entry_ids = []
    for node in nodes:
        if _is_entrypoint(node):
            chain = _walk(str(node.get("id")), outbound, by_id, hops=3)
            paths.append(_path("entrypoint", str(node.get("id")), chain))
            entry_ids.extend(item["id"] for item in chain)
            if len(paths) >= _MAX_PATHS:
                return paths[:_MAX_PATHS]

    route_ids = []
    for node in nodes:
        if _is_route(node):
            chain = _walk(str(node.get("id")), outbound, by_id, hops=3)
            paths.append(_path("route", str(node.get("id")), chain))
            route_ids.extend(item["id"] for item in chain)
            if len(paths) >= _MAX_PATHS:
                return paths[:_MAX_PATHS]

    touched = set(entry_ids) | set(route_ids)
    tests = []
    for node in nodes:
        if not _is_test_file(str(node.get("file") or "")):
            continue
        pointed = []
        for target in outbound.get(str(node.get("id")), []):
            if target in by_id:
                pointed.append(by_id[target])
        overlap = sum(1 for item in pointed if item.get("id") in touched)
        tests.append((overlap, node, pointed))
    tests.sort(key=lambda item: item[0], reverse=True)
    test_files = set()
    for _overlap, node, pointed in tests[:_MAX_TEST_CLOSURES]:
        chain = [_public_node(node)]
        for item in pointed:
            if len(chain) >= _MAX_NODES:
                break
            chain.append(_public_node(item))
        test_files.add(str(node.get("file") or ""))
        paths.append(_path("test_closure", str(node.get("id")), chain))
        if len(paths) >= _MAX_PATHS:
            return paths[:_MAX_PATHS]

    ranked = sorted(degree, key=lambda node_id: degree[node_id], reverse=True)
    for node_id in ranked[:_MAX_GODS]:
        if degree[node_id] <= 0:
            continue
        chain = [_public_node(by_id[node_id])]
        neighbors = []
        for other in inbound.get(node_id, []) + outbound.get(node_id, []):
            if other == node_id or other not in by_id:
                continue
            neighbor = by_id[other]
            if str(neighbor.get("file") or "") in test_files:
                continue
            if any(item["id"] == other for item in chain):
                continue
            neighbors.append(_public_node(neighbor))
        for neighbor in neighbors:
            if len(chain) >= _MAX_NODES:
                break
            chain.append(neighbor)
        paths.append(_path("god_neighborhood", node_id, chain))
        if len(paths) >= _MAX_PATHS:
            break
    return paths[:_MAX_PATHS]


def _path(kind: str, node_id: str, chain: list) -> dict:
    nodes = []
    for node in chain:
        if {"id", "label", "file", "kind", "signature"} <= set(node) and "docstring" not in node:
            nodes.append({key: node.get(key, "") for key in ("id", "label", "file", "kind", "signature")})
        else:
            nodes.append(_public_node(node))
    return {
        "id": f"{kind}:{node_id}",
        "kind": kind,
        "keywords": _keywords(nodes),
        "nodes": nodes[:_MAX_NODES],
    }


def _public_node(node: dict) -> dict:
    return {
        "id": str(node.get("id") or ""),
        "label": str(node.get("label") or ""),
        "file": str(node.get("file") or ""),
        "kind": str(node.get("kind") or ""),
        "signature": str(node.get("signature") or node.get("label") or ""),
    }


def _keywords(nodes: list) -> list:
    blob = " ".join(
        f"{node.get('label', '')} {node.get('file', '')} {node.get('id', '')}"
        for node in nodes
    )
    words = re.findall(r"[a-zA-Z0-9]{3,}", blob.lower())
    chosen = []
    for word in words:
        if word in _STOPWORDS or word in chosen:
            continue
        chosen.append(word)
        if len(chosen) >= _MAX_KEYWORDS:
            break
    return chosen


def _walk(start: str, outbound: dict, by_id: dict, hops: int) -> list:
    chain = []
    seen = set()
    frontier = [start]
    for depth in range(hops + 1):
        nxt = []
        for node_id in frontier:
            if node_id in seen or node_id not in by_id:
                continue
            seen.add(node_id)
            chain.append(_public_node(by_id[node_id]))
            if len(chain) >= _MAX_NODES:
                return chain
            if depth < hops:
                nxt.extend(outbound.get(node_id, []))
        frontier = nxt
    return chain


def _is_entrypoint(node: dict) -> bool:
    base = os.path.basename(str(node.get("file") or ""))
    if base in _ENTRY_FILES:
        return True
    return str(node.get("label") or "") == "main"


def _is_route(node: dict) -> bool:
    if str(node.get("kind") or "") == "route":
        return True
    label = str(node.get("label") or "").strip()
    if label.startswith("/"):
        return True
    upper = label.upper()
    for verb in _HTTP_VERBS:
        if upper == verb or upper.startswith(verb + " ") or upper.startswith(verb + "/"):
            return True
    return False


def _is_test_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return normalized.startswith("tests/test_") and normalized.endswith(".py")


def _read_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
