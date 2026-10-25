"""Bookkeeping vs code path classification for the CI test workflow.

A changeset is bookkeeping-only when every changed file is in the exempt
set from the v0.25.5 CI stabilization spec. ``docs/superpowers/**`` and
``README.md`` are intentionally not exempt: specs govern architecture, and
the README test-count gate has to run when that file changes.
"""
from __future__ import annotations

# Closed exempt set. Anything else, including other markdown, runs the suite.
_EXEMPT_EXACT = frozenset(
    {
        "CHANGELOG.md",
        ".gitattributes",
        ".gitignore",
        "roadmap.md",
        "todo.md",
        ".synlynk/config.json",
    }
)

_EXEMPT_PREFIXES = (
    "project-docs/",
    "docs/blog/",
    "docs/brainstorm/",
)


def is_bookkeeping_path(path: str) -> bool:
    """Return whether one repo-relative path is exempt bookkeeping."""
    normalized = str(path).strip().replace("\\", "/")
    if not normalized or normalized in {".", "/"}:
        return False
    if normalized in _EXEMPT_EXACT:
        return True
    return any(normalized.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def is_bookkeeping_only(changed_files) -> bool:
    """Return whether every changed path is bookkeeping.

    An empty list is not bookkeeping-only: a missing diff must run the suite.
    """
    files = [str(path) for path in changed_files if str(path).strip()]
    if not files:
        return False
    return all(is_bookkeeping_path(path) for path in files)
