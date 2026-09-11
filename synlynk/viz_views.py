"""Projection data for Vizor's product, logical, and infrastructure views.

The projection tables are deliberately separate from Synlynk's canonical
tables.  They are a refreshable, query-friendly representation of repository
topology used by the offline Vizor pages.
"""

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from typing import Dict, List, Tuple


_VIEWS = ("product", "logical", "infra")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _repo_name(repo_path: str) -> str:
    return os.path.basename(os.path.abspath(repo_path)) or "repo"


def _head_sha(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", os.path.abspath(repo_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _id(*parts: str) -> str:
    # IDs are readable for debugging and stable for repeat snapshots.
    return ":".join(str(part).replace(":", "%3A") for part in parts)


def init_workspace_view_tables(conn: sqlite3.Connection) -> None:
    """Create the refreshable workspace-view projection schema."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_view_nodes (
            id TEXT PRIMARY KEY,
            view TEXT NOT NULL,
            repo TEXT NOT NULL,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            attrs_json TEXT NOT NULL DEFAULT '{}',
            provenance TEXT NOT NULL,
            source_path TEXT,
            scanned_at TEXT NOT NULL,
            head_sha TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_view_nodes_view_repo
            ON workspace_view_nodes(view, repo);

        CREATE TABLE IF NOT EXISTS workspace_view_edges (
            id TEXT PRIMARY KEY,
            view TEXT NOT NULL,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            provenance TEXT NOT NULL,
            attrs_json TEXT NOT NULL DEFAULT '{}',
            scanned_at TEXT NOT NULL,
            FOREIGN KEY (from_id) REFERENCES workspace_view_nodes(id),
            FOREIGN KEY (to_id) REFERENCES workspace_view_nodes(id)
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_view_edges_view
            ON workspace_view_edges(view);

        CREATE TABLE IF NOT EXISTS workspace_view_meta (
            view TEXT PRIMARY KEY,
            generated_at TEXT NOT NULL,
            head_sha TEXT,
            source_counts_json TEXT NOT NULL DEFAULT '{}',
            duration_ms INTEGER NOT NULL DEFAULT 0,
            stale INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()


def _save_projection(conn: sqlite3.Connection, view: str, repo: str,
                     nodes: List[dict], edges: List[dict], started: float,
                     head_sha: str) -> None:
    init_workspace_view_tables(conn)
    conn.execute("DELETE FROM workspace_view_edges WHERE view = ? AND (from_id IN (SELECT id FROM workspace_view_nodes WHERE view = ? AND repo = ?) OR to_id IN (SELECT id FROM workspace_view_nodes WHERE view = ? AND repo = ?))", (view, view, repo, view, repo))
    conn.execute("DELETE FROM workspace_view_nodes WHERE view = ? AND repo = ?", (view, repo))
    conn.executemany(
        "INSERT INTO workspace_view_nodes (id, view, repo, kind, label, attrs_json, provenance, source_path, scanned_at, head_sha) VALUES (:id, :view, :repo, :kind, :label, :attrs_json, :provenance, :source_path, :scanned_at, :head_sha)",
        nodes,
    )
    conn.executemany(
        "INSERT INTO workspace_view_edges (id, view, from_id, to_id, kind, provenance, attrs_json, scanned_at) VALUES (:id, :view, :from_id, :to_id, :kind, :provenance, :attrs_json, :scanned_at)",
        edges,
    )
    conn.execute(
        "INSERT INTO workspace_view_meta (view, generated_at, head_sha, source_counts_json, duration_ms, stale) VALUES (?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(view) DO UPDATE SET generated_at=excluded.generated_at, head_sha=excluded.head_sha, source_counts_json=excluded.source_counts_json, duration_ms=excluded.duration_ms, stale=0",
        (view, _now(), head_sha, json.dumps({"nodes": len(nodes), "edges": len(edges)}), int((time.monotonic() - started) * 1000)),
    )
    conn.commit()


def _node(view: str, repo: str, kind: str, label: str, attrs: dict,
          source_path: str, provenance: str, now: str, head_sha: str) -> dict:
    return {"id": _id(view, repo, kind, source_path or label), "view": view,
            "repo": repo, "kind": kind, "label": label,
            "attrs_json": json.dumps(attrs, sort_keys=True),
            "provenance": provenance, "source_path": source_path,
            "scanned_at": now, "head_sha": head_sha}


def _edge(view: str, source: dict, target: dict, kind: str,
          provenance: str, now: str) -> dict:
    return {"id": _id("edge", source["id"], target["id"], kind),
            "view": view, "from_id": source["id"], "to_id": target["id"],
            "kind": kind, "provenance": provenance, "attrs_json": "{}",
            "scanned_at": now}


def extract_product_nodes(conn: sqlite3.Connection, repo_path: str) -> Tuple[List[dict], List[dict]]:
    """Extract authored journey documents and their declared routes."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    nodes, edges = [], []
    journey_root = os.path.join(repo_path, "docs", "journeys")
    if os.path.isdir(journey_root):
        for root, _, files in os.walk(journey_root):
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(root, filename)
                relative = os.path.relpath(path, repo_path).replace(os.sep, "/")
                journey = _node("product", repo, "journey", os.path.splitext(filename)[0].replace("-", " ").title(), {"file": relative}, relative, "authored", now, sha)
                nodes.append(journey)
                try:
                    text = open(path, encoding="utf-8").read()
                except OSError:
                    continue
                for match in re.finditer(r"(?m)^\s*route\s*:\s*(\S+)", text):
                    route = match.group(1)
                    route_node = _node("product", repo, "route", route, {"route": route}, relative + "#route=" + route, "extracted", now, sha)
                    nodes.append(route_node)
                    edges.append(_edge("product", journey, route_node, "includes", "extracted", now))
    _save_projection(conn, "product", repo, nodes, edges, started, sha)
    return nodes, edges


def extract_logical_nodes(conn: sqlite3.Connection, repo_path: str) -> Tuple[List[dict], List[dict]]:
    """Extract Python packages/modules from the repository tree."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    nodes, edges = [], []
    package_nodes: Dict[str, dict] = {}
    skip = {".git", ".synlynk", "__pycache__", "node_modules", ".venv", "venv"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
        py_files = sorted(f for f in files if f.endswith(".py") and not f.startswith("."))
        if not py_files:
            continue
        relative_dir = os.path.relpath(root, repo_path).replace(os.sep, "/")
        package_name = relative_dir if relative_dir != "." else repo
        package = package_nodes.get(package_name)
        if package is None:
            package = _node("logical", repo, "package", os.path.basename(root) if relative_dir != "." else repo, {"dir": relative_dir}, relative_dir, "extracted", now, sha)
            package_nodes[package_name] = package
            nodes.append(package)
        for filename in py_files:
            relative = os.path.relpath(os.path.join(root, filename), repo_path).replace(os.sep, "/")
            module = _node("logical", repo, "module", filename, {"path": relative}, relative, "extracted", now, sha)
            nodes.append(module)
            edges.append(_edge("logical", package, module, "includes", "extracted", now))
    # The scanner's tree is the canonical source when available; retain it as
    # metadata without making extraction depend on a particular DB schema.
    try:
        from synlynk.scan import _query_repo_file_tree
        _query_repo_file_tree()
    except Exception:
        pass
    _save_projection(conn, "logical", repo, nodes, edges, started, sha)
    return nodes, edges


def extract_infra_nodes(conn: sqlite3.Connection, repo_path: str) -> Tuple[List[dict], List[dict]]:
    """Describe the local daemon and Vizor service boundary."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    daemon = _node("infra", repo, "service", "Synlynk Daemon (Background)", {"type": "process"}, ".synlynk/daemon.pid", "inferred", now, sha)
    vizor = _node("infra", repo, "service", "Vizor Server (:8721)", {"port": 8721}, "synlynk/viz.py", "extracted", now, sha)
    nodes, edges = [daemon, vizor], [_edge("infra", daemon, vizor, "manages", "inferred", now)]
    _save_projection(conn, "infra", repo, nodes, edges, started, sha)
    return nodes, edges


def build_workspace_views_snapshot(conn: sqlite3.Connection, repo_path: str) -> dict:
    """Refresh all three projections and return the JSON-ready snapshot."""
    product = extract_product_nodes(conn, repo_path)
    logical = extract_logical_nodes(conn, repo_path)
    infra = extract_infra_nodes(conn, repo_path)
    return {"product": {"nodes": product[0], "edges": product[1]},
            "logical": {"nodes": logical[0], "edges": logical[1]},
            "infra": {"nodes": infra[0], "edges": infra[1]},
            "updated_at": _now()}
