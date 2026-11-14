"""Synlynk Constitution & Charter Governance (Normative Law Layer).

Formalizes the four Asimov Laws (0-3) and the Intent-Based Engineering invariant
into canonical code-level data structures and API queries per spec
docs/superpowers/specs/2026-11-13-synlynk-constitution-charter-governance-design.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class DeliveryTier(str, Enum):
    """Delivery Tier of a constitutional law or invariant."""
    PROSE = "prose"        # Tier 1: Mentioned in instruction/charter text only
    CITED = "cited"        # Tier 2: Citation tag checked by drift-gate
    INJECTED = "injected"  # Tier 3: Injected into generated session bearings block


@dataclass(frozen=True)
class ConstitutionLaw:
    """Canonical representation of a constitutional law or invariant."""
    id: str
    number: Optional[int]
    name: str
    summary: str
    tier: DeliveryTier
    enforcement_mechanism: str


CONSTITUTION_LAWS: Dict[str, ConstitutionLaw] = {
    "law-0": ConstitutionLaw(
        id="law-0",
        number=0,
        name="Secrets & System Integrity",
        summary="No artifact, harness output, or dispatched job may expose secrets, credentials, or system-integrity-breaking content.",
        tier=DeliveryTier.INJECTED,
        enforcement_mechanism="Forbidden pattern matching in evaluate_asimov_invariants() and preflight scanner.",
    ),
    "law-1": ConstitutionLaw(
        id="law-1",
        number=1,
        name="Human Sovereignty & App Identity",
        summary="Every dispatched unit of work carries required role attribution back to an accountable identity; no anonymous or personal-token action.",
        tier=DeliveryTier.INJECTED,
        enforcement_mechanism="Required role attribution check and Hardened PR Review Policy GitHub App token isolation.",
    ),
    "law-2": ConstitutionLaw(
        id="law-2",
        number=2,
        name="Evidence Over Assertions",
        summary="A claim of completion, verification, or success must be backed by directly-checked evidence (diff, test run, gh pr view), never inferred from status labels or self-report.",
        tier=DeliveryTier.INJECTED,
        enforcement_mechanism="Non-author QA verification checks, synlynk pr check, and PR review discipline.",
    ),
    "law-3": ConstitutionLaw(
        id="law-3",
        number=3,
        name="Metered Self-Preservation",
        summary="Autonomous execution is cost-bounded; token and financial circuit-breakers gate dispatch readiness and demote repeating failures.",
        tier=DeliveryTier.CITED,
        enforcement_mechanism="Token circuit breakers, prompt estimate ceiling (200k ceiling), and 2x-consecutive failure stall demotion.",
    ),
    "intent-invariant": ConstitutionLaw(
        id="intent-invariant",
        number=None,
        name="Intent-Based Engineering Invariant",
        summary="Every unit of dispatched work traces to a captured human intent (a GOVERNS goal/story), never to an un-sourced ad hoc instruction.",
        tier=DeliveryTier.CITED,
        enforcement_mechanism="100% GOVERNS adherence gate on dispatch and PR check.",
    ),
}

_CITATION_PATTERN = re.compile(r"<!--\s*constitution:\s*([a-zA-Z0-9_\-]+)\s*-->")


def get_law(law_id: str) -> Optional[ConstitutionLaw]:
    """Look up a constitutional law by ID or numeric alias (case-insensitive)."""
    if not law_id:
        return None
    key = str(law_id).strip().lower()
    if key in CONSTITUTION_LAWS:
        return CONSTITUTION_LAWS[key]
    
    # Handle numeric alias, e.g. "0" -> "law-0"
    if key.isdigit():
        num_key = f"law-{key}"
        if num_key in CONSTITUTION_LAWS:
            return CONSTITUTION_LAWS[num_key]

    return None


def list_laws() -> List[ConstitutionLaw]:
    """Return all canonical constitutional laws in order."""
    return list(CONSTITUTION_LAWS.values())


def validate_citation_tag(text: str) -> Optional[str]:
    """Extract and validate constitutional citation tag from text.
    
    Returns the valid law_id if found and registered, else None.
    """
    if not text:
        return None
    match = _CITATION_PATTERN.search(text)
    if not match:
        return None
    raw_id = match.group(1).lower()
    law = get_law(raw_id)
    return law.id if law else None
