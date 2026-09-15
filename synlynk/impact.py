"""Blast radius and impact calculator using the Graphify knowledge graph."""

import json
import os
from collections import deque
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


def _is_test_node(node: Dict[str, Any]) -> bool:
    file_path = str(node.get("file") or "").lower()
    label = str(node.get("label") or "").lower()
    node_id = str(node.get("id") or "").lower()
    return (
        file_path.startswith("tests/")
        or file_path.startswith("test/")
        or "/tests/" in file_path
        or "/test/" in file_path
        or label.startswith("test_")
        or label.endswith("_test")
        or node_id.startswith("tests.")
        or node_id.startswith("test.")
    )


def calculate_impact(
    repo_root: str,
    target: str,
    max_depth: int = 10,
) -> Dict[str, Any]:
    """Calculate the blast radius for a symbol or file in the repo.
    
    Returns upstream callers, downstream callees, and associated tests.
    """
    empty_report = {
        "target": target,
        "target_nodes": [],
        "upstream_callers": [],
        "downstream_callees": [],
        "associated_tests": [],
    }

    graph_path = Path(repo_root) / ".synlynk" / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        return empty_report

    try:
        data = json.loads(graph_path.read_text(errors="ignore"))
    except Exception:
        return empty_report

    nodes = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (data.get("edges") or data.get("links") or []) if isinstance(e, dict)]

    if not nodes:
        return empty_report

    # Index nodes
    node_by_id = {str(n.get("id")): n for n in nodes}

    # Match target nodes
    target_clean = target.strip()
    target_lower = target_clean.lower()
    matched_nodes = []
    for n in nodes:
        nid = str(n.get("id") or "")
        label = str(n.get("label") or "")
        file_path = str(n.get("file") or "")

        if (
            nid == target_clean
            or label == target_clean
            or file_path == target_clean
            or nid.lower() == target_lower
            or label.lower() == target_lower
            or file_path.lower() == target_lower
            or file_path.endswith("/" + target_clean)
            or file_path.endswith(target_clean)
        ):
            matched_nodes.append(n)

    if not matched_nodes:
        # Secondary loose match if no exact match
        for n in nodes:
            label = str(n.get("label") or "").lower()
            if target_lower in label:
                matched_nodes.append(n)

    if not matched_nodes:
        return empty_report

    target_ids = {str(n["id"]) for n in matched_nodes}

    # Build adjacency maps
    # inbound: target -> list of source nodes (callers)
    # outbound: source -> list of target nodes (callees)
    inbound_map: Dict[str, List[Dict[str, Any]]] = {}
    outbound_map: Dict[str, List[Dict[str, Any]]] = {}

    for e in edges:
        src = str(e.get("source"))
        tgt = str(e.get("target"))
        if src in node_by_id and tgt in node_by_id:
            inbound_map.setdefault(tgt, []).append(node_by_id[src])
            outbound_map.setdefault(src, []).append(node_by_id[tgt])

    # BFS Upstream (Callers & Tests)
    upstream_nodes: List[Dict[str, Any]] = []
    associated_tests: List[Dict[str, Any]] = []
    visited_upstream: Set[str] = set(target_ids)

    queue = deque([(tid, 0) for tid in target_ids])
    while queue:
        curr_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for parent in inbound_map.get(curr_id, []):
            pid = str(parent.get("id"))
            if pid not in visited_upstream:
                visited_upstream.add(pid)
                if _is_test_node(parent):
                    associated_tests.append(parent)
                else:
                    upstream_nodes.append(parent)
                queue.append((pid, depth + 1))

    # BFS Downstream (Callees)
    downstream_nodes: List[Dict[str, Any]] = []
    visited_downstream: Set[str] = set(target_ids)

    queue = deque([(tid, 0) for tid in target_ids])
    while queue:
        curr_id, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for child in outbound_map.get(curr_id, []):
            cid = str(child.get("id"))
            if cid not in visited_downstream:
                visited_downstream.add(cid)
                downstream_nodes.append(child)
                queue.append((cid, depth + 1))

    return {
        "target": target,
        "target_nodes": matched_nodes,
        "upstream_callers": upstream_nodes,
        "downstream_callees": downstream_nodes,
        "associated_tests": associated_tests,
    }


def cmd_impact(args) -> int:
    """CLI handler for `synlynk impact <symbol|file>`."""
    target = getattr(args, "target", None)
    if not target:
        print("Error: Target symbol or file path is required.")
        return 1

    repo_root = getattr(args, "repo_root", ".") or "."
    max_depth = getattr(args, "depth", 10) or 10
    as_json = getattr(args, "json", False)

    report = calculate_impact(repo_root, target, max_depth=max_depth)

    if as_json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"\n⚡ Blast Radius & Impact Analysis for '{target}':")
    if not report["target_nodes"]:
        print("  No matching symbol or file found in knowledge graph.")
        return 0

    print(f"  Matched targets: {len(report['target_nodes'])}")
    for n in report["target_nodes"]:
        loc = f" ({n.get('file')}:{n.get('line')})" if n.get('file') else ""
        print(f"    - {n.get('label') or n.get('id')}{loc}")

    print(f"\n  Upstream Callers ({len(report['upstream_callers'])}):")
    for c in report["upstream_callers"][:15]:
        loc = f" ({c.get('file')}:{c.get('line')})" if c.get('file') else ""
        print(f"    ▲ {c.get('label') or c.get('id')}{loc}")
    if len(report["upstream_callers"]) > 15:
        print(f"    ... and {len(report['upstream_callers']) - 15} more")

    print(f"\n  Associated Tests ({len(report['associated_tests'])}):")
    for t in report["associated_tests"]:
        loc = f" ({t.get('file')}:{t.get('line')})" if t.get('file') else ""
        print(f"    ✓ {t.get('label') or t.get('id')}{loc}")

    print(f"\n  Downstream Callees ({len(report['downstream_callees'])}):")
    for d in report["downstream_callees"][:10]:
        loc = f" ({d.get('file')}:{d.get('line')})" if d.get('file') else ""
        print(f"    ▼ {d.get('label') or d.get('id')}{loc}")
    if len(report["downstream_callees"]) > 10:
        print(f"    ... and {len(report['downstream_callees']) - 10} more")

    print()
    return 0
