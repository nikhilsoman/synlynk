import copy
import json
import os
from typing import Any, Dict, List, Optional


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
                "Set dispatch_active to true to enable OpenRouter dispatch. "
                "The models list provides fallback model IDs in attempt order."
            ),
        }
    },
}


def load_registry(path: Optional[str] = None) -> Dict[str, Any]:
    if path is None:
        path = os.path.join(os.getcwd(), ".synlynk", "registry.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                registry = json.load(f)
                if not isinstance(registry, dict):
                    return copy.deepcopy(DEFAULT_REGISTRY)
                # Preserve user-provided gateway settings while making the
                # preview schema available to older registry files.
                registry.setdefault("gateways", copy.deepcopy(DEFAULT_REGISTRY["gateways"]))
                return registry
        except (json.JSONDecodeError, OSError):
            return copy.deepcopy(DEFAULT_REGISTRY)
    return copy.deepcopy(DEFAULT_REGISTRY)


def save_registry(registry: Dict[str, Any], path: Optional[str] = None) -> str:
    """Save the registry configuration atomically to .synlynk/registry.json."""
    if path is None:
        path = os.path.join(os.getcwd(), ".synlynk", "registry.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)
    return path


def configure_openrouter(
    api_key: Optional[str] = None,
    models: Optional[List[str]] = None,
    base_url: Optional[str] = None,
    disable: bool = False,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Configure OpenRouter BYOK integration in registry.json."""
    registry = load_registry(config_path)
    if "gateways" not in registry or not isinstance(registry["gateways"], dict):
        registry["gateways"] = copy.deepcopy(DEFAULT_REGISTRY["gateways"])
    gateways = registry["gateways"]

    if "openrouter" not in gateways or not isinstance(gateways["openrouter"], dict):
        gateways["openrouter"] = copy.deepcopy(DEFAULT_REGISTRY["gateways"]["openrouter"])
    openrouter_cfg = gateways["openrouter"]

    if disable:
        openrouter_cfg["enabled"] = False
        openrouter_cfg["dispatch_active"] = False
        if "openrouter" in registry and isinstance(registry["openrouter"], dict):
            registry["openrouter"]["enabled"] = False
    else:
        openrouter_cfg["enabled"] = True
        openrouter_cfg["dispatch_active"] = True
        if "openrouter" in registry and isinstance(registry["openrouter"], dict):
            registry["openrouter"]["enabled"] = True

    if base_url:
        openrouter_cfg["base_url"] = base_url
    if models is not None:
        openrouter_cfg["models"] = models
    elif not openrouter_cfg.get("models"):
        openrouter_cfg["models"] = ["anthropic/claude-sonnet-4", "openai/gpt-4o"]

    save_registry(registry, config_path)
    return registry


def redact_secrets(text: str, secrets: List[str]) -> str:
    result = text
    for secret in secrets:
        if secret and len(secret) >= 4:
            result = result.replace(secret, "[REDACTED_SECRET]")
    return result
