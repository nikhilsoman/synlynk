"""Maintainer's CLI/TUI fence-hint contributor (spec §5.7, part 3). Surfaces
a one-line hint after any `synlynk exec`/`synlynk maintainer ...` invocation
when a pending proposal or dry-run finding exists -- the terminal-side
notification surface for people not looking at Vizor.
"""
import json
import os

from synlynk.fencing import FenceData, register_hint_contributor


def _pending_proposal_count(repo_root: str = ".") -> int:
    path = os.path.join(repo_root, ".synlynk", "proposals.json")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        proposals = data.get("proposals") or []
        return sum(1 for p in proposals if p.get("source", "").startswith("maintainer:"))
    except (json.JSONDecodeError, OSError):
        return 0


def maintainer_fence_hint_contributor(data: FenceData) -> None:
    count = _pending_proposal_count()
    if count > 0:
        label = "proposal" if count == 1 else "proposals"
        data.hints.append(f"{count} maintainer {label} pending review in Proposal Studio")


register_hint_contributor(maintainer_fence_hint_contributor)
