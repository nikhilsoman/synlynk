"""Adaptive Scope-Bounded Sparse Worktree Engine (#1389, #1390, #1391, #1787).

Provides high-performance cone-mode sparse worktrees for multi-agent dispatches,
preventing storage amplification and reducing checkout latency by only materializing
mandatory configuration and task-scoped paths.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Set

MANDATORY_SPARSE_CONE_DIRS = (".synlynk", "project-docs", "tests", "synlynk")


def is_sparse_worktree(worktree_path: str) -> bool:
    """Returns True if the given worktree has sparse checkout active."""
    if not os.path.isdir(worktree_path):
        return False
    try:
        res = subprocess.run(
            ["git", "-C", worktree_path, "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.returncode == 0 and res.stdout.strip().lower() in ("true", "1")
    except OSError:
        return False


def derive_sparse_cone_paths_from_graph(
    repo_root: str,
    task_text: str = "",
    story_id: Optional[str] = None,
    max_dirs: int = 8,
) -> List[str]:
    """Derive minimal required directory cones from the AST knowledge graph."""
    cone_set: Set[str] = set(MANDATORY_SPARSE_CONE_DIRS)
    graph_path = Path(repo_root) / ".synlynk" / "graphify-out" / "graph.json"

    if not graph_path.is_file():
        return sorted(cone_set)

    try:
        data = json.loads(graph_path.read_text(errors="ignore"))
    except Exception:
        return sorted(cone_set)

    nodes = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (data.get("edges") or data.get("links") or []) if isinstance(e, dict)]

    if not nodes:
        return sorted(cone_set)

    query_text = task_text or ""
    if story_id:
        query_text += f" {story_id}"
        try:
            from synlynk import _get_db
            conn = _get_db()
            row = conn.execute(
                "SELECT title, description, criteria FROM stories WHERE story_id = ?",
                (story_id,),
            ).fetchone()
            if row:
                query_text += f" {row[0] or ''} {row[1] or ''} {row[2] or ''}"
            conn.close()
        except Exception:
            pass

    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "when",
        "during", "after", "before", "error", "issue", "fix", "add",
        "update", "test", "into", "does", "what", "where", "which"
    }
    keywords = {w for w in re.findall(r"[a-zA-Z0-9_]{3,}", query_text.lower()) if w not in stopwords}

    if not keywords:
        return sorted(cone_set)

    scored_nodes = []
    for node in nodes:
        label = str(node.get("label") or "").lower()
        node_id = str(node.get("id") or "").lower()
        file_path = str(node.get("file") or "").lower()

        score = 0
        for kw in keywords:
            if kw in label:
                score += 3
            elif kw in node_id:
                score += 2
            elif kw in file_path:
                score += 1
        if score > 0:
            scored_nodes.append((score, node))

    scored_nodes.sort(key=lambda x: x[0], reverse=True)
    top_nodes = [n for _, n in scored_nodes[:10]]

    node_by_id = {str(n.get("id")): n for n in nodes}
    inbound: dict[str, list[dict]] = {}
    outbound: dict[str, list[dict]] = {}

    for edge in edges:
        src = str(edge.get("source"))
        tgt = str(edge.get("target"))
        if tgt in node_by_id:
            inbound.setdefault(tgt, []).append(node_by_id.get(src, {}))
        if src in node_by_id:
            outbound.setdefault(src, []).append(node_by_id.get(tgt, {}))

    for node in top_nodes:
        f = node.get("file") or ""
        if f:
            first_segment = f.strip().lstrip("./").split("/", 1)[0]
            if first_segment:
                cone_set.add(first_segment)

        nid = str(node.get("id"))
        for neighbor in (inbound.get(nid, []) + outbound.get(nid, []))[:5]:
            nf = neighbor.get("file") or ""
            if nf:
                n_segment = nf.strip().lstrip("./").split("/", 1)[0]
                if n_segment:
                    cone_set.add(n_segment)

    return sorted(cone_set)[:max_dirs]


def create_sparse_cone_worktree(
    repo_root: str,
    worktree_path: str,
    branch: str,
    base_ref: str,
    scoped_paths: Optional[Sequence[str]] = None,
) -> bool:
    """Creates an isolated git worktree configured with cone-mode sparse checkout.

    Lifecycle:
    1. git worktree add --no-checkout <path> -b <branch> <base_ref>
    2. git -C <path> config extensions.worktreeConfig true
    3. git -C <path> sparse-checkout init --cone
    4. git -C <path> sparse-checkout set <cone_dirs...>
    5. git -C <path> checkout <branch>
    """
    repo_root = os.path.abspath(repo_root)
    worktree_path = os.path.abspath(worktree_path)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # 1. Add worktree without materializing files
    add_cmd = ["git", "-C", repo_root, "worktree", "add", "--no-checkout", worktree_path, "-b", branch, base_ref]
    res_add = subprocess.run(add_cmd, capture_output=True, text=True, check=False)
    if res_add.returncode != 0:
        # If branch already exists (e.g. existing tracking branch), try without -b
        add_retry = ["git", "-C", repo_root, "worktree", "add", "--no-checkout", worktree_path, branch]
        res_retry = subprocess.run(add_retry, capture_output=True, text=True, check=False)
        if res_retry.returncode != 0:
            return False

    # 2. Enable worktree-scoped configuration
    res_cfg = subprocess.run(
        ["git", "-C", worktree_path, "config", "extensions.worktreeConfig", "true"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res_cfg.returncode != 0:
        return False

    # 3. Initialize sparse-checkout in cone mode
    res_init = subprocess.run(
        ["git", "-C", worktree_path, "sparse-checkout", "init", "--cone"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res_init.returncode != 0:
        return False

    # 4. Resolve cone directories
    cone_set = set(MANDATORY_SPARSE_CONE_DIRS)
    for p in scoped_paths or []:
        cleaned = p.strip().lstrip("./")
        if not cleaned:
            continue
        first_segment = cleaned.split("/", 1)[0]
        cone_set.add(first_segment)

    set_cmd = ["git", "-C", worktree_path, "sparse-checkout", "set"] + sorted(cone_set)
    res_set = subprocess.run(set_cmd, capture_output=True, text=True, check=False)
    if res_set.returncode != 0:
        return False

    # 5. Checkout the branch to populate the cone
    res_co = subprocess.run(
        ["git", "-C", worktree_path, "checkout", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return res_co.returncode == 0


def ensure_path_in_sparse_cone(worktree_path: str, target_path: str) -> bool:
    """Dynamically adds a target path or directory to an active sparse worktree cone."""
    if not is_sparse_worktree(worktree_path):
        return True

    cleaned = target_path.strip().lstrip("./")
    if not cleaned:
        return True

    res = subprocess.run(
        ["git", "-C", worktree_path, "sparse-checkout", "add", cleaned],
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode == 0
