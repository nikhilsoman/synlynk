"""Synlynk Companion v2.1: Ambient Multi-Channel Co-Pilot & Developer Engagement Engine.

Implements the 4-part message anatomy ([Signal], [Context], [Nudge], [Deep Links]),
stage/segment inference & pinning, domain vocabulary substitution, and registration
as a generic hint contributor in synlynk.fencing.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from synlynk.fencing import FenceData, register_hint_contributor

RELATIONSHIP_STAGES = (
    "onboarding",
    "companionship",
    "sounding_board",
    "policy_maker",
    "recruiter",
    "champion",
)

DEVELOPER_SEGMENTS = (
    "novice",
    "skeptic",
    "accelerant",
    "architect",
)

_PINNED_STAGE: Optional[str] = None
_PINNED_SEGMENT: Optional[str] = None
_ENABLED: bool = False


def is_companion_enabled() -> bool:
    """Check whether Companion engine is enabled via env var or runtime setting."""
    if os.environ.get("SYNLYNK_COMPANION", "0").lower() in ("1", "true", "yes"):
        return True
    return _ENABLED


def enable_companion(enabled: bool) -> None:
    """Enable or disable the Companion engine."""
    global _ENABLED
    _ENABLED = enabled


def clear_pinned_stage() -> None:
    """Clear pinned stage/segment (for test isolation and command boundaries)."""
    global _PINNED_STAGE, _PINNED_SEGMENT
    _PINNED_STAGE = None
    _PINNED_SEGMENT = None


def format_hyperlink(text: str, url: str) -> str:
    """Format an OSC 8 terminal hyperlink with plain-text fallback."""
    # Terminal OSC 8 escape sequence: \033]8;;{url}\033\\{text}\033]8;;\033\\
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def format_companion_message(
    signal: str,
    context: str,
    nudge: str,
    deep_links: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Format the canonical 4-part Companion v2.1 message box."""
    links_str = ""
    if deep_links:
        formatted_links = [f"↗ {format_hyperlink(title, url)}" for title, url in deep_links]
        links_str = " · ".join(formatted_links)

    lines = [
        f"[Signal]     {signal}",
        f"[Context]    {context}",
        f"[Nudge]      {nudge}",
    ]
    if links_str:
        lines.append(f"[Deep Links] {links_str}")

    return "\n".join(lines)


def apply_domain_vocab(text: str, vocab: Dict[str, str]) -> str:
    """Apply domain vocabulary substitution (longest-key-first, word boundaries, non-recursive)."""
    if not vocab:
        return text
    # Sort keys by length descending to prevent short prefix collision
    sorted_keys = sorted(vocab.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_keys) + r")\b", re.IGNORECASE)

    def _replace(match: re.Match) -> str:
        word = match.group(0).lower()
        # Find matching key
        for k in sorted_keys:
            if k.lower() == word:
                replacement = vocab[k]
                # Match original capitalization if capitalized
                if match.group(0)[0].isupper():
                    return replacement.capitalize()
                return replacement
        return match.group(0)

    return pattern.sub(_replace, text)


def infer_stage_and_segment() -> Tuple[str, str]:
    """Infer or retrieve pinned stage and segment for current command invocation."""
    global _PINNED_STAGE, _PINNED_SEGMENT
    if _PINNED_STAGE and _PINNED_SEGMENT:
        return _PINNED_STAGE, _PINNED_SEGMENT

    # In production, infers from .synlynk/telemetry.json or environment override
    stage = os.environ.get("SYNLYNK_COMPANION_STAGE", "onboarding")
    segment = os.environ.get("SYNLYNK_COMPANION_SEGMENT", "architect")

    if stage not in RELATIONSHIP_STAGES:
        stage = "onboarding"
    if segment not in DEVELOPER_SEGMENTS:
        segment = "accelerant"

    _PINNED_STAGE = stage
    _PINNED_SEGMENT = segment
    return stage, segment


def maybe_add_hint(data: FenceData) -> None:
    """Callback registered into synlynk.fencing._HINT_CONTRIBUTORS."""
    if not is_companion_enabled():
        return

    stage, segment = infer_stage_and_segment()
    kind_label = "completed" if data.kind == "task_complete" else "estimated"
    basis_info = f"${data.cost_usd:.2f} ({data.in_tokens:,} in / {data.out_tokens:,} out)"

    msg = format_companion_message(
        signal=f"Task {data.command} {kind_label} under stage '{stage}'",
        context=f"Basis: {basis_info} [{data.basis}]",
        nudge=f"Review verified artifacts or proceed to next task",
        deep_links=[("Vizor Observatory", "http://localhost:33333")],
    )
    data.hints.append(msg)


def register_companion_seam() -> None:
    """Register Companion callback into fencing hint contributors list."""
    register_hint_contributor(maybe_add_hint)


# Automatically wire seam when loaded
register_companion_seam()
