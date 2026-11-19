"""Discovery and persistence of per-harness CLI manifests."""

import hashlib
import json
import os
import subprocess

from synlynk._constants import HARNESS_CAPABILITY_BASELINES

MANIFEST_SCHEMA_VERSION = 1
HARNESS_BILLING_CONFIG_INVALID = "HARNESS_BILLING_CONFIG_INVALID"
_MANIFEST_DIR = os.path.join(".synlynk", "harnesses")


def _cli_version_hash(cli_name: str) -> str:
    try:
        result = subprocess.run([cli_name, "--version"], capture_output=True, text=True, timeout=10)
        version = (result.stdout or result.stderr or "").strip()
    except Exception:
        version = "unknown"
    return hashlib.sha256(version.encode()).hexdigest()[:16]


def _billing_rate_configured(harness: str) -> bool:
    from synlynk.costs import _payment_model_config_for_agent

    mode = (_payment_model_config_for_agent(harness) or {}).get("mode", "pay_as_you_go")
    if mode == "subscription":
        return True
    path = os.path.join(".synlynk", "billing.json")
    try:
        with open(path) as handle:
            rate = json.load(handle).get(harness, {}).get("cost_per_1k_tokens")
        return isinstance(rate, dict) and "input" in rate and "output" in rate
    except (OSError, ValueError, TypeError):
        return False


def discover_and_validate(harness: str) -> dict:
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    if not _billing_rate_configured(harness):
        raise ValueError(f"{HARNESS_BILLING_CONFIG_INVALID}: {harness} has no billing rate configured")
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "harness": harness,
        "models": baseline.get("models", []),
        "native_cli_flags": baseline.get("dispatch_flags", {}),
        "auth_model": baseline.get("panel_auth_check", {}),
        "mcp_tools": baseline.get("mcp_tools", []),
        "cli_version_hash": _cli_version_hash(baseline.get("cli", harness)),
        "last_validated_smoke_run": None,
    }
    os.makedirs(_MANIFEST_DIR, exist_ok=True)
    with open(os.path.join(_MANIFEST_DIR, f"{harness}.json"), "w") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest
