"""synlynk worktree: audit and clean up stale git worktrees/branches."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class WorktreeEntry:
    path: str
    branch: str
    nested_under: Optional[str] = None


@dataclass
class WorktreeVerdict:
    path: str
    branch: str
    verdict: str  # "safe" | "needs-review" | "unsafe"
    reason: str
    nested_under: Optional[str] = None


def _parse_worktree_porcelain(text: str) -> list:
    """Parses `git worktree list --porcelain` output into raw dicts."""
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                entries.append(current)
            current = {"path": line[len("worktree "):].strip(), "branch": None, "bare": False}
        elif current is None:
            continue
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            current["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line.startswith("bare"):
            current["bare"] = True
    if current is not None:
        entries.append(current)
    return entries


def _is_subpath(child: str, parent: str) -> bool:
    child_r = os.path.realpath(child)
    parent_r = os.path.realpath(parent)
    return child_r != parent_r and child_r.startswith(parent_r + os.sep)


def _build_worktree_entries(raw_entries: list, main_repo_path: str, cwd_worktree_path: str) -> list:
    """Excludes the main repo checkout and cwd's own worktree, then computes nesting."""
    filtered = []
    for raw in raw_entries:
        path = raw.get("path")
        if not path or raw.get("bare"):
            continue
        if os.path.realpath(path) == os.path.realpath(main_repo_path):
            continue
        if os.path.realpath(path) == os.path.realpath(cwd_worktree_path):
            continue
        filtered.append(WorktreeEntry(path=path, branch=raw.get("branch") or ""))

    for entry in filtered:
        candidates = [other for other in filtered if _is_subpath(entry.path, other.path)]
        if candidates:
            parent = max(candidates, key=lambda o: len(o.path))
            entry.nested_under = parent.path

    return filtered
