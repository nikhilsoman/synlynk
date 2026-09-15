"""Multi-repo knowledge mesh aggregator and cross-repository edge inference."""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple


def merge_fleet_graphs(repo_paths: List[str]) -> Dict[str, Any]:
    """Merge knowledge graphs from multiple repositories into a unified mesh."""
    merged_nodes: List[Dict[str, Any]] = []
    merged_edges: List[Dict[str, Any]] = []
    seen_node_ids: Set[str] = set()

    for path_str in repo_paths:
        repo_dir = Path(path_str).resolve()
        graph_file = repo_dir / ".synlynk" / "graphify-out" / "graph.json"
        if not graph_file.is_file():
            continue

        try:
            data = json.loads(graph_file.read_text(errors="ignore"))
        except Exception:
            continue

        nodes = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
        edges = [e for e in (data.get("edges") or data.get("links") or []) if isinstance(e, dict)]

        repo_name = repo_dir.name

        for n in nodes:
            nid = str(n.get("id") or "")
            if not nid:
                continue
            # If node id doesn't have repo namespace, prefix it
            if not nid.startswith(f"{repo_name}:") and ":" not in nid:
                nid = f"{repo_name}:{nid}"
                n["id"] = nid
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                n["repo"] = repo_name
                merged_nodes.append(n)

        for e in edges:
            src = str(e.get("source") or "")
            tgt = str(e.get("target") or "")
            if src and tgt:
                merged_edges.append(e)

    return {
        "nodes": merged_nodes,
        "edges": merged_edges,
    }


def infer_cross_repo_edges(merged_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Infer cross-repository dependencies such as HTTP API contracts and client fetches."""
    nodes = merged_graph.get("nodes") or []
    inferred_edges: List[Dict[str, Any]] = []

    # Identify route / API endpoint nodes
    route_nodes = []
    client_nodes = []

    for n in nodes:
        kind = str(n.get("kind") or "").lower()
        label = str(n.get("label") or "")

        if kind == "route" or (label.startswith("/") and len(label) > 1):
            route_nodes.append(n)
        elif kind in ("fetch", "client", "call") or "fetch(" in label or "http" in label.lower():
            client_nodes.append(n)

    # Correlate client calls to route endpoints across repos
    for client in client_nodes:
        clabel = str(client.get("label") or "")
        cid = str(client.get("id") or "")
        crepo = client.get("repo")

        for route in route_nodes:
            rlabel = str(route.get("label") or "")
            rid = str(route.get("id") or "")
            rrepo = route.get("repo")

            if crepo and rrepo and crepo == rrepo:
                continue  # only cross-repo edges

            # Extract path token from route label e.g. "/users"
            route_path = rlabel.strip()
            if route_path and route_path in clabel:
                inferred_edges.append({
                    "source": cid,
                    "target": rid,
                    "kind": "cross-repo-call",
                    "inferred": True,
                })

    return inferred_edges


def write_global_graph(
    merged_graph: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """Write the merged multi-repo graph to global-graph.json."""
    if output_path is None:
        target_path = Path.home() / ".synlynk" / "global-graph.json"
    else:
        target_path = Path(output_path).expanduser().resolve()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(merged_graph, indent=2))
    return str(target_path)


def cmd_multirepo_mesh(args) -> int:
    """CLI handler for `synlynk mesh`."""
    repo_args = getattr(args, "repos", None)
    repos = []
    if repo_args:
        repos = [r.strip() for r in repo_args.split(",") if r.strip()]
    else:
        # Check current repo and common parent workspaces
        cwd = Path.cwd()
        repos.append(str(cwd))
        # Look for sibling directories that are synlynk workspaces
        parent = cwd.parent
        for child in parent.iterdir():
            if child.is_dir() and (child / ".synlynk").is_dir() and str(child) not in repos:
                repos.append(str(child))

    merged = merge_fleet_graphs(repos)
    inferred = infer_cross_repo_edges(merged)
    merged["edges"].extend(inferred)

    output_path = getattr(args, "output", None)
    saved_path = write_global_graph(merged, output_path=output_path)

    print(f"\n🌐 Federated Knowledge Mesh Synthesized:")
    print(f"  Repositories aggregated: {len(repos)}")
    print(f"  Total nodes: {len(merged['nodes'])}")
    print(f"  Total edges: {len(merged['edges'])} ({len(inferred)} cross-repo inferred)")
    print(f"  Persisted to: {saved_path}\n")
    return 0
