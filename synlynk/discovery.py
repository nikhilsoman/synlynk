import ast
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


def _is_graphify_installed() -> bool:
    try:
        from synlynk.tool_installer import is_tool_available
        return is_tool_available("graphify")
    except Exception:
        return shutil.which("graphify") is not None


def _get_head_commit(repo_root: str) -> str:
    try:
        res = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=2,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def _read_graphify_manifest(repo_root: str) -> Optional[Dict[str, Any]]:
    manifest_path = Path(repo_root) / ".synlynk" / "graphify-out" / "manifest.json"
    if manifest_path.is_file():
        try:
            return json.loads(manifest_path.read_text(errors="ignore"))
        except Exception:
            return None
    return None


def scan_workspace_static(repo_root: str) -> Dict[str, Any]:
    """Execute <10s offline AST and package manifest scan across 3 dimensions."""
    t0 = time.time()
    root = Path(repo_root)

    languages = set()
    frameworks = set()
    routes = []
    entities = []

    # Check manifests
    if (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file():
        languages.add("Python")
        manifest_text = ""
        if (root / "pyproject.toml").is_file():
            manifest_text += (root / "pyproject.toml").read_text(errors="ignore")
        if (root / "requirements.txt").is_file():
            manifest_text += (root / "requirements.txt").read_text(errors="ignore")
        if "fastapi" in manifest_text.lower():
            frameworks.add("FastAPI")
        if "django" in manifest_text.lower():
            frameworks.add("Django")

    if (root / "package.json").is_file():
        languages.add("TypeScript" if list(root.glob("**/*.ts")) else "JavaScript")
        try:
            pkg = json.loads((root / "package.json").read_text(errors="ignore"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                frameworks.add("Next.js")
            if "react" in deps:
                frameworks.add("React")
        except Exception:
            pass

    # AST scan python files for routes
    for py_path in list(root.glob("*.py"))[:50]:
        try:
            tree = ast.parse(py_path.read_text(errors="ignore"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                            if dec.func.attr in ("get", "post", "put", "delete"):
                                if dec.args and isinstance(dec.args[0], ast.Constant):
                                    routes.append({"method": dec.func.attr.upper(), "path": dec.args[0].value, "file": py_path.name})
        except Exception:
            pass

    kg_section: Dict[str, Any] = {"available": False}
    if _is_graphify_installed():
        manifest = _read_graphify_manifest(str(root))
        if manifest:
            head_commit = _get_head_commit(str(root))
            built_at = str(manifest.get("built_at_commit") or "")
            stale = bool(head_commit and built_at and head_commit != built_at)
            kg_section = {
                "available": True,
                "stale": stale,
                "built_at_commit": built_at,
                "nodes_count": manifest.get("nodes_count", 0),
                "edges_count": manifest.get("edges_count", 0),
                "communities_count": manifest.get("communities_count", 0),
            }

    scan_ms = int((time.time() - t0) * 1000)
    return {
        "scan_time_ms": scan_ms,
        "domain": {"industry": "Developer Tooling", "inferred_function": "Application Service"},
        "physical": {
            "languages": sorted(list(languages)) if languages else ["Unknown"],
            "frameworks": sorted(list(frameworks)),
        },
        "logical": {
            "routes": routes,
            "entities": entities,
        },
        "knowledge_graph": kg_section,
    }

