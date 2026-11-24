"""Adapter for Agy / AntiGravity CLI transcript logs (.system_generated/logs/transcript*.jsonl)."""

import json
import os
from typing import Dict, Any
from tokentrail.models import TranscriptAdapter, SessionLedger, MessageTurn, TokenUsage


class AgyAdapter:
    """Parses Agy / AntiGravity JSONL transcripts and extracts verified token usage."""

    def detect(self, source_path: str) -> bool:
        if not source_path.endswith(".jsonl"):
            return False
        base = os.path.basename(source_path)
        return "transcript" in base

    def parse(self, source_path: str) -> SessionLedger:
        session_id = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(source_path))))
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

                step_idx = event.get("step_index")
                if step_idx is None:
                    continue

                msg_id = f"step-{step_idx}"
                # Agy step events with model usage
                usage_data = event.get("usage") or {}
                # Some events nest in tool_calls or metadata
                model = event.get("model") or "gemini-2.5-pro"
                timestamp = event.get("created_at")

                usage = TokenUsage(
                    input_tokens=usage_data.get("input_tokens", usage_data.get("prompt_tokens", 0)),
                    output_tokens=usage_data.get("output_tokens", usage_data.get("completion_tokens", 0)),
                    cache_write_tokens=usage_data.get("cache_write_tokens", 0),
                    cache_read_tokens=usage_data.get("cache_read_tokens", 0),
                )

                if usage.total_tokens > 0:
                    turns_by_id[msg_id] = MessageTurn(
                        message_id=msg_id,
                        model=model,
                        timestamp=timestamp,
                        usage=usage,
                    )

        return SessionLedger(
            session_id=session_id,
            harness="agy",
            source_path=source_path,
            turns=list(turns_by_id.values()),
        )
