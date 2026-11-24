"""High-level extraction router for tokentrail."""

import os
from typing import List, Optional
from tokentrail.models import SessionLedger
from tokentrail.adapters.claude import ClaudeCodeAdapter
from tokentrail.adapters.agy import AgyAdapter
from tokentrail.adapters.codex import CodexAdapter

ALL_ADAPTERS = [
    ClaudeCodeAdapter(),
    AgyAdapter(),
    CodexAdapter(),
]


def extract_ledger(source_path: str, harness: Optional[str] = None) -> SessionLedger:
    """Extract SessionLedger from a transcript file, auto-detecting harness if unspecified."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Transcript file not found: {source_path}")

    if harness:
        h = harness.lower()
        if "claude" in h:
            return ClaudeCodeAdapter().parse(source_path)
        elif "agy" in h or "gemini" in h:
            return AgyAdapter().parse(source_path)
        elif "codex" in h or "openai" in h:
            return CodexAdapter().parse(source_path)

    for adapter in ALL_ADAPTERS:
        if adapter.detect(source_path):
            return adapter.parse(source_path)

    # Fallback to claude adapter default
    return ClaudeCodeAdapter().parse(source_path)
