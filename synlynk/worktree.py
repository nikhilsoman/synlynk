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
