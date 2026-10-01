"""Multi-pass topology discovery engine for Synlynk onboarding.

Discovers and classifies workspace candidates across 4 archetypes:
1. Monorepo
2. Standalone Repo
3. Polyrepo Application Group
4. Multi-Project Container (e.g. ~/dev)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ARCHETYPE_MONOREPO = "monorepo"
ARCHETYPE_STANDALONE = "standalone"
ARCHETYPE_POLYREPO = "polyrepo_group"
ARCHETYPE_CONTAINER = "multi_project_container"

_MONOREPO_MANIFESTS = (
    "pnpm-workspace.yaml",
    "turbo.json",
    "nx.json",
    "go.work",
    "lerna.json",
)

_EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "vendor",
    ".cache",
    ".synlynk",
    "__pycache__",
    "dist",
    "build",
}


def _find_git_roots(target_path: Path, max_depth: int = 3) -> List[Path]:
    roots: List[Path] = []
    target_path = target_path.resolve()

    if (target_path / ".git").is_dir():
        roots.append(target_path)
        return roots

    def _scan(current: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            if not entry.is_dir() or entry.name in _EXCLUDED_DIRS:
                continue
            if (entry / ".git").is_dir():
                roots.append(entry.resolve())
            else:
                _scan(entry, depth + 1)

    _scan(target_path, 1)
    return sorted(roots, key=lambda p: str(p))


def _is_monorepo(root: Path) -> bool:
    if any((root / f).is_file() for f in _MONOREPO_MANIFESTS):
        return True
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            if "workspaces" in data:
                return True
        except Exception:
            pass
    cargo_toml = root / "Cargo.toml"
    if cargo_toml.is_file():
        try:
            text = cargo_toml.read_text(encoding="utf-8")
            if "[workspace]" in text:
                return True
        except Exception:
            pass
    return False


def compute_affinity(repo_a: Path, repo_b: Path) -> float:
    """Compute pairwise affinity score between two repository roots.
    Score >= 1.0 indicates strong polyrepo coupling.
    """
    score = 0.0
    parent_a = repo_a.parent
    parent_b = repo_b.parent

    # Check for shared parent orchestrator (docker-compose, Tiltfile, etc.)
    if parent_a == parent_b:
        compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"]
        for cf in compose_files:
            compose_path = parent_a / cf
            if compose_path.is_file():
                try:
                    content = compose_path.read_text(encoding="utf-8")
                    if repo_a.name in content and repo_b.name in content:
                        score += 1.5  # Strong signal
                except Exception:
                    pass

    # Check for name prefix similarity (e.g. myapp-web, myapp-api)
    parts_a = repo_a.name.split("-")
    parts_b = repo_b.name.split("-")
    if len(parts_a) > 1 and len(parts_b) > 1 and parts_a[0] == parts_b[0]:
        score += 0.4  # Medium signal

    # Check for cross-repo relative path references
    try:
        for p in (repo_a / "package.json", repo_a / "go.mod", repo_a / "requirements.txt"):
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="ignore")
                if f"../{repo_b.name}" in text:
                    score += 1.2
    except Exception:
        pass

    return score


def classify_archetype(target_path: Path, git_roots: List[Path]) -> Tuple[str, List[Dict[str, Any]]]:
    if not git_roots:
        return ARCHETYPE_STANDALONE, [{
            "slug": target_path.name or "workspace",
            "primary_repo": str(target_path.resolve()),
            "repos": [str(target_path.resolve())],
            "archetype": ARCHETYPE_STANDALONE,
            "greenfield": True,
        }]

    if len(git_roots) == 1 and git_roots[0] == target_path:
        if _is_monorepo(target_path):
            return ARCHETYPE_MONOREPO, [{
                "slug": target_path.name,
                "primary_repo": str(target_path.resolve()),
                "repos": [str(target_path.resolve())],
                "archetype": ARCHETYPE_MONOREPO,
                "greenfield": False,
            }]
        return ARCHETYPE_STANDALONE, [{
            "slug": target_path.name,
            "primary_repo": str(target_path.resolve()),
            "repos": [str(target_path.resolve())],
            "archetype": ARCHETYPE_STANDALONE,
            "greenfield": False,
        }]

    # Multiple git roots found. Check for polyrepo application clustering.
    clusters: List[List[Path]] = []
    unclustered = list(git_roots)

    while unclustered:
        seed = unclustered.pop(0)
        cluster = [seed]
        to_remove = []
        for other in unclustered:
            if compute_affinity(seed, other) >= 1.0:
                cluster.append(other)
                to_remove.append(other)
        for r in to_remove:
            unclustered.remove(r)
        clusters.append(cluster)

    workspaces = []
    if len(clusters) == 1 and len(clusters[0]) > 1:
        overall_archetype = ARCHETYPE_POLYREPO
        cluster = clusters[0]
        workspaces.append({
            "slug": target_path.name,
            "primary_repo": str(cluster[0].resolve()),
            "repos": [str(r.resolve()) for r in cluster],
            "archetype": ARCHETYPE_POLYREPO,
            "greenfield": False,
        })
    elif any(len(c) > 1 for c in clusters):
        overall_archetype = ARCHETYPE_CONTAINER
        for c in clusters:
            if len(c) > 1:
                workspaces.append({
                    "slug": c[0].parent.name if c[0].parent != target_path else c[0].name,
                    "primary_repo": str(c[0].resolve()),
                    "repos": [str(r.resolve()) for r in c],
                    "archetype": ARCHETYPE_POLYREPO,
                    "greenfield": False,
                })
            else:
                workspaces.append({
                    "slug": c[0].name,
                    "primary_repo": str(c[0].resolve()),
                    "repos": [str(c[0].resolve())],
                    "archetype": ARCHETYPE_STANDALONE,
                    "greenfield": False,
                })
    else:
        overall_archetype = ARCHETYPE_CONTAINER
        for r in git_roots:
            workspaces.append({
                "slug": r.name,
                "primary_repo": str(r.resolve()),
                "repos": [str(r.resolve())],
                "archetype": ARCHETYPE_STANDALONE,
                "greenfield": False,
            })

    return overall_archetype, workspaces


def discover_topology(target_path_str: str, max_depth: int = 3) -> Dict[str, Any]:
    target_path = Path(target_path_str).resolve()
    git_roots = _find_git_roots(target_path, max_depth=max_depth)
    archetype, workspaces = classify_archetype(target_path, git_roots)

    return {
        "target_path": str(target_path),
        "archetype": archetype,
        "git_roots_count": len(git_roots),
        "workspaces": workspaces,
    }


def merge_candidate_workspaces(
    candidate_plan: Dict[str, Any],
    workspace_slugs: List[str],
    new_slug: str,
    primary_repo: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    workspaces = plan.get("workspaces", [])
    merged_repos = []
    remaining = []

    for ws in workspaces:
        if ws["slug"] in workspace_slugs:
            merged_repos.extend(ws.get("repos", []))
        else:
            remaining.append(ws)

    # Dedup repos
    merged_repos = sorted(list(set(merged_repos)))
    merged_ws = {
        "slug": new_slug,
        "primary_repo": primary_repo,
        "repos": merged_repos,
        "archetype": ARCHETYPE_POLYREPO,
        "greenfield": False,
    }
    remaining.insert(0, merged_ws)
    plan["workspaces"] = remaining
    return plan


def split_candidate_workspace(
    candidate_plan: Dict[str, Any],
    workspace_slug: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    workspaces = plan.get("workspaces", [])
    result_workspaces = []

    for ws in workspaces:
        if ws["slug"] == workspace_slug and len(ws.get("repos", [])) > 1:
            for repo_path in ws["repos"]:
                r_name = Path(repo_path).name
                result_workspaces.append({
                    "slug": r_name,
                    "primary_repo": repo_path,
                    "repos": [repo_path],
                    "archetype": ARCHETYPE_STANDALONE,
                    "greenfield": False,
                })
        else:
            result_workspaces.append(ws)

    plan["workspaces"] = result_workspaces
    return plan


def designate_primary_repo(
    candidate_plan: Dict[str, Any],
    workspace_slug: str,
    primary_repo: str,
) -> Dict[str, Any]:
    plan = json.loads(json.dumps(candidate_plan))
    for ws in plan.get("workspaces", []):
        if ws["slug"] == workspace_slug:
            if primary_repo in ws.get("repos", []):
                ws["primary_repo"] = primary_repo
    return plan
