"""Dynamic task context pack generator using Graphify AST knowledge graph."""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Set


def _cut_to_token_budget(text: str, token_budget: int = 1500) -> str:
    """Bound text payload to token budget (approx 4 chars per token)."""
    max_chars = token_budget * 4
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit("\n", 1)[0]
    return f"{truncated}\n\n[Context truncated to {token_budget} token budget]"


def _extract_keywords(text: str) -> Set[str]:
    """Extract search tokens from task description."""
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "when",
        "during", "after", "before", "error", "issue", "fix", "add",
        "update", "test", "into", "does", "what", "where", "which"
    }
    words = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    return {w for w in words if w not in stopwords}


def synthesize_context_pack(
    repo_root: str,
    task_text: str = "",
    story_id: Optional[str] = None,
    token_budget: int = 1500,
) -> str:
    """Synthesize a compact 1-hop AST context pack for a task or story."""
    graph_path = Path(repo_root) / ".synlynk" / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        return ""

    try:
        data = json.loads(graph_path.read_text(errors="ignore"))
    except Exception:
        return ""

    nodes = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (data.get("edges") or data.get("links") or []) if isinstance(e, dict)]

    if not nodes:
        return ""

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

    keywords = _extract_keywords(query_text)
    if not keywords and not task_text:
        return ""

    # Score nodes by keyword matches
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
    top_nodes = [n for _, n in scored_nodes[:8]]

    if not top_nodes:
        return ""

    # Build caller and callee maps
    inbound: Dict[str, List[dict]] = {}
    outbound: Dict[str, List[dict]] = {}
    node_by_id = {str(n.get("id")): n for n in nodes}

    for edge in edges:
        src = str(edge.get("source"))
        tgt = str(edge.get("target"))
        if tgt in node_by_id:
            inbound.setdefault(tgt, []).append(node_by_id.get(src, {"label": src, "file": ""}))
        if src in node_by_id:
            outbound.setdefault(src, []).append(node_by_id.get(tgt, {"label": tgt, "file": ""}))

    lines = ["## Task Context Pack (Generated via Knowledge Graph)", "Target Symbols:"]
    for node in top_nodes:
        label = node.get("label") or node.get("id")
        file_str = node.get("file", "")
        line_num = node.get("line")
        loc = f"{file_str}:L{line_num}" if line_num else file_str
        loc_str = f" [{loc}]" if loc else ""
        lines.append(f"- {label}{loc_str}")

        nid = str(node.get("id"))
        callers = inbound.get(nid, [])
        if callers:
            lines.append("  - Callers:")
            for c in callers[:5]:
                clabel = c.get("label") or c.get("id")
                cfile = c.get("file", "")
                cline = c.get("line")
                cloc = f"{cfile}:L{cline}" if cline else cfile
                cloc_str = f" [{cloc}]" if cloc else ""
                lines.append(f"    - {clabel}{cloc_str}")

        callees = outbound.get(nid, [])
        if callees:
            lines.append("  - Dependencies / Callees:")
            for d in callees[:5]:
                dlabel = d.get("label") or d.get("id")
                dfile = d.get("file", "")
                dline = d.get("line")
                dloc = f"{dfile}:L{dline}" if dline else dfile
                dloc_str = f" [{dloc}]" if dloc else ""
                lines.append(f"    - {dlabel}{dloc_str}")

    result = "\n".join(lines)
    return _cut_to_token_budget(result, token_budget=token_budget)


def cmd_pack(args) -> int:
    """CLI handler for `synlynk pack <query-or-story>`."""
    target = getattr(args, "target", None) or ""
    repo_root = getattr(args, "repo_root", ".") or "."
    story_id = target if target.startswith("story-") else None
    task_text = "" if story_id else target

    pack = synthesize_context_pack(
        repo_root=repo_root,
        task_text=task_text,
        story_id=story_id,
        token_budget=getattr(args, "budget", 1500) or 1500,
    )
    if not pack:
        print("No matching knowledge graph symbols found or graphify index not present.")
        return 0
    print(pack)
    return 0
