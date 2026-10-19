"""First-class model and model-family registry.

The registry is deliberately provider-neutral.  Harnesses are execution
boundaries; a model spec describes the model's capabilities and economics.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import shutil
import subprocess
import time
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
    # Set only when a live probe payload actually carried rate or capability
    # fields. Absence means the surface did not expose them.
    probe_rates: dict[str, Any] | None = None

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
    ModelFamily("claude-5", "anthropic", ContextGeometry(200_000, 16_384, True), ("tool_calling", "json_schema", "vision", "prompt_caching")),
    ModelFamily("gemini-3", "google", ContextGeometry(1_000_000, 32_768, True), ("tool_calling", "json_schema", "vision")),
    ModelFamily("gpt-5.6", "openai", ContextGeometry(400_000, 32_768, True), ("tool_calling", "json_schema")),
    ModelFamily("grok-4", "xai", ContextGeometry(131_072, 16_384, True), ("tool_calling", "json_schema", "vision")),
    ModelFamily("gemma-2", "meta", ContextGeometry(8_192, 4_096, False), ("tool_calling",)),
    ModelFamily("deepseek-r1", "local", ContextGeometry(128_000, 8_192, True), ("tool_calling",)),
    ModelFamily("qwen2-5", "alibaba", ContextGeometry(128_000, 8_192, False), ("tool_calling",)),
    ModelFamily("hermes-3", "nous-research", ContextGeometry(128_000, 8_192, True), ("tool_calling",)),
    ModelFamily("ornith-1", "local"),
)

BUILTIN_MODEL_CATALOG = (
    _remote("claude-opus-5", "claude-5", "claude", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-opus-5-5", "claude-5", "claude", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-sonnet-5", "claude-5", "claude", EntitlementTier.INCLUDED_IN_BASE),
    _remote("claude-fable-5-1", "claude-5", "claude", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-fable-5", "claude-5", "claude", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-haiku-4-5-20251001", "claude-5", "claude", EntitlementTier.INCLUDED_IN_BASE),
    # Live `agy models` roster as of 2026-10-14 (gh:#2268). The previous
    # gemini-3.7-flash-medium / gemini-3.1-pro-* ids are rejected by the CLI.
    _remote("gemini-3.8-flash-low", "gemini-3", "agy", EntitlementTier.INCLUDED_IN_BASE),
    _remote("gemini-3.8-flash-medium", "gemini-3", "agy", EntitlementTier.INCLUDED_IN_BASE),
    _remote("gemini-3.8-flash-high", "gemini-3", "agy", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-sonnet-4-6", "claude-5", "agy", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("claude-opus-4-6-thinking", "claude-5", "agy", EntitlementTier.SUBSCRIPTION_CAPPED),
    _remote("gpt-oss-120b-medium", "gpt-5.6", "agy", EntitlementTier.INCLUDED_IN_BASE),
    _remote("gpt-5.6-luna", "gpt-5.6", "codex", EntitlementTier.INCLUDED_IN_BASE),
    _remote("grok-4.7", "grok-4", "grok", EntitlementTier.METERED_EXTRA_USAGE_ONLY),
    _remote("grok-4.6", "grok-4", "grok", EntitlementTier.SUBSCRIPTION_CAPPED),
    ModelSpec("Ornith-1.0-9B-4bit", "ornith-1", "local", locality="on_device_local", quantization="4bit", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("gemma-2-9b-it-q4", "gemma-2", "local", locality="on_device_local", quantization="Q4_K_M", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("deepseek-r1", "deepseek-r1", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("qwen2.5", "qwen2-5", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("Hermes-3-Llama-3.1-8B", "hermes-3", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("Hermes-3-Llama-3.1-70B", "hermes-3", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
    ModelSpec("Hermes-3-Llama-3.1-405B", "hermes-3", "local", locality="on_device_local", entitlement_tier=EntitlementTier.ZERO_COST_LOCAL),
)

# Public aliases kept intentionally simple for callers that want a catalog
# without coupling themselves to the implementation's tuple name.
MODEL_FAMILIES = BUILTIN_FAMILIES
BUILTIN_MODELS = BUILTIN_MODEL_CATALOG


def load_model_catalog(repo_path: Optional[str] = None) -> dict[str, Any]:
    """Load .synlynk/models.json declarative catalog with builtin fallback."""
    base = Path(repo_path) if repo_path else Path.cwd()
    catalog_path = base / ".synlynk" / "models.json"
    if catalog_path.is_file():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Builtin fallback catalog
    return {
        "schema_version": 1,
        "as_of": "2026-09-24",
        "tiers": {
            "fast": {
                "claude": "claude-haiku-4-5-20251001",
                "agy": "gemini-3.8-flash-medium",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.6",
                "local": "Ornith-1.0-9B-4bit",
                "muse": "muse-spark-1.3",
            },
            "pro": {
                "claude": "claude-sonnet-5",
                "agy": "gemini-3.8-flash-high",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.7",
                "local": "Ornith-1.0-9B-4bit",
                "muse": "muse-spark-1.3",
            },
            "reasoning": {
                "claude": "claude-opus-5-5",
                "agy": "claude-opus-4-6-thinking",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.7",
                "local": "Ornith-1.0-9B-4bit",
            },
            "hermes": {
                "local": "Hermes-3-Llama-3.1-8B",
            },
        },
        "models": [model_to_dict(m) for m in BUILTIN_MODEL_CATALOG],
    }


# Preference order when a catalog id is absent from the live Agy roster.
# Heads match `agy models` on 2026-10-14; the heuristic below covers the
# next rename without another hardcoded-only failure (gh:#2268).
_AGY_TIER_DISCOVERY_PREFERENCE = {
    "fast": ("gemini-3.8-flash-medium", "gemini-3.8-flash-low", "gemini-3.8-flash-high"),
    "pro": ("gemini-3.8-flash-high", "gemini-3.8-flash-medium", "claude-sonnet-4-6"),
    "reasoning": ("claude-opus-4-6-thinking", "gemini-3.8-flash-high", "claude-sonnet-4-6"),
}

_DISCOVERY_CACHE: dict[str, tuple[float, tuple[str, ...]]] = {}
_DISCOVERY_TTL_SECONDS = 300.0


def _static_tier_model(tier: str, harness: str, repo_path: Optional[str] = None) -> str:
    """Resolve a tier model from the declarative catalog only."""
    catalog = load_model_catalog(repo_path)
    tiers = catalog.get("tiers", {})
    tier_map = tiers.get(tier, {})
    if harness in tier_map:
        return tier_map[harness]
    # Fallback to pro or fast if tier unknown
    for t in ("pro", "fast", "reasoning"):
        if harness in tiers.get(t, {}):
            return tiers[t][harness]
    if harness == "codex":
        try:
            from synlynk.probe import _read_toml_string_value

            codex_home = Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
            configured = _read_toml_string_value(str(codex_home / "config.toml"), "model")
            if configured:
                return configured
        except Exception:
            pass
        return "gpt-5.6-luna"
    return f"{harness}-default"


def _heuristic_agy_tier_model(tier: str, discovered: list[str]) -> str | None:
    """Pick a live Agy model id when none of the preferred ids are present."""
    def first(predicate) -> str | None:
        for name in discovered:
            if predicate(name.lower()):
                return name
        return None

    if tier == "fast":
        return (
            first(lambda name: "flash" in name and "low" in name)
            or first(lambda name: "flash" in name and "medium" in name)
            or first(lambda name: "flash" in name)
        )
    if tier == "pro":
        return (
            first(lambda name: "flash" in name and "high" in name)
            or first(lambda name: "sonnet" in name)
            or first(lambda name: "flash" in name)
        )
    if tier == "reasoning":
        return (
            first(lambda name: "opus" in name or "thinking" in name)
            or first(lambda name: "flash" in name and "high" in name)
        )
    return None


def _pick_discovered_tier_model(harness: str, tier: str, configured: str, discovered: list[str]) -> str:
    """Keep a catalog id that the harness still advertises; otherwise fall back."""
    if not discovered or configured in discovered:
        return configured
    if harness != "agy":
        return configured
    for candidate in _AGY_TIER_DISCOVERY_PREFERENCE.get(tier, ()):
        if candidate in discovered:
            return candidate
    heuristic = _heuristic_agy_tier_model(tier, discovered)
    return heuristic or discovered[0]


# A scraped log fragment is not a model id (gh:#2441). Execution-log rows
# have been observed with values such as "'unknown'\nsynlynk/db.py:3772:",
# 'job.get("model_version")', and '_pkg("extract_model_version")(log_text,'.
# Real model ids never contain whitespace, backticks, parens, quotes, or a
# file.py:<line> reference, so reject anything shaped like that before it
# can enter or leave the harness_models catalog.
_FILE_LINE_REF_RE = re.compile(r"\.[A-Za-z0-9_]{1,8}:\d+")


def is_plausible_model_id(model_id: Any) -> bool:
    """True when a candidate string is shaped like a real model identifier."""
    if not isinstance(model_id, str):
        return False
    if not model_id or model_id.strip() != model_id:
        return False
    if re.search(r"\s", model_id):
        return False
    if any(ch in model_id for ch in ("`", "(", ")", '"', "'")):
        return False
    if _FILE_LINE_REF_RE.search(model_id):
        return False
    return True


def _curated_model_ids(harness: str, repo_path: Optional[str] = None) -> set[str]:
    """Return the maintained model allowlist for a harness."""
    catalog = load_model_catalog(repo_path)
    allowed = {
        str(model.get("model_id"))
        for model in catalog.get("models", [])
        if model.get("harness", model.get("harness_binding")) == harness
        and model.get("model_id")
    }
    # Tier mappings are also curated catalog entries. This covers harnesses
    # such as Muse that have a static tier mapping but no model metadata row.
    for tier_map in catalog.get("tiers", {}).values():
        if isinstance(tier_map, dict) and tier_map.get(harness):
            allowed.add(str(tier_map[harness]))
    return allowed


def resolve_tier_model(tier: str, harness: str, repo_path: Optional[str] = None) -> str:
    """Resolve a tier from the persisted discovery catalog, with a fresh-DB seed."""
    from synlynk import _get_db
    from synlynk.db import get_active_harness_models

    conn = _get_db()
    active = get_active_harness_models(conn, harness=harness, tier=tier)
    allowlisted = _curated_model_ids(harness, repo_path)
    for row in active:
        model_id = row.get("model_id")
        if is_plausible_model_id(model_id) and model_id in allowlisted:
            return model_id

    # The static catalog is a bootstrap seed only. Once discovery has ever
    # populated this harness, do not resurrect a retired catalog id.
    discovered = None
    if conn is not None:
        try:
            discovered = conn.execute(
                "SELECT 1 FROM harness_models WHERE harness_name=? LIMIT 1", (harness,)
            ).fetchone()
        except sqlite3.ProgrammingError:
            discovered = None
        except sqlite3.OperationalError as exc:
            if "no such table: harness_models" not in str(exc):
                raise
    if discovered:
        harness_rows = get_active_harness_models(conn, harness=harness, tier=tier)
        for row in harness_rows:
            model_id = row.get("model_id")
            if is_plausible_model_id(model_id) and model_id in allowlisted:
                return model_id
        # No allowlisted discovery row: fall through to the curated static
        # fallback below instead of returning a scraped or retired model.

    configured = _static_tier_model(tier, harness, repo_path)
    if harness == "agy":
        configured = _pick_discovered_tier_model(
            harness, tier, configured, discovered_model_ids("agy")
        )
    return configured


def get_models_from_catalog(repo_path: Optional[str] = None) -> list[ModelSpec]:
    """Parse ModelSpec objects from the loaded catalog."""
    catalog = load_model_catalog(repo_path)
    specs: list[ModelSpec] = []
    for m in catalog.get("models", []):
        rates = m.get("rates", {})
        if not isinstance(rates, RateCard):
            rates = RateCard(**rates) if isinstance(rates, dict) else RateCard()
        harness_binding = m.get("harness", m.get("harness_binding", "claude"))
        specs.append(
            ModelSpec(
                model_id=m["model_id"],
                family_id=m.get("family", m.get("family_id", "generic")),
                harness_binding=harness_binding,
                locality=m.get(
                    "locality",
                    "on_device_local" if harness_binding == "local" else "remote_api",
                ),
                quantization=m.get("quantization"),
                rates=rates,
                entitlement_tier=m.get("entitlement_tier", EntitlementTier.METERED_EXTRA_USAGE_ONLY),
                context_geometry=ContextGeometry(
                    max_input_tokens=m.get("context_window", 0),
                    max_output_tokens=m.get("max_output", 0),
                ),
            )
        )
    return specs if specs else list(BUILTIN_MODEL_CATALOG)


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


def _parse_agy_models_listing(text: str) -> list[str]:
    """Parse `agy models` id<TAB>label lines.

    `agy --help` does not list model ids (gh:#2268). Display names such as
    "Gemini 3.8 Flash (Medium)" are not executable `--model` values.
    """
    names: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith(("fetching ", "usage")):
            continue
        model_id = stripped.split("\t", 1)[0].strip()
        if " " in model_id:
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:/-]{2,}", model_id):
            continue
        lowered = model_id.lower()
        if any(token in lowered for token in ("gpt", "claude", "gemini", "grok", "llama", "qwen", "gemma", "deepseek", "oss")):
            names.append(model_id)
    return list(dict.fromkeys(names))


# Harnesses whose CLI actually lists models. Codex has no such surface
# (plan 2026-10-14): its configured model is read from config.toml instead.
CLI_MODEL_LIST_COMMANDS = {
    "claude": ["models"],
    "agy": ["models"],
    "grok": ["models"],
}

# Per-million rate keys a probe payload may carry. Per-1k aliases are scaled.
_PROBE_RATE_KEYS = {
    "input_per_mtok": ("input_per_mtok", 1.0),
    "rate_input_per_mtok": ("input_per_mtok", 1.0),
    "output_per_mtok": ("output_per_mtok", 1.0),
    "rate_output_per_mtok": ("output_per_mtok", 1.0),
    "cache_read_per_mtok": ("cache_read_per_mtok", 1.0),
    "rate_cache_read_per_mtok": ("cache_read_per_mtok", 1.0),
    "cache_write_per_mtok": ("cache_write_per_mtok", 1.0),
    "rate_cache_write_per_mtok": ("cache_write_per_mtok", 1.0),
    "tool_use_per_mtok": ("tool_use_per_mtok", 1.0),
    "rate_tool_use_per_mtok": ("tool_use_per_mtok", 1.0),
    "input_per_1k": ("input_per_mtok", 1000.0),
    "output_per_1k": ("output_per_mtok", 1000.0),
    "cache_read_per_1k": ("cache_read_per_mtok", 1000.0),
}
_PROBE_RATE_FIELDS = (
    "input_per_mtok", "output_per_mtok", "cache_read_per_mtok",
    "cache_write_per_mtok", "tool_use_per_mtok",
)
_EFFORT_SUFFIX = re.compile(r"-(low|medium|high)$", re.IGNORECASE)

# Gateway/BYOK adapters are not built (gh:#2076). An empty tuple makes the
# discovery loop a no-op instead of an error.
CONFIGURED_GATEWAY_PROVIDERS: tuple[str, ...] = ()


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _meta_from_mapping(item: dict) -> dict[str, Any]:
    """Pull rate and capability fields a listing payload actually contains."""
    buckets = [item]
    for key in ("rates", "pricing", "rate_card"):
        nested = item.get(key)
        if isinstance(nested, dict):
            buckets.append(nested)
    found: dict[str, Any] = {}
    for bucket in buckets:
        for key, (dest, scale) in _PROBE_RATE_KEYS.items():
            if key not in bucket or bucket[key] is None:
                continue
            number = _coerce_float(bucket[key])
            if number is None:
                continue
            found[dest] = number * scale
        for key in ("complexity_tier", "max_effort_level"):
            value = bucket.get(key)
            if isinstance(value, str) and value.strip():
                found[key] = value.strip()
        for src, dest in (
            ("context_window", "context_window_tokens"),
            ("context_window_tokens", "context_window_tokens"),
            ("max_output", "max_output_tokens"),
            ("max_output_tokens", "max_output_tokens"),
        ):
            if src not in bucket or bucket[src] is None:
                continue
            try:
                found[dest] = int(bucket[src])
            except (TypeError, ValueError):
                continue
    return found


def _observations_from_text(text: str, harness: str) -> list[dict[str, Any]]:
    """Parse a model listing into ids plus whatever rates the text encoded."""
    if harness == "agy":
        return [{"model_id": name, "meta": None} for name in _parse_agy_models_listing(text)]
    observations: list[dict[str, Any]] = []
    seen: set[str] = set()
    payload = None
    stripped = (text or "").strip()
    if stripped[:1] in "[{":
        try:
            payload = json.loads(stripped)
        except (ValueError, TypeError):
            payload = None
    values: list[Any] = []
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        nested = payload.get("models", payload.get("data", []))
        if isinstance(nested, list):
            values = nested
    for item in values:
        if isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if not name:
                continue
            model_id = str(name)
            if model_id in seen:
                continue
            seen.add(model_id)
            meta = _meta_from_mapping(item)
            observations.append({"model_id": model_id, "meta": meta or None})
        else:
            model_id = str(item).strip()
            if model_id and model_id not in seen:
                seen.add(model_id)
                observations.append({"model_id": model_id, "meta": None})
    for name in _parse_model_names(text):
        if name not in seen:
            seen.add(name)
            observations.append({"model_id": name, "meta": None})
    return observations


def probe_cli_harness(harness: str, executable: str | None = None, timeout: float = 5.0) -> list[ModelSpec]:
    """Probe one installed CLI without failing the caller when it is absent."""
    executable = executable or harness
    if harness not in CLI_MODEL_LIST_COMMANDS or not shutil.which(executable):
        return []
    try:
        result = subprocess.run(
            [executable, *CLI_MODEL_LIST_COMMANDS[harness]],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    observations = _observations_from_text(result.stdout, harness)
    if not observations:
        observations = _observations_from_text(result.stdout + "\n" + result.stderr, harness)
    specs: list[ModelSpec] = []
    for obs in observations:
        specs.append(ModelSpec(
            obs["model_id"], "discovered", harness,
            discovered=True,
            discovery_source=f"cli:{executable}",
            probe_rates=obs.get("meta"),
        ))
    return specs


def discovered_model_ids(harness: str) -> list[str]:
    """Return live model ids from the same probe ``discover_models()`` uses.

    Pytest skips the probe unless ``SYNLYNK_FORCE_MODEL_DISCOVERY=1``, so
    catalog unit tests stay offline. A successful probe is cached briefly.
    """
    forced = os.environ.get("SYNLYNK_FORCE_MODEL_DISCOVERY") == "1"
    if os.environ.get("PYTEST_CURRENT_TEST") and not forced:
        return []
    now = time.time()
    cached = _DISCOVERY_CACHE.get(harness)
    if cached and (now - cached[0]) < _DISCOVERY_TTL_SECONDS:
        return list(cached[1])
    ids = tuple(spec.model_id for spec in probe_cli_harness(harness))
    _DISCOVERY_CACHE[harness] = (now, ids)
    return list(ids)


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
    # Key by harness as well as id. Agy and Claude can both advertise
    # claude-sonnet-4-6; collapsing on id alone dropped the Agy binding.
    return list({(m.harness_binding, m.model_id): m for m in discovered}.values())


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


def iter_configured_gateway_providers() -> tuple[str, ...]:
    """Return gateway providers the discovery pass should query.

    The list is empty until a gateway adapter exists. Callers must treat that
    as a no-op, not as a failed probe.
    """
    return tuple(CONFIGURED_GATEWAY_PROVIDERS)


def probe_gateway_provider(provider: str) -> list[ModelSpec]:
    """List models for one configured gateway.

    No adapter is shipped yet (gh:#2076). A configured name therefore
    contributes nothing and must not fail the rest of the pass.
    """
    del provider
    return []


def _baseline_harness_names() -> list[str]:
    from synlynk import _constants

    return sorted(_constants.HARNESS_CAPABILITY_BASELINES)


def _read_codex_configured_model() -> str | None:
    """Single-model signal from ~/.codex/config.toml. Codex has no list command."""
    try:
        from synlynk.probe import _read_toml_string_value

        codex_home = Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
        return _read_toml_string_value(str(codex_home / "config.toml"), "model")
    except Exception:
        return None


_CONFIG_MODEL_READERS = {
    "codex": _read_codex_configured_model,
}


def _effort_suffix(model_id: str) -> str | None:
    match = _EFFORT_SUFFIX.search(model_id or "")
    return match.group(1).lower() if match else None


def _catalog_model(harness: str, model_id: str) -> ModelSpec | None:
    for model in BUILTIN_MODEL_CATALOG:
        if model.harness_binding == harness and model.model_id == model_id:
            return model
    return None


def _family_geometry(model: ModelSpec) -> tuple[int | None, int | None]:
    geometry = model.context_geometry
    if geometry is None:
        for family in BUILTIN_FAMILIES:
            if family.family_id == model.family_id:
                geometry = family.context_geometry
                break
    if geometry is None:
        return None, None
    return geometry.max_input_tokens or None, geometry.max_output_tokens or None


def _rate_columns(harness: str, model_id: str, meta: dict | None) -> dict[str, Any]:
    observed = {}
    if meta:
        for name in _PROBE_RATE_FIELDS:
            if name in meta:
                observed[name] = meta[name]
    empty = {
        "rate_input_per_mtok": None,
        "rate_output_per_mtok": None,
        "rate_cache_read_per_mtok": None,
        "rate_cache_write_per_mtok": None,
        "rate_tool_use_per_mtok": None,
        "rate_source": None,
    }
    if observed:
        empty.update({
            "rate_input_per_mtok": observed.get("input_per_mtok"),
            "rate_output_per_mtok": observed.get("output_per_mtok"),
            "rate_cache_read_per_mtok": observed.get("cache_read_per_mtok"),
            "rate_cache_write_per_mtok": observed.get("cache_write_per_mtok"),
            "rate_tool_use_per_mtok": observed.get("tool_use_per_mtok"),
            "rate_source": "cli_probe",
        })
        return empty
    catalog = _catalog_model(harness, model_id)
    if catalog is None:
        return empty
    card = catalog.rates
    return {
        "rate_input_per_mtok": card.input_per_1k * 1000,
        "rate_output_per_mtok": card.output_per_1k * 1000,
        "rate_cache_read_per_mtok": card.cache_read_per_1k * 1000,
        "rate_cache_write_per_mtok": None,
        "rate_tool_use_per_mtok": None,
        "rate_source": "curated_fallback",
    }


def _capability_columns(model_id: str, meta: dict | None, *, from_probe: bool) -> dict[str, Any]:
    """Copy a tier or effort only when the probe surface encoded it."""
    complexity = None
    effort = None
    if not from_probe:
        return {"complexity_tier": complexity, "max_effort_level": effort}
    if meta:
        if isinstance(meta.get("complexity_tier"), str):
            complexity = meta["complexity_tier"]
        if isinstance(meta.get("max_effort_level"), str):
            effort = meta["max_effort_level"]
    suffix = _effort_suffix(model_id)
    if suffix:
        complexity = complexity or suffix
        effort = effort or suffix
    return {"complexity_tier": complexity, "max_effort_level": effort}


def _window_columns(harness: str, model_id: str, meta: dict | None, discovery_source: str) -> dict[str, Any]:
    if meta and ("context_window_tokens" in meta or "max_output_tokens" in meta):
        return {
            "context_window_tokens": meta.get("context_window_tokens"),
            "max_output_tokens": meta.get("max_output_tokens"),
        }
    if discovery_source == "curated_fallback":
        catalog = _catalog_model(harness, model_id)
        if catalog is not None:
            window, output = _family_geometry(catalog)
            return {"context_window_tokens": window, "max_output_tokens": output}
    return {"context_window_tokens": None, "max_output_tokens": None}


def _discovery_row(
    harness: str,
    model_id: str,
    discovery_source: str,
    meta: dict | None,
    *,
    from_probe: bool,
    provider: str = "native",
) -> dict[str, Any]:
    row = {
        "harness_name": harness,
        "model_id": model_id,
        "provider": provider,
        "discovery_source": discovery_source,
    }
    row.update(_rate_columns(harness, model_id, meta))
    row.update(_capability_columns(model_id, meta, from_probe=from_probe))
    row.update(_window_columns(harness, model_id, meta, discovery_source))
    return row


def _rows_from_probe_specs(specs: list[ModelSpec], *, provider: str = "native") -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        rows.append(_discovery_row(
            spec.harness_binding,
            spec.model_id,
            spec.discovery_source or f"cli:{spec.harness_binding}",
            spec.probe_rates,
            from_probe=True,
            provider=provider,
        ))
    return rows


def _curated_rows(harness: str) -> list[dict[str, Any]]:
    return [
        _discovery_row(harness, model.model_id, "curated_fallback", None, from_probe=False)
        for model in BUILTIN_MODEL_CATALOG
        if model.harness_binding == harness
    ]


def _discover_native_harness(harness: str) -> list[dict[str, Any]]:
    """Probe one native harness, then config, then the curated catalog."""
    if harness in CLI_MODEL_LIST_COMMANDS:
        specs = probe_cli_harness(harness)
        if specs:
            return _rows_from_probe_specs(specs)
    elif harness == "local":
        specs = probe_local_runtimes()
        if specs:
            return _rows_from_probe_specs(specs)
    else:
        reader = _CONFIG_MODEL_READERS.get(harness)
        if reader is not None:
            configured = reader()
            if configured:
                return [_discovery_row(harness, configured, "config_file", None, from_probe=False)]
    return _curated_rows(harness)


def _mark_absent_models_stale(conn, harness: str, provider: str, seen_ids: set[str]) -> None:
    """Mark active rows this pass did not see. History is kept."""
    if seen_ids:
        placeholders = ",".join("?" for _ in seen_ids)
        conn.execute(
            "UPDATE harness_models SET status='stale' "
            "WHERE harness_name=? AND provider=? AND status='active' "
            f"AND model_id NOT IN ({placeholders})",
            (harness, provider, *sorted(seen_ids)),
        )
        return
    conn.execute(
        "UPDATE harness_models SET status='stale' "
        "WHERE harness_name=? AND provider=? AND status='active'",
        (harness, provider),
    )


_DISCOVERY_UPSERT_KEYS = (
    "provider", "discovery_source",
    "rate_input_per_mtok", "rate_output_per_mtok", "rate_cache_read_per_mtok",
    "rate_cache_write_per_mtok", "rate_tool_use_per_mtok", "rate_source",
    "complexity_tier", "max_effort_level", "context_window_tokens", "max_output_tokens",
)


def _upsert_discovery_row(conn, row: dict[str, Any]) -> None:
    from synlynk.db import upsert_harness_model

    upsert_harness_model(
        conn,
        row["harness_name"],
        row["model_id"],
        **{key: row.get(key) for key in _DISCOVERY_UPSERT_KEYS},
    )


def run_model_catalog_discovery(conn) -> list[dict[str, Any]]:
    """Refresh harness_models from live probes, config, and curated fallback.

    Iterates ``HARNESS_CAPABILITY_BASELINES`` for ``provider='native'``.
    Gateway providers come from ``CONFIGURED_GATEWAY_PROVIDERS``, which is
    empty until adapters exist, so that loop does nothing today. Previously
    active rows absent from a scanned provider are marked ``status='stale'``.
    """
    rows: list[dict[str, Any]] = []
    for harness in _baseline_harness_names():
        discovered = _discover_native_harness(harness)
        for row in discovered:
            _upsert_discovery_row(conn, row)
        _mark_absent_models_stale(
            conn, harness, "native", {row["model_id"] for row in discovered},
        )
        rows.extend(discovered)

    for provider in iter_configured_gateway_providers():
        specs = probe_gateway_provider(provider)
        if not specs:
            continue
        grouped: dict[str, list[ModelSpec]] = {}
        for spec in specs:
            grouped.setdefault(spec.harness_binding, []).append(spec)
        for harness, group in grouped.items():
            discovered = _rows_from_probe_specs(group, provider=provider)
            for row in discovered:
                if not row.get("discovery_source") or str(row["discovery_source"]).startswith("cli:"):
                    row["discovery_source"] = "provider_api"
                if row.get("rate_source") == "cli_probe":
                    row["rate_source"] = "provider_api"
                _upsert_discovery_row(conn, row)
            _mark_absent_models_stale(
                conn, harness, provider, {row["model_id"] for row in discovered},
            )
            rows.extend(discovered)
    return rows


def cmd_models_discover(json_output: bool = False) -> list[dict[str, Any]]:
    from synlynk import _get_db
    conn = _get_db()
    try:
        rows = run_model_catalog_discovery(conn)
        conn.commit()
    finally:
        conn.close()
    if json_output:
        print(json.dumps(rows, indent=2))
    elif not rows:
        print("Discovered no additional models.")
    else:
        print("\n".join(f"{row['harness_name']}\t{row['model_id']}" for row in rows))
    return rows
