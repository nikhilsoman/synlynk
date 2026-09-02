"""First-class model and model-family registry.

The registry is deliberately provider-neutral.  Harnesses are execution
boundaries; a model spec describes the model's capabilities and economics.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class EntitlementTier(str, Enum):
    INCLUDED_IN_BASE = "included_in_base"
    SUBSCRIPTION_CAPPED = "subscription_capped"
    METERED_EXTRA_USAGE_ONLY = "metered_extra_usage_only"
    ZERO_COST_LOCAL = "zero_cost_local"


@dataclass(frozen=True)
class RateCard:
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0
    cache_read_per_1k: float = 0.0
    reasoning_per_1k: float = 0.0


@dataclass(frozen=True)
class ContextGeometry:
    max_input_tokens: int = 0
    max_output_tokens: int = 0
    reasoning_tokens: bool = False


@dataclass(frozen=True)
class ModelFamily:
    family_id: str
    provider: str
    context_geometry: ContextGeometry = field(default_factory=ContextGeometry)
    native_features: tuple[str, ...] = ()
    prompt_adapter: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    family_id: str
    harness_binding: str
    locality: str = "remote_api"
    quantization: str | None = None
    rates: RateCard = field(default_factory=RateCard)
    entitlement_tier: EntitlementTier = EntitlementTier.METERED_EXTRA_USAGE_ONLY
    context_geometry: ContextGeometry | None = None
    native_features: tuple[str, ...] = ()
    discovered: bool = False
    discovery_source: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.rates, dict):
            object.__setattr__(self, "rates", RateCard(**self.rates))
        if isinstance(self.entitlement_tier, str):
            object.__setattr__(self, "entitlement_tier", EntitlementTier(self.entitlement_tier))
        if self.locality not in {"remote_api", "on_device_local"}:
            raise ValueError("locality must be remote_api or on_device_local")


def _remote(model_id: str, family_id: str, harness: str, tier=EntitlementTier.METERED_EXTRA_USAGE_ONLY, **kw) -> ModelSpec:
    return ModelSpec(model_id, family_id, harness, entitlement_tier=tier, **kw)


BUILTIN_FAMILIES = (
    ModelFamily("claude-3-5", "anthropic", ContextGeometry(200_000, 8_192, True), ("tool_calling", "json_schema", "vision", "prompt_caching")),
    ModelFamily("gemini-1-5", "google", ContextGeometry(1_000_000, 8_192, True), ("tool_calling", "json_schema", "vision")),
    ModelFamily("gemini-2-0", "google", ContextGeometry(1_000_000, 8_192, True), ("tool_calling", "json_schema", "vision")),
    ModelFamily("gpt-4o", "openai", ContextGeometry(128_000, 16_384, False), ("tool_calling", "json_schema", "vision")),
    ModelFamily("gemma-2", "meta", ContextGeometry(8_192, 4_096, False), ("tool_calling",)),
    ModelFamily("deepseek-r1", "local", ContextGeometry(128_000, 8_192, True), ("tool_calling",)),
    ModelFamily("qwen2-5", "alibaba", ContextGeometry(128_000, 8_192, False), ("tool_calling",)),
)

BUILTIN_MODEL_CATALOG = (
    _remote("claude-3-5-sonnet-20241022", "claude-3-5", "claude", EntitlementTier.INCLUDED_IN_BASE),
    _remote("claude-3-5-opus-20240229", "claude-3-5", "claude", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("gemini-1.5-flash", "gemini-1-5", "agy", EntitlementTier.INCLUDED_IN_BASE),
    _remote("gemini-1.5-pro", "gemini-1-5", "agy", EntitlementTier.METERED_EXTRA_USAGE_ONLY),
    _remote("gemini-2.0-flash", "gemini-2-0", "agy", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("gpt-4o-2024-11-20", "gpt-4o", "codex", EntitlementTier.INCLUDED_IN_BASE),
    _remote("grok-2-latest", "gpt-4o", "grok", EntitlementTier.METERED_EXTRA_USAGE_ONLY),
    ModelSpec("gemma-2-9b-it-q4", "gemma-2", "local", locality="on_device_local", quantization="Q4_K_M", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("deepseek-r1", "deepseek-r1", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("qwen2.5", "qwen2-5", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
)

# Public aliases kept intentionally simple for callers that want a catalog
# without coupling themselves to the implementation's tuple name.
MODEL_FAMILIES = BUILTIN_FAMILIES
BUILTIN_MODELS = BUILTIN_MODEL_CATALOG


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def model_to_dict(model: ModelSpec) -> dict[str, Any]:
    return _jsonable(model)


def family_to_dict(family: ModelFamily) -> dict[str, Any]:
    return _jsonable(family)


def _parse_model_names(text: str) -> list[str]:
    names: list[str] = []
    try:
        payload = json.loads(text)
        values = payload if isinstance(payload, list) else payload.get("models", []) if isinstance(payload, dict) else []
        for item in values:
            name = item.get("id") or item.get("name") if isinstance(item, dict) else str(item)
            if name:
                names.append(str(name))
    except (ValueError, TypeError):
        pass
    for name in re.findall(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_.:/-]{2,}(?:\.[A-Za-z0-9_-]+)?", text):
        if any(token in name.lower() for token in ("gpt", "claude", "gemini", "grok", "llama", "qwen", "gemma", "deepseek")):
            names.append(name.rstrip(".,:;"))
    return list(dict.fromkeys(names))


def probe_cli_harness(harness: str, executable: str | None = None, timeout: float = 5.0) -> list[ModelSpec]:
    """Probe one installed CLI without failing the caller when it is absent."""
    commands = {"claude": ["models"], "codex": ["--list-models"], "agy": ["--help"], "grok": ["models"]}
    executable = executable or harness
    if not shutil.which(executable):
        return []
    try:
        result = subprocess.run([executable, *commands[harness]], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ModelSpec(name, "discovered", harness, discovered=True, discovery_source=f"cli:{executable}") for name in _parse_model_names(result.stdout + "\n" + result.stderr)]


def _probe_http(url: str, timeout: float = 1.5) -> list[str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        values = payload.get("models", []) if isinstance(payload, dict) else payload
        return [str(item.get("name") or item.get("id")) for item in values if isinstance(item, dict) and (item.get("name") or item.get("id"))]
    except (OSError, ValueError, urllib.error.URLError):
        return []


def probe_local_runtimes(timeout: float = 1.5) -> list[ModelSpec]:
    found: list[ModelSpec] = []
    ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    if not ollama.startswith("http"):
        ollama = "http://" + ollama
    for name in _probe_http(ollama + "/api/tags", timeout):
        found.append(ModelSpec(name, "discovered", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL, discovered=True, discovery_source="ollama:/api/tags"))
    base = os.environ.get("OMLX_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    for path in ("/v1/models", "/api/models"):
        for name in _probe_http(base + path, timeout):
            found.append(ModelSpec(name, "discovered", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL, discovered=True, discovery_source=f"omlx:{path}"))
    model_dir = Path(os.environ.get("OMLX_MODELS_DIR", Path.home() / ".omlx" / "models"))
    if model_dir.is_dir():
        for path in model_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".gguf", ".safetensors", ".mlx"}:
                found.append(ModelSpec(path.stem, "discovered", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL, discovered=True, discovery_source="omlx:filesystem"))
    return list({m.model_id: m for m in found}.values())


def probe_ollama(timeout: float = 1.5) -> list[ModelSpec]:
    """Probe Ollama's standard model-tags endpoint."""
    return [m for m in probe_local_runtimes(timeout) if m.discovery_source == "ollama:/api/tags"]


def probe_omlx(timeout: float = 1.5) -> list[ModelSpec]:
    """Probe oMLX's OpenAI-compatible roster and local model directory."""
    return [m for m in probe_local_runtimes(timeout) if m.discovery_source and m.discovery_source.startswith("omlx:")]


def discover_environment() -> list[ModelSpec]:
    """Compatibility name for the complete local environment discovery pass."""
    return discover_models()


def discover_models() -> list[ModelSpec]:
    discovered: list[ModelSpec] = []
    for harness in ("claude", "codex", "agy", "grok"):
        discovered.extend(probe_cli_harness(harness))
    discovered.extend(probe_local_runtimes())
    return list({m.model_id: m for m in discovered}.values())


def register_builtin_models(conn) -> None:
    from synlynk.db import upsert_model_family, upsert_model
    for family in BUILTIN_FAMILIES:
        upsert_model_family(conn, family)
    for model in BUILTIN_MODEL_CATALOG:
        upsert_model(conn, model)


def cmd_models_list(json_output: bool = False) -> list[dict[str, Any]]:
    from synlynk import _get_db
    from synlynk.db import list_models
    conn = _get_db()
    register_builtin_models(conn)
    rows = list_models(conn)
    conn.close()
    if json_output:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(f"{row['model_id']}\t{row['harness_binding']}\t{row['entitlement_tier']}\t{row['locality']}")
    return rows


def cmd_models_show(model_id: str, json_output: bool = False) -> dict[str, Any] | None:
    from synlynk import _get_db
    from synlynk.db import get_model
    conn = _get_db(); register_builtin_models(conn); row = get_model(conn, model_id); conn.close()
    if row is None:
        raise ValueError(f"unknown model: {model_id}")
    print(json.dumps(row, indent=2) if json_output else "\n".join(f"{k}: {v}" for k, v in row.items()))
    return row


def cmd_models_discover(json_output: bool = False) -> list[dict[str, Any]]:
    from synlynk import _get_db
    from synlynk.db import upsert_model
    conn = _get_db(); register_builtin_models(conn)
    models = discover_models()
    for model in models:
        upsert_model(conn, model)
    conn.commit(); conn.close()
    rows = [model_to_dict(model) for model in models]
    print(json.dumps(rows, indent=2) if json_output else ("Discovered no additional models." if not rows else "\n".join(m["model_id"] for m in rows)))
    return rows
