"""Static guard: nothing outside db_schema.py/roadmap_identity.py persists
roadmap_arcs.id / roadmap_phases.id as a stored identity (gh:#5443 item 3).
This is an allowlist-based grep, not a full SQL parser: it flags any
non-allowlisted source line that looks like it is storing (INSERT/UPDATE
SET col = id) the positional id from roadmap_arcs/roadmap_phases
into another table or an external API payload. Purely-local, same-request
ordering uses (ORDER BY id, dry-run display counts) are not flagged because
they don't persist anything.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SUSPECT_PATTERN = re.compile(r"roadmap_(arcs|phases)\.id\b")

# (file, line substring) pairs that are known-safe and reviewed:
# ordering/display only, never persisted.
_ALLOWLIST = {
    ("synlynk/gh_sync_backfill.py", "ORDER BY id ASC"),
    ("synlynk/gh_sync_cli.py", "ORDER BY id ASC"),
}


def test_no_new_code_persists_roadmap_positional_id():
    offenders = []
    for path in (_REPO_ROOT / "synlynk").rglob("*.py"):
        rel = str(path.relative_to(_REPO_ROOT))
        if rel in {"synlynk/db_schema.py", "synlynk/roadmap_identity.py"}:
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not _SUSPECT_PATTERN.search(line):
                continue
            if any(rel == f and substr in line for f, substr in _ALLOWLIST):
                continue
            offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "found code outside db_schema.py/roadmap_identity.py referencing "
        "roadmap_arcs.id/roadmap_phases.id; use arc_uid/phase_uid (see "
        "synlynk/roadmap_identity.py) or add a reviewed allowlist entry if "
        "this is genuinely display/ordering-only:\n" + "\n".join(offenders)
    )
