"""Small, conservative helpers for append-only markdown rebases."""

import ast
from dataclasses import dataclass, field
import os
import re
import subprocess
from typing import Optional, List, Dict, Tuple, Any, Set


MARKDOWN_INDEX_PATHS = (
    "docs/blog/README.md",
    "project-docs/memory.md",
    "CHANGELOG.md",
)
_CONFLICT = re.compile(r"^<<<<<<< .*$", re.M)
_PR_NUMBER = re.compile(r"(?:PR|#)(\d+)", re.I)


def _merge_markdown_conflict(text: str) -> Optional[str]:
    """Resolve conflict blocks by preserving unique lines in stable order."""
    if not _CONFLICT.search(text):
        return None
    lines = text.splitlines(keepends=True)
    output = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<<"):
            output.append(lines[i]); i += 1; continue
        ours, theirs = [], []
        i += 1
        target = ours
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            if lines[i].startswith("======="):
                target = theirs
            else:
                target.append(lines[i])
            i += 1
        if i >= len(lines):
            return None
        combined = []
        for line in ours + theirs:
            if line not in combined:
                combined.append(line)
        if any("|" in line for line in combined):
            header = [line for line in combined if line.lstrip().startswith("|") and "---" in line]
            body = [line for line in combined if line not in header]
            body.sort(key=lambda line: int(_PR_NUMBER.search(line).group(1)) if _PR_NUMBER.search(line) else 10**9)
            combined = body[:1] + header + body[1:] if header else body
        output.extend(combined)
        i += 1
    return "".join(output)


def auto_rebase_markdown_conflicts(repo_path: str, branch: str, target_branch: str = "main") -> bool:
    """Merge target into *branch* when all conflicts are supported markdown appends."""
    def run(*args):
        return subprocess.run(["git", "-C", repo_path, *args], text=True,
                              capture_output=True, check=False)

    if run("fetch", "origin", target_branch).returncode != 0:
        return False
    merge = run("merge", "--no-edit", f"origin/{target_branch}")
    if merge.returncode == 0:
        return True
    status = run("status", "--porcelain").stdout.splitlines()
    conflicted = [line[3:] for line in status if line.startswith("UU ")]
    if not conflicted or any(path not in MARKDOWN_INDEX_PATHS for path in conflicted):
        run("merge", "--abort")
        return False
    for path in conflicted:
        full = os.path.join(repo_path, path)
        with open(full, encoding="utf-8") as handle:
            resolved = _merge_markdown_conflict(handle.read())
        if resolved is None:
            run("merge", "--abort"); return False
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(resolved)
    if run("add", "--", *conflicted).returncode != 0:
        run("merge", "--abort"); return False
    return run("commit", "-m", "merge: auto-rebase markdown index").returncode == 0


@dataclass
class SpeculativeRebaseNode:
    """Represents a node in a speculative rebase tree for concurrent agent branches."""
    node_id: str
    base_sha: str
    applied_branches: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending" | "speculative_merged" | "verified" | "conflict"
    conflict_details: Optional[dict] = None
    test_command: Optional[str] = None
    pre_verified: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class BranchInterference:
    """Analysis of commutativity and interference between two concurrent branches."""
    branch_a: str
    branch_b: str
    classification: str  # "disjoint" | "ast_compatible" | "semantic_conflict"
    overlapping_files: List[str] = field(default_factory=list)
    conflicting_symbols: List[str] = field(default_factory=list)
    auto_resolvable: bool = False
    details: dict = field(default_factory=dict)


def compute_branch_interference(
    branch_a_name: str,
    branch_b_name: str,
    branch_a_files: List[str],
    branch_b_files: List[str],
    branch_a_symbols: Optional[dict] = None,
    branch_b_symbols: Optional[dict] = None,
) -> BranchInterference:
    """Determine pairwise commutativity and conflict classification between two branches."""
    overlap = sorted(list(set(branch_a_files) & set(branch_b_files)))
    if not overlap:
        return BranchInterference(
            branch_a=branch_a_name,
            branch_b=branch_b_name,
            classification="disjoint",
            overlapping_files=[],
            conflicting_symbols=[],
            auto_resolvable=True,
            details={"reason": "Disjoint file sets; branches commute strictly."},
        )

    conflicting = []
    if branch_a_symbols and branch_b_symbols:
        for file_path in overlap:
            syms_a = set(branch_a_symbols.get(file_path, []))
            syms_b = set(branch_b_symbols.get(file_path, []))
            sym_overlap = syms_a & syms_b
            if sym_overlap:
                conflicting.extend(sorted(list(sym_overlap)))

    if conflicting:
        return BranchInterference(
            branch_a=branch_a_name,
            branch_b=branch_b_name,
            classification="semantic_conflict",
            overlapping_files=overlap,
            conflicting_symbols=conflicting,
            auto_resolvable=False,
            details={"reason": f"Overlapping modifications to symbols: {conflicting}"},
        )

    return BranchInterference(
        branch_a=branch_a_name,
        branch_b=branch_b_name,
        classification="ast_compatible",
        overlapping_files=overlap,
        conflicting_symbols=[],
        auto_resolvable=True,
        details={"reason": "Files overlap but changes operate on distinct AST nodes."},
    )


def extract_python_ast_symbols(source_code: str) -> dict:
    """Extract top-level AST declarations, symbols, and imports from Python code."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return {"error": str(exc), "symbols": {}, "imports": []}

    symbols = {}
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = {
                "type": "function",
                "lineno": getattr(node, "lineno", 0),
                "end_lineno": getattr(node, "end_lineno", 0),
                "args": [arg.arg for arg in node.args.args],
                "docstring": ast.get_docstring(node),
            }
        elif isinstance(node, ast.ClassDef):
            methods = [
                m.name for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            symbols[node.name] = {
                "type": "class",
                "lineno": getattr(node, "lineno", 0),
                "end_lineno": getattr(node, "end_lineno", 0),
                "methods": methods,
                "docstring": ast.get_docstring(node),
            }
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols[target.id] = {
                        "type": "assignment",
                        "lineno": getattr(node, "lineno", 0),
                        "end_lineno": getattr(node, "end_lineno", 0),
                    }
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"module": alias.name, "asname": alias.asname})
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append({"module": mod, "name": alias.name, "asname": alias.asname})

    return {"symbols": symbols, "imports": imports}


def ast_3way_merge_python(base_src: str, ours_src: str, theirs_src: str) -> Tuple[Optional[str], dict]:
    """Perform a 3-way AST semantic merge on Python source code (Ours + Theirs relative to Base).

    Resolves:
    - Independent top-level function/class additions
    - Non-conflicting import unions and deduplications
    - Non-conflicting symbol modifications

    Returns (merged_source, metadata). If unresolvable syntactic conflict exists, returns (None, metadata).
    """
    try:
        base_ast = ast.parse(base_src)
        ours_ast = ast.parse(ours_src)
        theirs_ast = ast.parse(theirs_src)
    except SyntaxError as exc:
        return None, {"error": f"Syntax error during AST parse: {exc}", "resolvable": False}

    def split_body(tree: ast.Module):
        imports = []
        declarations = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)
            else:
                declarations.append(node)
        return imports, declarations

    base_imp, base_decl = split_body(base_ast)
    ours_imp, ours_decl = split_body(ours_ast)
    theirs_imp, theirs_decl = split_body(theirs_ast)

    # 1. Merge Imports (Set union of imported names, preserving canonical structure)
    merged_imports = []
    seen_imports = set()

    for imp_node in base_imp + ours_imp + theirs_imp:
        dump = ast.dump(imp_node)
        if dump not in seen_imports:
            seen_imports.add(dump)
            merged_imports.append(imp_node)

    # 2. Merge Declarations
    merged_declarations = []
    ours_by_name = {}
    for node in ours_decl:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ours_by_name[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            ours_by_name[node.targets[0].id] = node

    theirs_by_name = {}
    for node in theirs_decl:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            theirs_by_name[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            theirs_by_name[node.targets[0].id] = node

    base_by_name = {}
    for node in base_decl:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            base_by_name[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            base_by_name[node.targets[0].id] = node

    all_names = list(dict.fromkeys(list(base_by_name.keys()) + list(ours_by_name.keys()) + list(theirs_by_name.keys())))
    conflicts = []

    for name in all_names:
        in_base = name in base_by_name
        in_ours = name in ours_by_name
        in_theirs = name in theirs_by_name

        if in_ours and in_theirs:
            ours_dump = ast.dump(ours_by_name[name])
            theirs_dump = ast.dump(theirs_by_name[name])
            base_dump = ast.dump(base_by_name[name]) if in_base else None

            if ours_dump == theirs_dump:
                merged_declarations.append(ours_by_name[name])
            elif in_base:
                if ours_dump == base_dump:
                    merged_declarations.append(theirs_by_name[name])
                elif theirs_dump == base_dump:
                    merged_declarations.append(ours_by_name[name])
                else:
                    conflicts.append(name)
            else:
                conflicts.append(name)
        elif in_ours and not in_theirs:
            if in_base:
                base_dump = ast.dump(base_by_name[name])
                ours_dump = ast.dump(ours_by_name[name])
                if ours_dump != base_dump:
                    conflicts.append(name)
            else:
                merged_declarations.append(ours_by_name[name])
        elif in_theirs and not in_ours:
            if in_base:
                base_dump = ast.dump(base_by_name[name])
                theirs_dump = ast.dump(theirs_by_name[name])
                if theirs_dump != base_dump:
                    conflicts.append(name)
            else:
                merged_declarations.append(theirs_by_name[name])

    for node in ours_decl:
        if not hasattr(node, "name") and not (isinstance(node, ast.Assign) and isinstance(getattr(node, "targets", [None])[0], ast.Name)):
            if ast.dump(node) not in [ast.dump(n) for n in merged_declarations]:
                merged_declarations.append(node)
    for node in theirs_decl:
        if not hasattr(node, "name") and not (isinstance(node, ast.Assign) and isinstance(getattr(node, "targets", [None])[0], ast.Name)):
            if ast.dump(node) not in [ast.dump(n) for n in merged_declarations]:
                merged_declarations.append(node)

    if conflicts:
        return None, {
            "resolvable": False,
            "conflicts": conflicts,
            "reason": f"Semantic/AST conflict on declarations: {conflicts}",
        }

    new_module = ast.Module(body=merged_imports + merged_declarations, type_ignores=[])
    try:
        ast.fix_missing_locations(new_module)
        merged_code = ast.unparse(new_module)
        ast.parse(merged_code)
        return merged_code, {
            "resolvable": True,
            "merged_declarations": len(merged_declarations),
            "merged_imports": len(merged_imports),
            "conflicts": [],
        }
    except Exception as exc:
        return None, {"resolvable": False, "error": f"Failed to unparse or validate merged AST: {exc}"}
