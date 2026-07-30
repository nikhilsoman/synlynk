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


def _classify_worktree(
    entry: WorktreeEntry,
    worktree_missing: bool,
    is_dirty: bool,
    dirty_summary: str,
    is_ancestor: bool,
    gh_available: bool,
    pr_info,
    net_diff_lines,
    commits_ahead: int,
) -> WorktreeVerdict:
    """Pure classifier — rules 1-3 of the spec's ordered algorithm (dirty
    override → ancestor check → PR state). Takes pre-fetched git/gh signals
    as arguments; does not shell out itself."""
    if worktree_missing:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "worktree directory missing — stale registration", entry.nested_under,
        )
    if is_dirty:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"dirty: {dirty_summary}", entry.nested_under,
        )
    if is_ancestor:
        return WorktreeVerdict(
            entry.path, entry.branch, "safe",
            "merged, direct ancestor", entry.nested_under,
        )
    if not gh_available:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            "could not verify PR state — gh unavailable", entry.nested_under,
        )
    if pr_info is None:
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
        )

    state = pr_info.get("state")
    number = pr_info.get("number")
    if state == "MERGED":
        return WorktreeVerdict(
            entry.path, entry.branch, "safe", f"PR #{number} merged", entry.nested_under,
        )
    if state == "CLOSED":
        net = net_diff_lines if net_diff_lines is not None else 0
        if net <= 0:
            return WorktreeVerdict(
                entry.path, entry.branch, "safe",
                f"PR #{number} closed, stale — no unique content vs main", entry.nested_under,
            )
        return WorktreeVerdict(
            entry.path, entry.branch, "needs-review",
            f"PR #{number} closed, {net} net lines of unmerged content", entry.nested_under,
        )
    if state == "OPEN":
        return WorktreeVerdict(
            entry.path, entry.branch, "unsafe", f"PR #{number} open — active work", entry.nested_under,
        )
    return WorktreeVerdict(
        entry.path, entry.branch, "needs-review",
        f"no PR found, {commits_ahead} commits ahead of main", entry.nested_under,
    )
