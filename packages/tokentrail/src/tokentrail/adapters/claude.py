"""Adapter for Claude Code interactive CLI transcripts (~/.claude/projects/**/*.jsonl)."""

import json
import os
from typing import Dict, Any
from tokentrail.models import TranscriptAdapter, SessionLedger, MessageTurn, TokenUsage


class ClaudeCodeAdapter:
    """Parses Claude Code JSONL transcripts and deduplicates streaming message chunks."""

    def detect(self, source_path: str) -> bool:
        if not source_path.endswith(".jsonl"):
            return False
        # Read first few lines to detect Claude Code event structure
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                for _ in range(5):
                    line = f.readline()
                    if not line:
                        break
                    data = json.loads(line)
                    if data.get("type") in ("message", "user", "assistant") or "message" in data:
                        return True
        except Exception:
            return False
        return False

    def parse(self, source_path: str) -> SessionLedger:
        session_id = os.path.splitext(os.path.basename(source_path))[0]
        # Invariant: Streaming turns emit multiple JSONL events for the same message.id.
        # We group by message.id and keep the terminal usage object to prevent 2x overcounting.
        turns_by_id: Dict[str, MessageTurn] = {}

        with open(source_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue

                # Case 1: event wraps message object
                msg = event.get("message") if isinstance(event, dict) else None
                if not msg and event.get("type") == "message":
                    msg = event

                if not isinstance(msg, dict):
                    continue

                msg_id = msg.get("id")
                if not msg_id:
                    continue

                usage_data = msg.get("usage") or {}
                if not usage_data:
                    continue

                model = msg.get("model") or event.get("model") or "claude-3-5-sonnet"
                timestamp = event.get("timestamp") or event.get("created_at")

                usage = TokenUsage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                    cache_write_tokens=usage_data.get("cache_creation_input_tokens", 0),
                    cache_read_tokens=usage_data.get("cache_read_input_tokens", 0),
                )

                # Overwrite prior intermediate streaming chunks with the latest terminal usage
                turns_by_id[msg_id] = MessageTurn(
                    message_id=msg_id,
                    model=model,
                    timestamp=timestamp,
                    usage=usage,
                )

        return SessionLedger(
            session_id=session_id,
            harness="claude",
            source_path=source_path,
            turns=list(turns_by_id.values()),
        )
