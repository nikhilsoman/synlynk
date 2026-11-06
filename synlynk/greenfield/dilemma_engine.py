"""Genuine Dilemma Engine for Stage 2 & 3 architectural forks (v0.28.5)."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_ARCHETYPES = [
    {
        "category": "cli",
        "keywords": ["cli", "terminal", "command", "tool", "digest", "script", "audio", "rss"],
        "topic": "Local Embedded Persistence: SQLite WAL vs Flat JSON/YAML Dotfiles",
        "option_a": "Embedded SQLite WAL Storage (Atomic crash safety, indexed query speed, zero external pip deps)",
        "option_b": "Flat Dotfile Storage (Human-readable YAML/JSON, trivial git versioning, minimal footprint)",
        "recommended": "Option A (Embedded SQLite WAL)",
        "panel_arguments": {
            "claude": "Recommend SQLite WAL: enables structured indexing, transactional rollbacks, and crash safety during multi-step runs.",
            "codex": "Agreed: Python's builtin sqlite3 standard library requires zero pip dependencies, keeping packaging lightweight and standalone.",
            "agy": "Deterministic testing is much simpler with SQLite; in-memory (:memory:) fixtures allow sub-second automated test suites.",
            "grok": "Low write contention expected; WAL mode prevents any read blocking during background sync operations.",
        },
    },
    {
        "category": "backend",
        "keywords": ["service", "api", "backend", "web", "server", "fastapi", "queue", "worker"],
        "topic": "Task Queue Architecture: Asynchronous Broker (Redis/NATS) vs In-Process Multi-Worker Pool",
        "option_a": "In-Process Async Worker Pool (Zero operational dependencies, instant single-node bootstrap, minimal cost)",
        "option_b": "External Message Broker (Horizontal multi-instance scaling, persistent distributed queue state)",
        "recommended": "Option A (In-Process Async Worker Pool for MVP)",
        "panel_arguments": {
            "claude": "Recommend In-Process Async Worker Pool for Milestone 1: eliminates external infrastructure requirements for first-time developers.",
            "codex": "Python asyncio Queue + TaskGroups provide robust concurrency with typed contracts and simple test mocking.",
            "agy": "Contract tests run cleanly without requiring docker-compose or spinning up background Redis containers in CI.",
            "grok": "Fast start-up latency; defer external broker migration to Arc 2 once workload metrics warrant it.",
        },
    },
    {
        "category": "data_media",
        "keywords": ["data", "media", "cache", "download", "transcribe", "whisper", "stream", "video"],
        "topic": "Asset Storage Strategy: Local Content-Addressed Cache vs Direct Object Storage",
        "option_a": "Local Content-Addressed Filesystem Cache (Offline velocity, SHA-256 deduplication, zero cloud egress costs)",
        "option_b": "Cloud Object Storage (Centralized persistence, pre-signed URL sharing, team synchronicity)",
        "recommended": "Option A (Local Content-Addressed Filesystem Cache)",
        "panel_arguments": {
            "claude": "Recommend Local SHA-256 Content-Addressed Cache: gives immediate developer feedback and works offline without cloud credentials.",
            "codex": "Content-addressed chunking prevents redundant duplicate downloads and keeps hash validation localized.",
            "agy": "Local directory structure is fully deterministic and easily verified in tests using pytest tmp_path fixtures.",
            "grok": "High local I/O throughput; keeps API secrets out of the initial developer onboarding path.",
        },
    },
    {
        "category": "general",
        "keywords": [],
        "topic": "Extensibility Architecture: Hook-Based Plugin Registry vs Rigid Monolithic Core",
        "option_a": "Hook-Based Plugin Registry (Decoupled modules, clean test boundaries, easy feature additions)",
        "option_b": "Monolithic Core Modules (Centralized control flow, single code path, simple debugging)",
        "recommended": "Option A (Hook-Based Plugin Registry)",
        "panel_arguments": {
            "claude": "Recommend Hook-Based Registry: promotes separation of concerns and clear interface boundaries from Day 1.",
            "codex": "Type hints with Protocol classes ensure type safety across plugin boundaries without tight coupling.",
            "agy": "Test isolation is superior; individual extensions can be tested with mock hooks without running the full engine.",
            "grok": "Allows future third-party integrations to hook into the workflow cleanly without monkey-patching core logic.",
        },
    },
]


def isolate_dilemma(raw_intent: str, category_override: Optional[str] = None) -> Dict[str, Any]:
    """Isolate a non-trivial architectural fork based on project intent keywords."""
    lower_intent = raw_intent.lower()

    if category_override:
        for arch in _ARCHETYPES:
            if arch["category"] == category_override:
                return arch

    # Match based on keywords
    for arch in _ARCHETYPES[:-1]:  # Skip general default
        if any(re.search(rf"\b{kw}\b", lower_intent) for kw in arch["keywords"]):
            return arch

    return _ARCHETYPES[-1]


def format_decide_box(dilemma: Dict[str, Any]) -> str:
    """Format the Stage 3 DECIDE consensus panel ASCII presentation."""
    lines = [
        "┌─────────────────────────────────────────────────────────────────────────────┐",
        f"│ ⚖️ synlynk decide: Deliberating Architectural Dilemma                       │",
        f"│ Topic: {dilemma['topic'][:68].ljust(68)} │",
        "│                                                                             │",
    ]

    panel_args = dilemma["panel_arguments"]
    for role, member in [("Claude - Architect", "claude"), ("Codex - Dev", "codex"), ("Agy - QA", "agy"), ("Grok - Infra", "grok")]:
        arg = panel_args.get(member, "")
        prefix = f"[{role}]".ljust(22)
        # Wrap arg nicely into 52 chars
        words = arg.split()
        current = ""
        first = True
        for w in words:
            if len(current) + len(w) + 1 <= 50:
                current = f"{current} {w}".strip()
            else:
                line_content = f"{prefix if first else ' '.ljust(22)} \"{current}\""
                lines.append(f"│ {line_content.ljust(75)} │")
                current = w
                first = False
        if current:
            line_content = f"{prefix if first else ' '.ljust(22)} \"{current}\""
            lines.append(f"│ {line_content.ljust(75)} │")

    lines.extend([
        "│ ─────────────────────────────────────────────────────────────────────────── │",
        f"│ PANEL CONSENSUS: {dilemma['recommended'][:57].ljust(58)}│",
        "│ [Enter] Accept Recommendation · [O] Override with Alternative               │",
        "└─────────────────────────────────────────────────────────────────────────────┘",
    ])
    return "\n".join(lines)
