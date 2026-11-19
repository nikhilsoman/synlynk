"""Discover and validate per-harness routing manifests."""

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
        result = subprocess.run(
            [cli_name, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version_text = (result.stdout or result.stderr or "").strip()
    except Exception:
        version_text = "unknown"
    return hashlib.sha256(version_text.encode()).hexdigest()[:16]


def _billing_rate_configured(harness: str) -> bool:
    from synlynk.costs import _payment_model_config_for_agent

    mode = (_payment_model_config_for_agent(harness) or {}).get("mode", "pay_as_you_go")
    if mode == "subscription":
        return True

    billing_path = os.path.join(".synlynk", "billing.json")
    if not os.path.exists(billing_path):
        return False
    try:
        with open(billing_path, encoding="utf-8") as handle:
            billing = json.load(handle)
        rate = billing.get(harness, {}).get("cost_per_1k_tokens")
        return isinstance(rate, dict) and "input" in rate and "output" in rate
    except (OSError, TypeError, ValueError):
        return False


def discover_and_validate(harness: str) -> dict:
    """Discover a harness's CLI shape and write its local manifest."""
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
    if not _billing_rate_configured(harness):
        raise ValueError(
            f"{HARNESS_BILLING_CONFIG_INVALID}: {harness} is billed per-token "
            "but has no cost_per_1k_tokens configured in .synlynk/billing.json"
        )

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
    with open(os.path.join(_MANIFEST_DIR, f"{harness}.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest
