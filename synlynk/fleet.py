"""Fleet operability helpers: Core 4 instruction files, nested state.db, doctor hard-fail."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Sequence

from synlynk._constants import CORE_FLEET, CORE_INSTRUCTION_FILES


def check_core_instruction_files(
    root: str | Path, agents: Iterable[str] | None = None
) -> List[str]:
    """Return core agent names whose instruction files are missing under root."""
    root = Path(root)
    agents = list(agents) if agents is not None else sorted(CORE_FLEET)
    missing = []
    for agent in agents:
        if agent not in CORE_FLEET:
            continue
        rel = CORE_INSTRUCTION_FILES.get(agent)
        if not rel:
            continue
        if not (root / rel).is_file():
            missing.append(agent)
    return missing


def find_nested_product_state_dbs(root: str | Path) -> List[str]:
    """Paths under worktrees that look like product ledgers (not intentional empty)."""
    root = Path(root)
    hits = []
    for base in ("worktrees", ".worktrees", ".claude/worktrees"):
        d = root / base
        if not d.is_dir():
            continue
        for p in d.rglob("state.db"):
            parts = set(p.parts)
            if ".synlynk" in parts or p.parent.name == ".synlynk":
                hits.append(str(p))
    return hits


def is_nested_worktree_state_path(path: str) -> bool:
    """True if path sits under a job/feature worktree layout (not canonical home)."""
    norm = os.path.abspath(path).replace("\\", "/")
    return any(seg in norm for seg in ("/worktrees/", "/.worktrees/", "/.claude/worktrees/"))


def assert_not_nested_product_ledger(path: str, *, home_writable: bool) -> None:
    """Refuse product ledger under worktrees when the home canonical path is usable."""
    if home_writable and is_nested_worktree_state_path(path):
        raise RuntimeError(
            f"nested product state.db refused ({path}); "
            "use canonical ~/.synlynk/projects/<key>/state.db"
        )


def doctor_hard_fail(
    *,
    tc_results: dict,
    missing_instructions: Sequence[str],
    nested_state_dbs: Sequence[str],
) -> bool:
    """True if doctor should exit non-zero for Core fail-closed conditions.

    TC-5 is intentionally ignored for hard fail (warn-only).
    """
    if missing_instructions or nested_state_dbs:
        return True
    if not tc_results.get("tc2", True):
        return True
    if not tc_results.get("tc3", True):
        return True
    return False
