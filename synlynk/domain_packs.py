"""In-repo versioned domain packs and suggested tool baselines.

Provides capability-neutral lifecycle definitions and tool suggestions for
different industry verticals (Software, Film/Creative Media, Clinical/Biopharma).

Per Binding Amendment 2 (dec-4a53a2ee):
Tool suggestions are strictly baselines and MUST require explicit human confirmation.
No taxonomy lookup or domain pack may grant write authority unconfirmed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DOMAIN_PACKS_DIR = Path(__file__).parent / "domain_packs"


def list_domain_packs() -> list[str]:
    """Return all available domain pack identifiers in-repo."""
    if not _DOMAIN_PACKS_DIR.exists():
        return []
    return sorted(
        p.stem for p in _DOMAIN_PACKS_DIR.glob("*.json") if p.is_file()
    )


def load_domain_pack(domain_id: str) -> dict[str, Any]:
    """Load and parse a domain pack JSON by identifier."""
    target = _DOMAIN_PACKS_DIR / f"{domain_id}.json"
    if not target.exists():
        raise FileNotFoundError(f"Unknown domain pack '{domain_id}' at {target}")
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def get_suggested_tool_baseline(
    domain_id: str,
    archetype_id: str,
    sfia_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve suggested tool baselines for an (archetype, sfia_codes) tuple.

    Per Binding Amendment 2, every returned tool dictionary is strictly flagged
    with requires_confirmation=True and confirmed=False.
    """
    pack = load_domain_pack(domain_id)
    sfia_set = set(sfia_codes or [])
    suggestions = []

    for tool in pack.get("suggested_tools", []):
        match_archetype = tool.get("archetype") == archetype_id
        match_sfia = not tool.get("sfia") or tool.get("sfia") in sfia_set or not sfia_set

        if match_archetype and match_sfia:
            suggestions.append({
                "tool_id": tool["tool_id"],
                "source": tool.get("source", "native_code"),
                "scope_paths": list(tool.get("scope_paths", [])),
                "requires_confirmation": True,
                "confirmed": False,
            })

    return suggestions
