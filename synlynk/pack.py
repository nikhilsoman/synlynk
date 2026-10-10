"""Dynamic task context pack generator using Graphify AST knowledge graph."""

import ast
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
        "during", "after", "before", "into", "does", "what", "where", "which"
    }
    words = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    res = {w for w in words if w not in stopwords}
    return res if res else set(words)


def _get_ast_signature(file_path: str, symbol_name: str) -> Optional[Dict[str, Any]]:
    """Parse Python AST to extract definition line, docstring, and line number."""
    if not os.path.isfile(file_path):
        return None
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=file_path)
    except Exception:
        return None

    name = symbol_name.split("::")[-1].split(".")[-1]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            doc = ast.get_docstring(node) or ""
            lines = content.splitlines()
            start_line = node.lineno
            sig_line = lines[start_line - 1].strip() if 0 < start_line <= len(lines) else f"def {node.name}(...)"
            return {"signature": sig_line, "docstring": doc, "line": start_line}
        elif isinstance(node, ast.ClassDef) and node.name == name:
            doc = ast.get_docstring(node) or ""
            lines = content.splitlines()
            start_line = node.lineno
            sig_line = lines[start_line - 1].strip() if 0 < start_line <= len(lines) else f"class {node.name}:"
            return {"signature": sig_line, "docstring": doc, "line": start_line}
    return None


def extract_symbol_signatures_and_tests(
    repo_root: str,
    symbols: List[str],
) -> Dict[str, Any]:
    """Extract signatures, docstrings, and related test files for a list of symbols."""
    results: Dict[str, Any] = {}
    tests_dir = Path(repo_root) / "tests"

    for sym in symbols:
        file_part = sym.split("::")[0] if "::" in sym else ""
        sym_name = sym.split("::")[-1] if "::" in sym else sym
        abs_file = os.path.join(repo_root, file_part) if file_part else ""

        sig_data = _get_ast_signature(abs_file, sym_name) if abs_file else None
        signature = sig_data["signature"] if sig_data else f"def/class {sym_name}"
        docstring = sig_data["docstring"] if sig_data else ""
        line_num = sig_data["line"] if sig_data else None

        # Discover matching tests
        found_tests: Set[str] = set()
        clean_name = sym_name.split(".")[-1]
        module_name = Path(file_part).stem if file_part else clean_name

        if tests_dir.is_dir():
            for tfile in tests_dir.glob("test_*.py"):
                trel = str(tfile.relative_to(repo_root))
                try:
                    tcontent = tfile.read_text(encoding="utf-8", errors="ignore")
                    if clean_name in tcontent or module_name in tcontent:
                        found_tests.add(trel)
                except Exception:
                    pass

        results[sym] = {
            "signature": signature,
            "docstring": docstring,
            "file": file_part,
            "line": line_num,
            "tests": sorted(found_tests),
        }
    return results


def synthesize_context_pack(
    repo_root: str,
    task_text: str = "",
    story_id: Optional[str] = None,
    token_budget: int = 1500,
) -> str:
    """Synthesize a rich AST context pack for a task or story."""
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
        doc = str(node.get("docstring") or node.get("desc") or "").lower()

        score = 0
        for kw in keywords:
            if kw in label:
                score += 4
            elif kw in node_id:
                score += 3
            elif kw in file_path:
                score += 2
            elif kw in doc:
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

    # Extract primary communities / subsystems
    subsystems: List[str] = []
    seen_subs: Set[str] = set()
    for node in top_nodes:
        comm_name = node.get("community_name")
        if not comm_name:
            file_str = node.get("file", "")
            comm_name = file_str or node.get("label", "Unknown Subsystem")
        if comm_name and comm_name not in seen_subs:
            seen_subs.add(comm_name)
            subsystems.append(comm_name)

    # Collect suggested test targets
    test_files: Set[str] = set()
    for node in top_nodes:
        file_str = node.get("file", "")
        if "test" in file_str:
            test_files.add(file_str)
        nid = str(node.get("id"))
        for caller in inbound.get(nid, []):
            cfile = caller.get("file", "")
            if "test" in cfile:
                test_files.add(cfile)

    lines = [
        "## Task Context Pack (Generated via AST Knowledge Graph)",
        "",
        "### Primary Subsystems & Communities",
    ]
    for sub in subsystems[:4]:
        lines.append(f"- **Subsystem:** `{sub}`")

    lines.append("")
    lines.append("### Target Symbols & Interfaces")
    
    # Extract signatures for top nodes
    sym_ids = [str(n.get("id")) for n in top_nodes]
    extracted_sigs = extract_symbol_signatures_and_tests(repo_root, sym_ids)

    for node in top_nodes:
        nid = str(node.get("id"))
        info = extracted_sigs.get(nid, {})
        label = node.get("label") or node.get("id")
        file_str = node.get("file", "") or info.get("file", "")
        line_num = node.get("line") or info.get("line")
        loc = f"{file_str}:L{line_num}" if line_num else file_str
        loc_str = f" [{loc}]" if loc else ""
        sig = info.get("signature") or node.get("signature")
        doc = info.get("docstring") or node.get("docstring") or node.get("desc")

        if sig:
            lines.append(f"- `{sig}`{loc_str}")
        else:
            lines.append(f"- `{label}`{loc_str}")

        if doc:
            first_line = doc.strip().split("\n", 1)[0][:140]
            lines.append(f"  *{first_line}*")

        callers = inbound.get(nid, [])
        if callers:
            lines.append("  - Inbound Callers:")
            for c in callers[:5]:
                clabel = c.get("label") or c.get("id")
                cfile = c.get("file", "")
                cline = c.get("line")
                cloc = f"{cfile}:L{cline}" if cline else cfile
                cloc_str = f" [{cloc}]" if cloc else ""
                lines.append(f"    - `{clabel}`{cloc_str}")

        callees = outbound.get(nid, [])
        if callees:
            lines.append("  - Dependencies / Callees:")
            for d in callees[:5]:
                dlabel = d.get("label") or d.get("id")
                dfile = d.get("file", "")
                dline = d.get("line")
                dloc = f"{dfile}:L{dline}" if dline else dfile
                dloc_str = f" [{dloc}]" if dloc else ""
                lines.append(f"    - `{dlabel}`{dloc_str}")

        # Add tests found for this symbol
        for tf in info.get("tests", []):
            test_files.add(tf)

    if test_files:
        lines.append("")
        lines.append("### Suggested Verification Test Targets")
        for tf in sorted(test_files)[:5]:
            lines.append(f"- `pytest {tf}`")

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
