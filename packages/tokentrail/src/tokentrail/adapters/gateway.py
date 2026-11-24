"""Adapter for Gateway & Proxy Interceptors (OpenRouter, LiteLLM, OpenAI-compatible JSON/headers)."""

import json
from typing import Dict, Any, Optional
from tokentrail.models import TokenUsage, MessageTurn, SessionLedger


class GatewayAdapter:
    """Extracts token usage from Gateway responses and response headers."""

    @staticmethod
    def parse_response_dict(response_data: Dict[str, Any], session_id: str = "gateway-session") -> SessionLedger:
        """Parse standard OpenAI/LiteLLM/OpenRouter JSON response."""
        usage_data = response_data.get("usage") or {}
        msg_id = response_data.get("id") or "resp-0"
        model = response_data.get("model") or "unknown"
        created = response_data.get("created")
        timestamp = str(created) if created else None

        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        
        details = usage_data.get("prompt_tokens_details") or {}
        cache_read = details.get("cached_tokens", usage_data.get("cache_read_input_tokens", 0))
        cache_write = usage_data.get("cache_creation_input_tokens", 0)

        usage = TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_write_tokens=cache_write,
            cache_read_tokens=cache_read,
        )

        turn = MessageTurn(
            message_id=msg_id,
            model=model,
            timestamp=timestamp,
            usage=usage,
        )

        return SessionLedger(
            session_id=session_id,
            harness="gateway",
            source_path="api://stream",
            turns=[turn],
        )

    @staticmethod
    def parse_litellm_headers(headers: Dict[str, str], session_id: str = "litellm-session") -> Optional[TokenUsage]:
        """Extract usage from x-litellm-response-cost or usage headers if present."""
        prompt_t = int(headers.get("x-litellm-prompt-tokens") or 0)
        comp_t = int(headers.get("x-litellm-completion-tokens") or 0)
        if prompt_t == 0 and comp_t == 0:
            return None
        return TokenUsage(
            input_tokens=prompt_t,
            output_tokens=comp_t,
            cache_write_tokens=0,
            cache_read_tokens=0,
        )
