import json
import os
from typing import Any, Dict, List

DEFAULT_REGISTRY: Dict[str, Any] = {
    "supabase": {"enabled": True, "auth_type": "byok", "vault_key": "SUPABASE_ACCESS_TOKEN"},
    "vercel": {"enabled": True, "auth_type": "byok", "vault_key": "VERCEL_TOKEN"},
    "openrouter": {"enabled": True, "auth_type": "byok", "vault_key": "OPENROUTER_API_KEY"},
    "fal_ai": {"enabled": False, "auth_type": "byok", "vault_key": "FAL_KEY"},
    "gateways": {
        "openrouter": {
            "enabled": False,
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "models": [],
            "note": (
                "Dispatch integration ships in v0.26.0. Use synlynk gateway "
                "probe to test connectivity."
            ),
        }
    },
}


def load_registry() -> Dict[str, Any]:
    path = os.path.join(os.getcwd(), ".synlynk", "registry.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                if not isinstance(registry, dict):
                    return DEFAULT_REGISTRY
                # Preserve user-provided gateway settings while making the
                # preview schema available to older registry files.
                registry.setdefault("gateways", DEFAULT_REGISTRY["gateways"])
                return registry
        except (json.JSONDecodeError, OSError):
            return DEFAULT_REGISTRY
    return DEFAULT_REGISTRY


def redact_secrets(text: str, secrets: List[str]) -> str:
    result = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            result = result.replace(secret, "[REDACTED_SECRET]")
    return result
