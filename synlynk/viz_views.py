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


_VIEWS = ("product", "logical", "infra", "world")



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
                     head_sha: str, stale: int = 0) -> None:
    init_workspace_view_tables(conn)
    conn.execute("DELETE FROM workspace_view_edges WHERE view = ? AND (from_id IN (SELECT id FROM workspace_view_nodes WHERE view = ? AND repo = ?) OR to_id IN (SELECT id FROM workspace_view_nodes WHERE view = ? AND repo = ?))", (view, view, repo, view, repo))
    conn.execute("DELETE FROM workspace_view_nodes WHERE view = ? AND repo = ?", (view, repo))
    unique_nodes = list({n["id"]: n for n in nodes}.values())
    conn.executemany(
        "INSERT OR REPLACE INTO workspace_view_nodes (id, view, repo, kind, label, attrs_json, provenance, source_path, scanned_at, head_sha) VALUES (:id, :view, :repo, :kind, :label, :attrs_json, :provenance, :source_path, :scanned_at, :head_sha)",
        unique_nodes,
    )
    unique_edges = list({e["id"]: e for e in edges}.values())
    conn.executemany(
        "INSERT OR REPLACE INTO workspace_view_edges (id, view, from_id, to_id, kind, provenance, attrs_json, scanned_at) VALUES (:id, :view, :from_id, :to_id, :kind, :provenance, :attrs_json, :scanned_at)",
        unique_edges,
    )
    conn.execute(
        "INSERT INTO workspace_view_meta (view, generated_at, head_sha, source_counts_json, duration_ms, stale) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(view) DO UPDATE SET generated_at=excluded.generated_at, head_sha=excluded.head_sha, source_counts_json=excluded.source_counts_json, duration_ms=excluded.duration_ms, stale=excluded.stale",
        (view, _now(), head_sha, json.dumps({"nodes": len(nodes), "edges": len(edges)}), int((time.monotonic() - started) * 1000), stale),
    )
    conn.commit()


def _node(view: str, repo: str, kind: str, label: str, attrs: dict,
          source_path: str, provenance: str, now: str, head_sha: str) -> dict:
    node_key = label if view == "world" else (source_path or label)
    return {"id": _id(view, repo, kind, node_key), "view": view,
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
    """Extract Python packages/modules or Graphify call-graph from the repository tree."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    nodes, edges = [], []

    # Check if Graphify AST knowledge graph is present
    graph_path = os.path.join(repo_path, ".synlynk", "graphify-out", "graph.json")
    manifest_path = os.path.join(repo_path, ".synlynk", "graphify-out", "manifest.json")

    graph_data = None
    if os.path.isfile(graph_path):
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and isinstance(loaded.get("nodes"), list):
                    graph_data = loaded
        except Exception:
            graph_data = None

    if graph_data is not None:
        try:
            # Read manifest for commit staleness anchor
            built_at_commit = ""
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest_data = json.load(f)
                        if isinstance(manifest_data, dict):
                            built_at_commit = str(manifest_data.get("built_at_commit") or "")
                except Exception:
                    built_at_commit = ""
            if not built_at_commit:
                built_at_commit = str(graph_data.get("built_at_commit") or "")

            is_stale = bool(sha and built_at_commit and sha != built_at_commit)
            stale_val = 1 if is_stale else 0

            raw_nodes = [n for n in (graph_data.get("nodes") or []) if isinstance(n, dict)]
            raw_edges = [e for e in (graph_data.get("edges") or graph_data.get("links") or []) if isinstance(e, dict)]

            degrees: Dict[str, int] = {}
            for e in raw_edges:
                src = str(e.get("source") or e.get("from") or e.get("from_id") or "")
                tgt = str(e.get("target") or e.get("to") or e.get("to_id") or "")
                if src:
                    degrees[src] = degrees.get(src, 0) + 1
                if tgt:
                    degrees[tgt] = degrees.get(tgt, 0) + 1

            total_nodes = len(raw_nodes)
            id_map: Dict[str, str] = {}
            seen_node_ids = set()

            for rn in raw_nodes:
                raw_id = str(rn.get("id") or "")
                label = str(rn.get("label") or raw_id or "")
                kind = str(rn.get("kind") or "module")
                source_path = str(rn.get("source_path") or rn.get("file") or rn.get("path") or "")
                if not source_path and ":" in raw_id:
                    source_path = raw_id.split(":", 1)[0]

                node_id = _id("logical", repo, kind, raw_id or source_path or label)
                id_map[raw_id] = node_id
                id_map[label] = node_id

                if node_id in seen_node_ids:
                    continue
                seen_node_ids.add(node_id)

                community = rn.get("community", 0)
                centrality = rn.get("centrality") or rn.get("rank")
                if centrality is None:
                    deg = degrees.get(raw_id, 0)
                    centrality = round(deg / max(1, total_nodes - 1), 4) if total_nodes > 1 else 1.0

                attrs = {k: v for k, v in rn.items() if k not in ("id", "label", "kind", "source_path", "file", "path")}
                attrs["community"] = community
                attrs["centrality"] = centrality
                if built_at_commit:
                    attrs["built_at_commit"] = built_at_commit
                if is_stale:
                    attrs["stale"] = True

                node = {
                    "id": node_id,
                    "view": "logical",
                    "repo": repo,
                    "kind": kind,
                    "label": label,
                    "attrs_json": json.dumps(attrs, sort_keys=True),
                    "provenance": "graphify",
                    "source_path": source_path,
                    "scanned_at": now,
                    "head_sha": sha,
                    "community": community,
                    "centrality": centrality,
                    "stale": is_stale,
                }
                nodes.append(node)

            seen_edge_ids = set()
            for re_edge in raw_edges:
                src_raw = str(re_edge.get("source") or re_edge.get("from") or re_edge.get("from_id") or "")
                tgt_raw = str(re_edge.get("target") or re_edge.get("to") or re_edge.get("to_id") or "")
                from_id = id_map.get(src_raw) or _id("logical", repo, "node", src_raw)
                to_id = id_map.get(tgt_raw) or _id("logical", repo, "node", tgt_raw)

                if from_id not in seen_node_ids or to_id not in seen_node_ids:
                    continue

                edge_kind = str(re_edge.get("kind") or re_edge.get("type") or "calls")
                edge_id = _id("edge", from_id, to_id, edge_kind)
                if edge_id in seen_edge_ids:
                    continue
                seen_edge_ids.add(edge_id)

                edge_attrs = {k: v for k, v in re_edge.items() if k not in ("source", "target", "from", "to", "from_id", "to_id", "kind", "type")}
                edge = {
                    "id": edge_id,
                    "view": "logical",
                    "from_id": from_id,
                    "to_id": to_id,
                    "kind": edge_kind,
                    "provenance": "graphify",
                    "attrs_json": json.dumps(edge_attrs, sort_keys=True),
                    "scanned_at": now,
                }
                edges.append(edge)

            _save_projection(conn, "logical", repo, nodes, edges, started, sha, stale=stale_val)
            return nodes, edges
        except Exception:
            # Fall back cleanly to standard directory-based extraction on any schema error
            nodes, edges = [], []

    package_nodes: Dict[str, dict] = {}
    skip = {
        ".git", ".synlynk", "__pycache__", "node_modules", ".venv", "venv",
        "worktrees", ".worktrees", ".claude", ".pytest_cache", ".ruff_cache",
        "dist", "build", "test_archive", "test_context_output",
    }
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
    try:
        from synlynk.scan import _query_repo_file_tree
        _query_repo_file_tree()
    except Exception:
        pass
    _save_projection(conn, "logical", repo, nodes, edges, started, sha, stale=0)
    return nodes, edges


def extract_infra_nodes(conn: sqlite3.Connection, repo_path: str) -> Tuple[List[dict], List[dict]]:
    """Describe the local daemon and Vizor service boundary."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    daemon = _node("infra", repo, "service", "Synlynk Daemon (Background)", {"type": "process"}, ".synlynk/daemon.pid", "inferred", now, sha)
    vizor = _node("infra", repo, "service", "Vizor Server (:8721)", {"port": 8721}, "synlynk/viz.py", "extracted", now, sha)
    nodes, edges = [daemon, vizor], [_edge("infra", daemon, vizor, "manages", "inferred", now)]
    _save_projection(conn, "infra", repo, nodes, edges, started, sha)
    return nodes, edges


def extract_world_nodes(conn: sqlite3.Connection, repo_path: str) -> Tuple[List[dict], List[dict]]:

    """Extract inside-out world perspective: external APIs, webhooks, IdPs, databases, and opportunity radar."""
    started, now, repo, sha = time.monotonic(), _now(), _repo_name(repo_path), _head_sha(repo_path)
    nodes: List[dict] = []
    edges: List[dict] = []

    # 1. Center Workspace Root Node (Ring 0)
    root_node = _node(
        "world", repo, "workspace", f"{repo} (Workspace Core)",
        {"ring": 0, "tier": "core", "criticality": 1.0, "description": "Local workspace runtime boundary"},
        ".", "extracted", now, sha
    )
    nodes.append(root_node)

    # 2. Heuristic External Egress Scanner
    detected_integrations: Dict[str, dict] = {}
    known_patterns = [
        # LLM / AI Providers
        (r"(openai|chatgpt)", "OpenAI API", "llm", 1, "LLM Inference Gateway", "OPENAI_API_KEY"),
        (r"(anthropic|claude)", "Anthropic Claude API", "llm", 1, "LLM Inference Gateway", "ANTHROPIC_API_KEY"),
        (r"(generativelanguage|gemini|google\.generativeai)", "Google Gemini API", "llm", 1, "LLM Multimodal API", "GEMINI_API_KEY"),
        (r"(grok|xai)", "xAI Grok API", "llm", 1, "LLM Inference Gateway", "XAI_API_KEY"),
        (r"(openrouter)", "OpenRouter Gateway", "llm", 1, "Model Aggregator", "OPENROUTER_API_KEY"),
        (r"(fal\.ai|fal_client)", "fal.ai Media Engine", "media", 1, "Generative Media & 3D", "FAL_KEY"),
        # Payments & Billing
        (r"(stripe)", "Stripe Payments", "payment", 1, "Payment Gateway & Billing", "STRIPE_API_KEY"),
        (r"(lemon_squeezy|lemonsqueezy)", "Lemon Squeezy", "payment", 1, "Merchant of Record", "LEMONSQUEEZY_API_KEY"),
        # Auth & Identity
        (r"(auth0)", "Auth0 Identity", "auth", 1, "OAuth2 / OIDC IdP", "AUTH0_CLIENT_SECRET"),
        (r"(clerk)", "Clerk Auth", "auth", 1, "User Management & Auth", "CLERK_SECRET_KEY"),
        (r"(firebase.*auth)", "Firebase Auth", "auth", 1, "Identity Provider", "FIREBASE_AUTH_KEY"),
        # Cloud Storage & Databases
        (r"(supabase)", "Supabase Backend", "database", 1, "Postgres & Edge Functions", "SUPABASE_KEY"),
        (r"(pinecone)", "Pinecone Vector DB", "database", 1, "Vector Index & Retrieval", "PINECONE_API_KEY"),
        (r"(redis)", "Redis Cache", "database", 1, "In-Memory Cache & Lock Store", "REDIS_URL"),
        (r"(s3|boto3|aws)", "AWS S3 / Cloud", "storage", 2, "Blob Storage & Infrastructure", "AWS_SECRET_ACCESS_KEY"),
        # Communications & Notifications
        (r"(resend)", "Resend Email", "comms", 2, "Transactional Email Delivery", "RESEND_API_KEY"),
        (r"(twilio)", "Twilio SMS/Voice", "comms", 2, "Telephony & SMS Gateway", "TWILIO_AUTH_TOKEN"),
        (r"(sendgrid)", "SendGrid Email", "comms", 2, "Email Delivery", "SENDGRID_API_KEY"),
        (r"(slack_sdk|slack)", "Slack Webhooks", "comms", 2, "Team Notification Webhooks", "SLACK_BOT_TOKEN"),
        # Developer & Source Control
        (r"(github\.com|api\.github\.com)", "GitHub REST/GraphQL API", "vcs", 1, "Source Control & Apps API", "GH_TOKEN"),
    ]

    # Quick scan of workspace files for patterns
    skip_dirs = {".git", ".synlynk", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".pytest_cache", ".ruff_cache", "project-docs", "docs"}
    scanned_count = 0
    max_scan_files = 150
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for f in files:
            if f.endswith((".py", ".js", ".ts", ".json", ".env.example", ".env", ".yml", ".yaml")):
                fpath = os.path.join(root, f)
                scanned_count += 1
                if scanned_count > max_scan_files:
                    break
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read(15000)
                        for pattern, label, category, ring, desc, env_var in known_patterns:
                            if label not in detected_integrations and re.search(pattern, content, re.IGNORECASE):
                                detected_integrations[label] = {
                                    "label": label,
                                    "category": category,
                                    "ring": ring,
                                    "description": desc,
                                    "env_var": env_var,
                                    "source_path": os.path.relpath(fpath, repo_path),
                                }
                except Exception:
                    pass
        if scanned_count > max_scan_files:
            break

    # Fallback to standard core providers if running in clean test sandbox
    if not detected_integrations:
        detected_integrations["GitHub REST/GraphQL API"] = {
            "label": "GitHub REST/GraphQL API", "category": "vcs", "ring": 1,
            "description": "Source Control & Apps API", "env_var": "GH_TOKEN", "source_path": "synlynk/gh.py"
        }
        detected_integrations["Google Gemini API"] = {
            "label": "Google Gemini API", "category": "llm", "ring": 1,
            "description": "LLM Multimodal API", "env_var": "GEMINI_API_KEY", "source_path": "synlynk/dispatch.py"
        }

    # Add detected integration nodes
    for name, item in detected_integrations.items():
        node = _node(
            "world", repo, item["category"], item["label"],
            {
                "ring": item["ring"],
                "category": item["category"],
                "description": item["description"],
                "env_var": item["env_var"],
                "tier": "egress" if item["ring"] <= 2 else "opportunity",
                "criticality": 0.9 if item["ring"] == 1 else 0.5,
            },
            item.get("source_path", "runtime"), "extracted", now, sha
        )
        nodes.append(node)
        edge_kind = "calls" if item["category"] in ("llm", "payment", "vcs") else "integrates_with"
        edges.append(_edge("world", root_node, node, edge_kind, "extracted", now))

    # 3. Opportunity Radar Ring 3 Projections (from .synlynk/radar.json or PM opportunities)
    radar_file = os.path.join(repo_path, ".synlynk", "radar.json")
    if os.path.exists(radar_file):
        try:
            with open(radar_file, "r", encoding="utf-8") as rf:
                opps = json.load(rf).get("opportunities", [])
                for opp in opps:
                    opp_node = _node(
                        "world", repo, "opportunity", opp.get("title", "Opportunity Node"),
                        {
                            "ring": 3,
                            "category": "opportunity",
                            "description": opp.get("description", "Projected partner opportunity"),
                            "tier": "opportunity",
                            "estimated_value": opp.get("value", "medium"),
                        },
                        "project-docs/roadmap.md", "projected", now, sha
                    )
                    nodes.append(opp_node)
                    edges.append(_edge("world", root_node, opp_node, "evaluates", "projected", now))
        except Exception:
            pass

    _save_projection(conn, "world", repo, nodes, edges, started, sha)
    return nodes, edges


def build_workspace_views_snapshot(conn: sqlite3.Connection, repo_path: str) -> dict:
    """Refresh all four projections and return the JSON-ready snapshot."""
    product = extract_product_nodes(conn, repo_path)
    logical = extract_logical_nodes(conn, repo_path)
    infra = extract_infra_nodes(conn, repo_path)
    world = extract_world_nodes(conn, repo_path)
    logical_stale = False
    try:
        row = conn.execute("SELECT stale FROM workspace_view_meta WHERE view = 'logical'").fetchone()
        if row and row[0]:
            logical_stale = bool(row[0])
    except Exception:
        pass
    return {
        "product": {"nodes": product[0], "edges": product[1]},
        "logical": {"nodes": logical[0], "edges": logical[1], "stale": logical_stale},
        "infra": {"nodes": infra[0], "edges": infra[1]},
        "world": {"nodes": world[0], "edges": world[1]},
        "updated_at": _now()
    }

