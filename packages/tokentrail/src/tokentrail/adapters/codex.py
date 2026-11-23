"""Adapter for Codex CLI transcripts (~/.codex/sessions/**/*.jsonl)."""

import json
import os
from typing import Dict, Any
from tokentrail.models import TranscriptAdapter, SessionLedger, MessageTurn, TokenUsage


class CodexAdapter:
    """Parses Codex JSONL transcripts and extracts verified token usage per turn."""

    def detect(self, source_path: str) -> bool:
        if not source_path.endswith(".jsonl"):
            return False
        if "codex" in source_path:
            return True
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                for _ in range(5):
                    line = f.readline()
                    if not line:
                        break
                    data = json.loads(line)
                    if data.get("source") == "codex" or "codex" in str(data.get("model", "")):
                        return True
        except Exception:
            return False
        return False

    def parse(self, source_path: str) -> SessionLedger:
        session_id = os.path.splitext(os.path.basename(source_path))[0]
        turns_by_id: Dict[str, MessageTurn] = {}

        with open(source_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue

                # Codex events may report turn id or message id
                msg_id = event.get("turn_id") or event.get("id") or f"turn-{idx}"
                usage_data = event.get("usage") or {}
                if not usage_data and "response" in event and isinstance(event["response"], dict):
                    usage_data = event["response"].get("usage") or {}

                if not usage_data:
                    continue

                model = event.get("model") or "o3-mini"
                timestamp = event.get("timestamp") or event.get("created_at")

                prompt_tokens = usage_data.get("prompt_tokens", usage_data.get("input_tokens", 0))
                completion_tokens = usage_data.get("completion_tokens", usage_data.get("output_tokens", 0))
                cache_read = usage_data.get("prompt_tokens_details", {}).get("cached_tokens", 0) if isinstance(usage_data.get("prompt_tokens_details"), dict) else usage_data.get("cached_tokens", 0)
                cache_write = usage_data.get("cache_write_tokens", 0)

                usage = TokenUsage(
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    cache_write_tokens=cache_write,
                    cache_read_tokens=cache_read,
                )

                turns_by_id[msg_id] = MessageTurn(
                    message_id=msg_id,
                    model=model,
                    timestamp=timestamp,
                    usage=usage,
                )

        return SessionLedger(
            session_id=session_id,
            harness="codex",
            source_path=source_path,
            turns=list(turns_by_id.values()),
        )
