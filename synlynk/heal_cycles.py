"""Cycle detection and automated refactoring story generator using Graphify AST graph."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple


def _normalize_cycle(cycle: List[str]) -> Tuple[str, ...]:
    """Rotate cycle so the lexicographically smallest element is first."""
    if not cycle:
        return ()
    min_idx = cycle.index(min(cycle))
    rotated = cycle[min_idx:] + cycle[:min_idx]
    return tuple(rotated)


def detect_import_cycles(repo_root: str = ".") -> List[List[str]]:
    """Detect elementary cycles in the dependency/import graph."""
    graph_path = Path(repo_root) / ".synlynk" / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        return []

    try:
        data = json.loads(graph_path.read_text(errors="ignore"))
    except Exception:
        return []

    nodes = [n for n in (data.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (data.get("edges") or data.get("links") or []) if isinstance(e, dict)]

    if not nodes or not edges:
        return []

    # Build directed adjacency list
    adj: Dict[str, List[str]] = {}
    for node in nodes:
        nid = str(node.get("id") or "")
        if nid:
            adj.setdefault(nid, [])

    for edge in edges:
        src = str(edge.get("source") or "")
        tgt = str(edge.get("target") or "")
        if src and tgt and src != tgt:
            adj.setdefault(src, []).append(tgt)

    # DFS cycle detector with recursion stack
    discovered_cycles: Set[Tuple[str, ...]] = set()
    visited: Set[str] = set()
    rec_stack: List[str] = []
    stack_set: Set[str] = set()

    def dfs(u: str):
        visited.add(u)
        rec_stack.append(u)
        stack_set.add(u)

        for v in adj.get(u, []):
            if v in stack_set:
                # Cycle detected from v to u
                cycle_start = rec_stack.index(v)
                cycle = rec_stack[cycle_start:]
                if len(cycle) >= 2:
                    discovered_cycles.add(_normalize_cycle(cycle))
            elif v not in visited:
                dfs(v)

        rec_stack.pop()
        stack_set.remove(u)

    for node_id in sorted(list(adj.keys())):
        if node_id not in visited:
            dfs(node_id)

    # Return sorted list of cycle lists
    sorted_cycles = [list(c) for c in sorted(discovered_cycles)]
    return sorted_cycles


def _create_story_safe(
    title: str,
    description: str,
    criteria: str,
    role: str = "architect",
    story_type: str = "tech-debt",
    priority: str = "p1",
) -> Optional[str]:
    """Create a refactoring story in state.db safely."""
    try:
        from synlynk.db import create_story
        return create_story(
            title=title,
            description=description,
            criteria=criteria,
            role=role,
            story_type=story_type,
            priority=priority,
        )
    except Exception:
        try:
            from synlynk import _get_db
            import uuid
            conn = _get_db()
            story_id = f"story-cycle-{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO stories (story_id, title, description, criteria, status, priority) "
                "VALUES (?, ?, ?, ?, 'ready', ?)",
                (story_id, title, description, criteria, priority),
            )
            conn.commit()
            conn.close()
            return story_id
        except Exception:
            return None


def heal_import_cycles(repo_root: str = ".", create_stories: bool = True) -> List[Dict[str, Any]]:
    """Detect circular dependencies and optionally create remediation stories."""
    cycles = detect_import_cycles(repo_root)
    results = []

    for cycle in cycles:
        cycle_str = " -> ".join(cycle) + f" -> {cycle[0]}"
        title = f"Refactor circular dependency between {cycle[0]} and {cycle[1]}"
        description = (
            f"Automated architectural finding via Graphify AST:\n"
            f"Detected dependency cycle:\n`{cycle_str}`\n\n"
            f"Circular dependencies degrade testability, hinder lazy loading, and risk runtime import errors."
        )
        criteria = (
            f"- Break the import cycle between {', '.join(cycle)}\n"
            f"- Extract shared types/interfaces to a common module or apply dependency inversion\n"
            f"- Verify clean import with `synlynk heal --cycles`"
        )

        story_id = None
        if create_stories:
            story_id = _create_story_safe(
                title=title,
                description=description,
                criteria=criteria,
                role="architect",
                story_type="tech-debt",
                priority="p1",
            )

        results.append({
            "cycle": cycle,
            "cycle_path": cycle_str,
            "title": title,
            "story_id": story_id,
        })

    return results


def cmd_heal_cycles(args) -> int:
    """CLI handler for `synlynk heal --cycles`."""
    repo_root = getattr(args, "repo_root", ".") or "."
    create_stories = getattr(args, "create_stories", True)

    results = heal_import_cycles(repo_root=repo_root, create_stories=create_stories)
    if not results:
        print("✓ No import or dependency cycles detected in knowledge graph.")
        return 0

    print(f"\n⚠ Found {len(results)} circular dependency cycle(s):")
    for idx, item in enumerate(results, 1):
        print(f"\n[{idx}] {item['cycle_path']}")
        print(f"    Title: {item['title']}")
        if item.get("story_id"):
            print(f"    Remediation Story Created: {item['story_id']}")

    print("\nRun `synlynk story list` to inspect remediation stories.")
    return 0
