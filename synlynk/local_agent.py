"""synlynk local agent: config loading and oMLX reachability helpers for the
'local' dispatch agent. 'local' is dispatched as a real CLI subprocess (`aider`,
pointed at oMLX as an OpenAI-compatible backend) via the existing dispatch_agent()
machinery — this module owns only the config/flag-building helpers that invocation
needs, and the `synlynk local doctor` health-check command. It does not talk to
Aider or oMLX's chat-completions endpoint directly; Aider does that."""

import json
import os
import shutil
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
    """Returns the id of the pinned model, or the first roster entry if none pinned."""
    for model in config["models"]:
        if model.get("pinned"):
            return model["id"]
    return config["models"][0]["id"]


def _health_check(endpoint: str, timeout: int = 5) -> dict:
    """GETs {endpoint}/v1/models and reports reachability plus model ids."""
    req = urllib.request.Request(f"{endpoint}/v1/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {"reachable": False, "error": str(exc)}
    available = [m.get("id") for m in payload.get("data", [])]
    return {"reachable": True, "available_models": available}


def _local_dispatch_model_flags(config_path: str = None) -> list:
    """Builds aider model flags from .agents/local.json."""
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    endpoint = config["endpoint"]
    model_id = _pinned_model(config)
    model_entry = next((model for model in config["models"] if model["id"] == model_id), {})
    edit_format = model_entry.get("edit_format", "whole")
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", model_id,
        "--edit-format", edit_format,
    ]


def cmd_local_doctor(config_path: str = None) -> int:
    """Prints oMLX reachability plus roster status. Returns 0 if healthy, 1 otherwise."""
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
    result = _health_check(endpoint)
    if not result["reachable"]:
        print(f"  ✗ oMLX unreachable at {endpoint}: {result['error']}")
        print("    Start it with: omlx serve")
        return 1
    print(f"  ✓ oMLX reachable at {endpoint}")
    from synlynk.local_agent_seed import seed_local_capability_envelope
    seed_local_capability_envelope(_get_db())
    print("  ✓ starter capability envelope seeded (docs/testing, execute stage)")
    roster_ids = [model["id"] for model in config["models"]]
    available = set(result["available_models"])
    missing = [model_id for model_id in roster_ids if model_id not in available]
    for model_id in roster_ids:
        mark = "✓" if model_id not in missing else "✗"
        print(f"  {mark} {model_id}")
    if missing:
        print(f"    Missing models: {', '.join(missing)} — download via oMLX admin panel or CLI")
    aider_missing = shutil.which("aider") is None
    if aider_missing:
        print("  ✗ aider not found on PATH")
        print("    Install it with: pipx install aider-chat")
    else:
        print("  ✓ aider installed")
    if missing or aider_missing:
        return 1
    return 0
