"""Per-harness CLI manifests used to detect capability drift."""

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
            [cli_name, "--version"], capture_output=True, text=True, timeout=10
        )
        version_text = (result.stdout or result.stderr or "").strip()
    except Exception:
        version_text = "unknown"
    return hashlib.sha256(version_text.encode()).hexdigest()[:16]


def discover_and_validate(harness: str) -> dict:
    """Discover and persist the current CLI fingerprint for ``harness``."""
    baseline = HARNESS_CAPABILITY_BASELINES.get(harness, {})
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
