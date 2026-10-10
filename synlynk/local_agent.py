"""synlynk local agent: config loading and oMLX reachability helpers for the
'local' dispatch agent. 'local' is dispatched as a real CLI subprocess (`aider`,
pointed at oMLX as an OpenAI-compatible backend) via the existing dispatch_agent()
machinery — this module owns only the config/flag-building helpers that invocation
needs, and the `synlynk local doctor` health-check command. It does not talk to
Aider or oMLX's chat-completions endpoint directly; Aider does that."""

import json
import importlib.util
import os
import shutil
import subprocess as _subprocess
import sys
import urllib.error
import urllib.request

from synlynk import _get_db

_DEFAULT_CONFIG_PATH = os.path.join(".agents", "local.json")
_DEFAULT_LOCAL_CONFIG = {
    "name": "local",
    "endpoint": "http://127.0.0.1:8000",
    "models": [
        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
        {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
        {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
    ],
    "hardware_tier": "16gb-default",
}


def _check_prism_ml_available() -> bool:
    """Returns True if the prism-ml package is importable (needed for Ternary-Bonsai)."""
    return importlib.util.find_spec("prism_ml") is not None


_TIER_THRESHOLDS = [
    (12 * 1024**3, "8gb-light"),
    (20 * 1024**3, "16gb-default"),
    (48 * 1024**3, "32gb-pro"),
    (float("inf"), "64gb-fleet"),
]


def _detect_hardware_tier() -> str:
    """Detect RAM and return the corresponding local hardware tier.

    Uses ``sysctl`` on macOS and ``/proc/meminfo`` on Linux. Detection
    failures conservatively fall back to the default tier.
    """
    try:
        if sys.platform == "darwin":
            raw = _subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], timeout=5
            )
            ram_bytes = int(raw.strip())
        else:
            with open("/proc/meminfo") as meminfo:
                for line in meminfo:
                    if line.startswith("MemTotal:"):
                        ram_bytes = int(line.split()[1]) * 1024
                        break
                else:
                    return "16gb-default"
    except Exception:
        return "16gb-default"

    for threshold, tier in _TIER_THRESHOLDS:
        if ram_bytes < threshold:
            return tier
    return "64gb-fleet"


def _select_model_for_tier(tier: str, config: dict) -> str:
    """Return the best available model id for a hardware tier."""
    candidates = [
        model for model in config["models"] if tier in model.get("tier", [])
    ]
    eligible = [
        model for model in candidates
        if not (
            model.get("loader") == "prism-ml"
            and not _check_prism_ml_available()
        )
    ]
    if eligible:
        return eligible[0]["id"]

    fallback = next(
        (model for model in config["models"] if not model.get("loader")),
        None,
    )
    if fallback:
        return fallback["id"]
    return config["models"][0]["id"]


def _load_local_config(path: str = None) -> dict:
    """Reads and parses .agents/local.json. Raises FileNotFoundError if missing."""
    if path is None:
        path = _DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `synlynk local doctor` for setup guidance."
        )
    with open(path) as f:
        return json.load(f)


def _pinned_model(config: dict) -> str:
    """Returns the pinned model id, or the first roster entry if none is pinned."""
    if "pinned_model" in config:
        return config["pinned_model"]
    for model in config["models"]:
        if model.get("pinned"):
            return model["id"]
    return config["models"][0]["id"]


def _health_check(endpoint: str, timeout: int = 5, api_key: str = None) -> dict:
    """GETs {endpoint}/v1/models and reports reachability plus model ids."""
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{endpoint}/v1/models", method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {"reachable": False, "error": str(exc)}
    available = [m.get("id") for m in payload.get("data", [])]
    return {"reachable": True, "available_models": available}


def _orbstack_health_check(timeout: int = 3) -> dict:
    """Return whether OrbStack is installed and running.

    This is intentionally separate from ``_health_check``: a reachable oMLX
    endpoint does not prove that the container runtime needed by a
    containerized local setup is available.
    """
    orbctl = shutil.which("orbctl")
    if orbctl is None:
        return {"reachable": False, "error": "orbctl is not installed or not on PATH"}
    try:
        result = _subprocess.run(
            [orbctl, "status"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, _subprocess.TimeoutExpired) as exc:
        return {"reachable": False, "error": str(exc)}
    status = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0 or "running" not in status.lower():
        detail = status or "status check failed"
        return {"reachable": False, "error": detail}
    return {"reachable": True}


_STARTER_TIER_GUARDRAIL_FLAGS = [
    "--no-auto-lint",
    "--no-auto-test",
    "--map-tokens", "0",
]


def _local_dispatch_model_flags(config_path: str = None) -> list:
    """Builds aider model flags from .agents/local.json.

    Always appends Starter-tier safety guardrails (no autonomous lint/test
    execution, no repo-map context) - see
    docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
    Full-tier flags (--architect, auto-lint/auto-test: true) are a future,
    separately-gated change and must not be added here.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    endpoint = config["endpoint"]
    model_id = _pinned_model(config)

    def _entry_for(mid):
        return next((model for model in config["models"] if model["id"] == mid), {})

    model_entry = _entry_for(model_id)
    if model_entry.get("loader") == "prism-ml" and not _check_prism_ml_available():
        fallback = next((model for model in config["models"] if not model.get("loader")), None)
        if fallback is None:
            return []
        model_id = fallback["id"]
        model_entry = fallback
    edit_format = model_entry.get("edit_format", "whole")
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", f"openai/{model_id}",
        "--edit-format", edit_format,
    ] + _STARTER_TIER_GUARDRAIL_FLAGS


def cmd_local_doctor(config_path: str = None, init: bool = False) -> int:
    """Print oMLX reachability, roster status, and hardware recommendation.

    With ``init=True``, write the detected ``hardware_tier`` and recommended
    ``pinned_model`` back to the local config.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError as exc:
        if config_path == _DEFAULT_CONFIG_PATH:
            config = _DEFAULT_LOCAL_CONFIG
        else:
            print(f"  ✗ {exc}")
            return 1
    endpoint = config["endpoint"]
    api_key = os.environ.get("OPENAI_API_KEY")
    result = _health_check(endpoint, api_key=api_key)
    if not result["reachable"]:
        print(f"  ✗ oMLX unreachable at {endpoint}: {result['error']}")
        if "401" in result["error"]:
            print("    oMLX rejected the request (401 Unauthorized) — export OPENAI_API_KEY and retry")
        else:
            print("    Start it with: omlx serve")
        return 1
    print(f"  ✓ oMLX reachable at {endpoint}")
    tier = _detect_hardware_tier()
    best_model = _select_model_for_tier(tier, config)
    print(f"  ✓ hardware tier: {tier}")
    print(f"  ✓ recommended model: {best_model}")
    if init:
        config["hardware_tier"] = tier
        config["pinned_model"] = best_model
        write_path = config_path or _DEFAULT_CONFIG_PATH
        with open(write_path, "w") as f:
            json.dump(config, f, indent=2)
        print(
            f"  ✓ wrote hardware_tier={tier!r} and "
            f"pinned_model={best_model!r} to {write_path}"
        )
    from synlynk.local_agent_seed import seed_local_capability_envelope
    seed_local_capability_envelope(_get_db())
    print("  ✓ starter capability envelope seeded (docs/testing, execute stage)")
    available = set(result["available_models"])
    missing = [model["id"] for model in config["models"] if model["id"] not in available]
    for model in config["models"]:
        model_id = model["id"]
        in_roster = model_id not in missing
        loader = model.get("loader")
        loader_ok = True
        loader_note = ""
        if loader == "prism-ml":
            loader_ok = _check_prism_ml_available()
            loader_note = " [prism-ml: ✓]" if loader_ok else " [prism-ml: ✗ — pip install prism-ml]"
        mark = "✓" if (in_roster and loader_ok) else ("⚠" if in_roster else "✗")
        print(f"  {mark} {model_id}{loader_note}")
    if missing:
        print(f"    Missing from oMLX roster: {', '.join(missing)}")
    aider_missing = shutil.which("aider") is None
    if aider_missing:
        print("  ✗ aider not found on PATH")
        print("    Install it with: pipx install aider-chat")
    else:
        print("  ✓ aider installed")
    if missing or aider_missing:
        return 1
    return 0
