"""Document Sidecar Knowledge Graph for synlynk (v0.32.1).

Extracts and indexes markdown documents across the workspace (specs, plans,
decisions, project-docs, guides) into an AST-aware knowledge graph persisted at
.synlynk/docgraph.json. Provides reverse code-to-doc lookups for sub-3k context packaging.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class DocumentNode:
    path: str
    title: str
    doc_type: str
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    headers: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    code_references: List[str] = field(default_factory=list)
    issues_and_prs: List[int] = field(default_factory=list)
    sha256: str = ""
    line_count: int = 0


@dataclass
class DocGraph:
    schema_version: str = "1.0"
    built_at: str = ""
    built_at_commit: str = ""
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    reverse_code_index: Dict[str, List[str]] = field(default_factory=dict)
    reverse_doc_index: Dict[str, List[str]] = field(default_factory=dict)
    broken_links: List[Dict[str, Any]] = field(default_factory=list)
    orphaned_specs: List[str] = field(default_factory=list)

    def get_docs_for_code(self, code_path: str) -> List[str]:
        """Return relative document paths referencing the given code file."""
        norm = code_path.strip().lstrip("/")
        return sorted(self.reverse_code_index.get(norm, []))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_yaml_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter delimited by leading '---'. Returns (dict, body_text)."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_yaml = parts[1]
    body = parts[2]

    # Try standard yaml if available, otherwise robust line-by-line fallback
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw_yaml)
        if isinstance(parsed, dict):
            return parsed, body
    except Exception:
        pass

    result: Dict[str, Any] = {}
    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if val.startswith("[") and val.endswith("]"):
                items = [item.strip().strip("\"'") for item in val[1:-1].split(",") if item.strip()]
                result[key] = items
            elif val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            else:
                result[key] = val
    return result, body


def classify_doc_type(rel_path: str) -> str:
    """Classify markdown document by directory or filename convention."""
    norm = rel_path.replace("\\", "/").lower()
    base = os.path.basename(norm)

    if "docs/superpowers/specs/" in norm or norm.startswith("specs/"):
        return "spec"
    if "docs/superpowers/plans/" in norm or norm.startswith("plans/"):
        return "plan"
    if "project-docs/decisions/" in norm or "decisions/" in norm:
        return "decision"
    if "project-docs/devlogs/" in norm or "devlogs/" in norm:
        return "devlog"
    if base == "roadmap.md" or "roadmap" in base:
        return "roadmap"
    if base == "todo.md":
        return "todo"
    if base == "costs.md":
        return "costs"
    if base == "memory.md":
        return "memory"
    if base == "readme.md":
        return "readme"
    if base == "changelog.md":
        return "changelog"
    if "guide" in norm or "tutorial" in norm:
        return "guide"
    if "strategy" in norm:
        return "strategy"
    if "blog" in norm:
        return "blog"
    return "general_doc"


def extract_document_node(file_path: str, repo_root: str) -> DocumentNode:
    """Analyze a single markdown document and extract structural metadata."""
    abs_path = os.path.abspath(file_path if os.path.isabs(file_path) else os.path.join(repo_root, file_path))
    rel_path = os.path.relpath(abs_path, repo_root).replace("\\", "/")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return DocumentNode(path=rel_path, title="", doc_type=classify_doc_type(rel_path))

    frontmatter, body = parse_yaml_frontmatter(content)
    lines = content.splitlines()

    # Extract title: frontmatter title > first H1 (# Title) > filename
    title = str(frontmatter.get("title") or "")
    headers: List[str] = []
    if not title:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            headers.append(stripped)

    if not title:
        title = Path(rel_path).stem.replace("-", " ").replace("_", " ").title()

    # Extract links: [text](target)
    links: List[str] = []
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        target = match.group(2).strip()
        if target and not target.startswith("#"):
            links.append(target)

    # Extract backticked code and file references
    code_refs: Set[str] = set()
    code_ext_pattern = re.compile(r"^[a-zA-Z0-9_\-\./]+\.(py|js|ts|tsx|jsx|json|md|sh|toml|yaml|yml|rs|go|c|h|cpp)$")
    for match in re.finditer(r"`([^`]+)`", content):
        token = match.group(1).strip()
        if code_ext_pattern.match(token) and not token.startswith("http"):
            code_refs.add(token.lstrip("/"))
        elif "/" in token and not token.startswith("http") and not token.startswith("`"):
            code_refs.add(token.lstrip("/"))

    # Extract issue and PR numbers (#1234, gh:#1234, PR #1234)
    issues_and_prs: Set[int] = set()
    for match in re.finditer(r"(?:#|gh:#|PR\s*#)(\d+)", content, re.IGNORECASE):
        try:
            issues_and_prs.add(int(match.group(1)))
        except ValueError:
            pass

    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    doc_type = classify_doc_type(rel_path)

    return DocumentNode(
        path=rel_path,
        title=title,
        doc_type=doc_type,
        frontmatter=frontmatter,
        headers=headers,
        links=links,
        code_references=sorted(code_refs),
        issues_and_prs=sorted(issues_and_prs),
        sha256=sha256,
        line_count=len(lines),
    )


def _find_markdown_files(repo_root: str) -> List[str]:
    """Discover all non-ignored markdown files in the repository."""
    skip_dirs = {
        ".git",
        ".synlynk",
        ".worktrees",
        "node_modules",
        "venv",
        ".venv",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
    }
    md_files: List[str] = []
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))
    return md_files


def build_docgraph(repo_root: str, output_path: Optional[str] = None) -> DocGraph:
    """Build the full Document Sidecar Knowledge Graph for the workspace."""
    repo_root = os.path.abspath(repo_root)
    files = _find_markdown_files(repo_root)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    reverse_code_index: Dict[str, List[str]] = {}
    reverse_doc_index: Dict[str, List[str]] = {}
    broken_links: List[Dict[str, Any]] = []

    # 1. Parse all document nodes
    for fpath in files:
        node = extract_document_node(fpath, repo_root)
        nodes[node.path] = asdict(node)

    # 2. Build edges and cross-indices
    for doc_path, data in nodes.items():
        doc_dir = os.path.dirname(os.path.join(repo_root, doc_path))

        # Index code references
        for code_ref in data.get("code_references", []):
            reverse_code_index.setdefault(code_ref, []).append(doc_path)
            edges.append({
                "source": doc_path,
                "target": code_ref,
                "type": "references_code",
            })

        # Index document links
        for link in data.get("links", []):
            if link.startswith("http://") or link.startswith("https://") or link.startswith("mailto:"):
                continue

            clean_link = link.split("#")[0].strip()
            if not clean_link:
                continue

            # Resolve relative link target
            target_abs = os.path.normpath(os.path.join(doc_dir, clean_link))
            target_rel = os.path.relpath(target_abs, repo_root).replace("\\", "/")

            if os.path.exists(target_abs):
                if target_rel in nodes:
                    reverse_doc_index.setdefault(target_rel, []).append(doc_path)
                    edges.append({
                        "source": doc_path,
                        "target": target_rel,
                        "type": "links_to_doc",
                    })
                else:
                    edges.append({
                        "source": doc_path,
                        "target": target_rel,
                        "type": "links_to_file",
                    })
            else:
                broken_links.append({
                    "source": doc_path,
                    "target": link,
                    "resolved_target": target_rel,
                })

    # 3. Identify orphaned specs (specs with no incoming doc links and no parent_goal)
    orphaned_specs: List[str] = []
    for doc_path, data in nodes.items():
        if data.get("doc_type") == "spec":
            incoming = reverse_doc_index.get(doc_path, [])
            parent_goal = data.get("frontmatter", {}).get("parent_goal")
            if not incoming and not parent_goal:
                orphaned_specs.append(doc_path)

    # 4. Resolve HEAD commit if available
    head_sha = ""
    try:
        from synlynk.scan import _read_git_head_commit_direct

        head_sha = _read_git_head_commit_direct(repo_root)
    except Exception:
        pass

    graph = DocGraph(
        schema_version="1.0",
        built_at=datetime.now(timezone.utc).isoformat(),
        built_at_commit=head_sha,
        nodes=nodes,
        edges=edges,
        reverse_code_index=reverse_code_index,
        reverse_doc_index=reverse_doc_index,
        broken_links=broken_links,
        orphaned_specs=sorted(orphaned_specs),
    )

    if output_path is None:
        output_path = os.path.join(repo_root, ".synlynk", "docgraph.json")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, indent=2)

    return graph
