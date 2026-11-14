"""Bearings Card Generator & Ingestion Layer (Approach C - Hybrid Generation).

Generates the single-sourced, byte-identical constitutional session bearings block
injected into context/prompts per spec docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md
and gh:#5233.
"""

from __future__ import annotations

import re
from synlynk.constitution import CONSTITUTION_LAWS, DeliveryTier


BEARINGS_START_MARKER = "<!-- synlynk:bearings:start -->"
BEARINGS_END_MARKER = "<!-- synlynk:bearings:end -->"
_BEARINGS_RE = re.compile(
    rf"{re.escape(BEARINGS_START_MARKER)}.*?{re.escape(BEARINGS_END_MARKER)}",
    re.DOTALL,
)


def generate_bearings_block() -> str:
    """Generate the canonical session bearings block from Tier 3 constitutional laws."""
    law0 = CONSTITUTION_LAWS["law-0"]
    law1 = CONSTITUTION_LAWS["law-1"]
    law2 = CONSTITUTION_LAWS["law-2"]

    lines = [
        BEARINGS_START_MARKER,
        "## Session Bearings & Constitutional Invariants (Tier 3 - Injected)",
        f"<!-- constitution: {law0.id} -->",
        f"- **Law 0 ({law0.name}):** No credential leaks, personal tokens, or un-isolated file modifications. Zero secrets in prompt/commit history.",
        f"<!-- constitution: {law1.id} -->",
        f"- **Law 1 ({law1.name}):** Every dispatch requires role attribution (`--as-agent <role>`). Use GitHub App identity (`synlynk gh --role <role> -- ...`), never personal GitHub credentials.",
        f"<!-- constitution: {law2.id} -->",
        f"- **Law 2 ({law2.name}):** Evidence over assertions. Run direct verification commands (`synlynk pr check`, `pytest`, `gh pr view --json`) and inspect exit codes before claiming completion or passing status.",
        "- **Operational Discipline:**",
        "  - Session wake/sweep: Keep background daemons alive with `tpm wake` / `tpm sweep`.",
        "  - Review findings: PR findings require a dispatched reviewer agent, never an ad hoc manual menu.",
        BEARINGS_END_MARKER,
    ]
    return "\n".join(lines)


def inject_bearings_block(text: str) -> str:
    """Inject or replace the canonical bearings block in target prompt/context text."""
    block = generate_bearings_block()
    if _BEARINGS_RE.search(text):
        return _BEARINGS_RE.sub(block, text)

    # Insert after title header or at the top
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("# "):
        header = lines[0]
        rest = "".join(lines[1:])
        return f"{header}\n{block}\n\n{rest.lstrip()}"
    return f"{block}\n\n{text}"
