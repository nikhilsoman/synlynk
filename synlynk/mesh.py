"""Federated knowledge mesh aggregator and sibling worktree AST conflict preemption engine."""

import ast
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple


# ============================================================================
# 1. Multi-Repo Knowledge Mesh Aggregation
# ============================================================================

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


# ============================================================================
# 2. AST Mesh Worktree Conflict Preemption Engine
# ============================================================================

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class AstSymbolInfo:
    name: str
    symbol_type: str  # "function" | "async_function" | "class" | "method" | "assignment" | "import"
    start_line: int
    end_line: int
    parent: Optional[str] = None
    docstring: Optional[str] = None


def extract_file_ast_symbols(source_code: str) -> List[AstSymbolInfo]:
    """Extract fine-grained AST symbols including classes, methods, and functions."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    symbols: List[AstSymbolInfo] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stype = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
            symbols.append(AstSymbolInfo(
                name=node.name,
                symbol_type=stype,
                start_line=getattr(node, "lineno", 1),
                end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                docstring=ast.get_docstring(node),
            ))
        elif isinstance(node, ast.ClassDef):
            c_start = getattr(node, "lineno", 1)
            c_end = getattr(node, "end_lineno", c_start)
            symbols.append(AstSymbolInfo(
                name=node.name,
                symbol_type="class",
                start_line=c_start,
                end_line=c_end,
                docstring=ast.get_docstring(node),
            ))
            # Extract methods inside class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mtype = "async_method" if isinstance(item, ast.AsyncFunctionDef) else "method"
                    m_start = getattr(item, "lineno", c_start)
                    m_end = getattr(item, "end_lineno", m_start)
                    symbols.append(AstSymbolInfo(
                        name=f"{node.name}.{item.name}",
                        symbol_type=mtype,
                        start_line=m_start,
                        end_line=m_end,
                        parent=node.name,
                        docstring=ast.get_docstring(item),
                    ))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append(AstSymbolInfo(
                        name=target.id,
                        symbol_type="assignment",
                        start_line=getattr(node, "lineno", 1),
                        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                    ))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append(AstSymbolInfo(
                    name=alias.name,
                    symbol_type="import",
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                ))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                full = f"{mod}.{alias.name}" if mod else alias.name
                symbols.append(AstSymbolInfo(
                    name=full,
                    symbol_type="import",
                    start_line=getattr(node, "lineno", 1),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                ))

    return symbols


def parse_diff_line_ranges(diff_text: str) -> Dict[str, List[Tuple[int, int]]]:
    """Parse git unified diff output into file paths and modified line ranges in the new file."""
    file_ranges: Dict[str, List[Tuple[int, int]]] = {}
    current_file = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/"):].strip()
            if current_file not in file_ranges:
                file_ranges[current_file] = []
        elif line.startswith("@@ ") and current_file:
            match = _HUNK_RE.match(line)
            if match:
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) is not None else 1
                if new_count == 0:
                    # Deletion point
                    file_ranges[current_file].append((new_start, new_start))
                else:
                    file_ranges[current_file].append((new_start, new_start + new_count - 1))

    return file_ranges


def map_diff_to_ast_symbols(
    source_code: str,
    line_ranges: List[Tuple[int, int]],
) -> List[Dict[str, Any]]:
    """Determine which AST symbols intersect with modified line ranges."""
    symbols = extract_file_ast_symbols(source_code)
    if not symbols:
        return []

    modified_symbols = []
    seen_symbol_names = set()

    for r_start, r_end in line_ranges:
        matched = False
        # First check fine-grained methods / functions / assignments
        for sym in symbols:
            # Check overlap between [sym.start_line, sym.end_line] and [r_start, r_end]
            if max(sym.start_line, r_start) <= min(sym.end_line, r_end):
                if sym.name not in seen_symbol_names:
                    seen_symbol_names.add(sym.name)
                    modified_symbols.append({
                        "name": sym.name,
                        "type": sym.symbol_type,
                        "start_line": sym.start_line,
                        "end_line": sym.end_line,
                        "parent": sym.parent,
                    })
                matched = True

        if not matched:
            # Modification outside named symbols (module body / top-level constants / comments)
            anon_name = f"module:L{r_start}-L{r_end}"
            if anon_name not in seen_symbol_names:
                seen_symbol_names.add(anon_name)
                modified_symbols.append({
                    "name": anon_name,
                    "type": "module_scope",
                    "start_line": r_start,
                    "end_line": r_end,
                })

    return modified_symbols


def get_worktree_modified_symbols(
    worktree_path: str,
    base_ref: str = "main",
) -> Dict[str, Any]:
    """Inspect a worktree directory and extract all modified files and AST symbols."""
    worktree_dir = Path(worktree_path).resolve()
    if not worktree_dir.is_dir():
        return {"path": worktree_path, "branch": "unknown", "files": {}, "error": "Directory missing"}

    # Get active branch name
    branch_res = subprocess.run(
        ["git", "-C", str(worktree_dir), "branch", "--show-current"],
        capture_output=True, text=True, check=False,
    )
    branch = branch_res.stdout.strip() or "(detached)"

    # Determine base ref for diff
    diff_args = ["git", "-C", str(worktree_dir), "diff", "-U0", f"{base_ref}...HEAD"]
    diff_res = subprocess.run(diff_args, capture_output=True, text=True, check=False)

    if diff_res.returncode != 0:
        diff_args = ["git", "-C", str(worktree_dir), "diff", "-U0", "HEAD"]
        diff_res = subprocess.run(diff_args, capture_output=True, text=True, check=False)

    # Also capture uncommitted (staged/unstaged) diff
    uncommitted_res = subprocess.run(
        ["git", "-C", str(worktree_dir), "diff", "-U0", "HEAD"],
        capture_output=True, text=True, check=False,
    )

    combined_diff = diff_res.stdout + "\n" + uncommitted_res.stdout
    file_ranges = parse_diff_line_ranges(combined_diff)

    file_symbols: Dict[str, List[Dict[str, Any]]] = {}

    for rel_path, ranges in file_ranges.items():
        abs_file = worktree_dir / rel_path
        if abs_file.is_file() and rel_path.endswith(".py"):
            try:
                code = abs_file.read_text(errors="ignore")
                symbols = map_diff_to_ast_symbols(code, ranges)
                file_symbols[rel_path] = symbols
            except Exception:
                file_symbols[rel_path] = [{"name": "file_level", "type": "raw", "start_line": 1, "end_line": 1}]
        else:
            file_symbols[rel_path] = [{"name": "file_level", "type": "non_python", "start_line": 1, "end_line": 1}]

    return {
        "path": str(worktree_dir),
        "branch": branch,
        "files": file_symbols,
    }


def detect_worktree_ast_conflicts(
    repo_root: str = ".",
    worktrees: Optional[List[str]] = None,
    base_ref: str = "main",
) -> Dict[str, Any]:
    """Detect AST collisions and blast radius interference across sibling worktrees."""
    root_dir = Path(repo_root).resolve()

    discovered_worktrees: List[str] = []
    if worktrees:
        discovered_worktrees = [str(Path(w).resolve()) for w in worktrees]
    else:
        # Discover worktrees via git
        res = subprocess.run(
            ["git", "-C", str(root_dir), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if line.startswith("worktree "):
                    wpath = line[len("worktree "):].strip()
                    discovered_worktrees.append(wpath)

    # Collect modifications per worktree
    wt_data: List[Dict[str, Any]] = []
    for wt in discovered_worktrees:
        data = get_worktree_modified_symbols(wt, base_ref=base_ref)
        if data.get("files"):
            wt_data.append(data)

    conflicts: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    compatible: List[Dict[str, Any]] = []

    # Pairwise comparison
    for i in range(len(wt_data)):
        for j in range(i + 1, len(wt_data)):
            wt_a = wt_data[i]
            wt_b = wt_data[j]

            files_a = set(wt_a["files"].keys())
            files_b = set(wt_b["files"].keys())
            overlapping_files = sorted(list(files_a & files_b))

            if not overlapping_files:
                continue

            for fpath in overlapping_files:
                syms_a = {s["name"]: s for s in wt_a["files"].get(fpath, [])}
                syms_b = {s["name"]: s for s in wt_b["files"].get(fpath, [])}

                shared_symbols = sorted(list(set(syms_a.keys()) & set(syms_b.keys())))

                if shared_symbols:
                    conflicts.append({
                        "severity": "CRITICAL",
                        "file": fpath,
                        "worktree_a": wt_a["path"],
                        "branch_a": wt_a["branch"],
                        "worktree_b": wt_b["path"],
                        "branch_b": wt_b["branch"],
                        "conflicting_symbols": shared_symbols,
                        "recommendation": (
                            f"Serialize merge order: Merge {wt_a['branch']} first, "
                            f"then rebase {wt_b['branch']} to resolve '{', '.join(shared_symbols)}'."
                        ),
                    })
                else:
                    # Files overlap but modified AST symbols are disjoint
                    compatible.append({
                        "severity": "INFO",
                        "file": fpath,
                        "worktree_a": wt_a["path"],
                        "branch_a": wt_a["branch"],
                        "worktree_b": wt_b["path"],
                        "branch_b": wt_b["branch"],
                        "symbols_a": list(syms_a.keys()),
                        "symbols_b": list(syms_b.keys()),
                        "recommendation": "Disjoint AST symbol edits in same file. Commits should commute cleanly.",
                    })

    overall_status = "CLEAN"
    if conflicts:
        overall_status = "CONFLICT"
    elif warnings:
        overall_status = "WARNING"

    return {
        "status": overall_status,
        "analyzed_worktrees": len(wt_data),
        "worktrees": wt_data,
        "critical_conflicts": conflicts,
        "warnings": warnings,
        "ast_compatible": compatible,
    }


def cmd_multirepo_mesh(args) -> int:
    """CLI handler for `synlynk mesh`."""
    check_conflicts = getattr(args, "conflicts", False) or getattr(args, "overlap", False)
    as_json = getattr(args, "json", False)

    if check_conflicts:
        repo_root = getattr(args, "repo_root", ".") or "."
        worktrees_arg = getattr(args, "worktrees", None)
        worktrees = [w.strip() for w in worktrees_arg.split(",") if w.strip()] if worktrees_arg else None
        base_ref = getattr(args, "base", "main") or "main"
        fail_on_conflict = getattr(args, "fail_on_conflict", False)

        report = detect_worktree_ast_conflicts(repo_root=repo_root, worktrees=worktrees, base_ref=base_ref)

        if as_json:
            print(json.dumps(report, indent=2))
            return 1 if (fail_on_conflict and report["status"] == "CONFLICT") else 0

        print("\n🔍 AST Mesh Worktree Conflict Preemption Report:")
        print(f"  Status: {'🟢 CLEAN' if report['status'] == 'CLEAN' else '🔴 CONFLICT' if report['status'] == 'CONFLICT' else '🟡 WARNING'}")
        print(f"  Active worktrees analyzed: {report['analyzed_worktrees']}")

        if report["critical_conflicts"]:
            print(f"\n  🚨 CRITICAL AST Symbol Collisions ({len(report['critical_conflicts'])}):")
            for c in report["critical_conflicts"]:
                print(f"    - File: {c['file']}")
                print(f"      Branch A: {c['branch_a']} ({Path(c['worktree_a']).name})")
                print(f"      Branch B: {c['branch_b']} ({Path(c['worktree_b']).name})")
                print(f"      Colliding Symbols: {', '.join(c['conflicting_symbols'])}")
                print(f"      💡 Recommendation: {c['recommendation']}")

        if report["ast_compatible"]:
            print(f"\n  ✅ AST-Compatible Concurrent Edits ({len(report['ast_compatible'])}):")
            for comp in report["ast_compatible"]:
                print(f"    - File: {comp['file']}")
                print(f"      Branch A: {comp['branch_a']} -> {', '.join(comp['symbols_a'][:3])}")
                print(f"      Branch B: {comp['branch_b']} -> {', '.join(comp['symbols_b'][:3])}")
                print(f"      Status: Disjoint AST symbols (Parallel-safe)")

        if not report["critical_conflicts"] and not report["ast_compatible"]:
            print("  No overlapping modified files or AST symbol collisions across active worktrees.")

        print()
        if fail_on_conflict and report["status"] == "CONFLICT":
            return 1
        return 0

    # Default: Federated knowledge mesh aggregation
    repo_args = getattr(args, "repos", None)
    repos = []
    if repo_args:
        repos = [r.strip() for r in repo_args.split(",") if r.strip()]
    else:
        # Check current repo and common parent workspaces
        cwd = Path.cwd()
        repos.append(str(cwd))
        parent = cwd.parent
        for child in parent.iterdir():
            if child.is_dir() and (child / ".synlynk").is_dir() and str(child) not in repos:
                repos.append(str(child))

    merged = merge_fleet_graphs(repos)
    inferred = infer_cross_repo_edges(merged)
    merged["edges"].extend(inferred)

    output_path = getattr(args, "output", None)
    saved_path = write_global_graph(merged, output_path=output_path)

    if as_json:
        print(json.dumps(merged, indent=2))
        return 0

    print(f"\n🌐 Federated Knowledge Mesh Synthesized:")
    print(f"  Repositories aggregated: {len(repos)}")
    print(f"  Total nodes: {len(merged['nodes'])}")
    print(f"  Total edges: {len(merged['edges'])} ({len(inferred)} cross-repo inferred)")
    print(f"  Persisted to: {saved_path}\n")
    return 0
