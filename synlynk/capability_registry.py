"""Capability Registry: a unified manifest shape for native code hooks,
local-harness-installed MCPs/Skills, and (held pending spec §3a.4/Phase 7)
remote third-party connectors. See spec §4.

This module implements only the native-hook source (Phase 5). Local-harness
and remote sources are separate modules (capability_registry_local.py,
Phase 6; remote ingestion stays out of scope per spec §7 until the Phase 7
trust/dedup gate lands).
"""
import json
import os

NATIVE_REGISTRY_DIR = os.path.join(".synlynk", "capability_registry", "native")

REQUIRED_MANIFEST_FIELDS = (
    "capability_id", "name", "source", "description", "purpose", "scope",
    "auth", "harness_compat", "workspace_id", "owner", "version",
)


def _validate_manifest(manifest: dict, path: str) -> None:
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        raise ValueError(f"{path}: missing required manifest field(s): {', '.join(missing)}")


def load_native_capabilities() -> list:
    """Load and validate every native-hook manifest under NATIVE_REGISTRY_DIR.

    Returns [] if the directory does not exist (no native capabilities
    registered yet — not an error).
    """
    if not os.path.isdir(NATIVE_REGISTRY_DIR):
        return []
    capabilities = []
    for name in sorted(os.listdir(NATIVE_REGISTRY_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(NATIVE_REGISTRY_DIR, name)
        with open(path) as fh:
            manifest = json.load(fh)
        _validate_manifest(manifest, path)
        capabilities.append(manifest)
    return capabilities


LOCAL_REGISTRY_DIR = os.path.join(".synlynk", "capability_registry", "local")


def load_local_capabilities(harness: str = None) -> list:
    """Load local_harness-source manifests, optionally filtered to those whose
    harness_compat includes `harness` (or is the literal string "any").
    """
    if not os.path.isdir(LOCAL_REGISTRY_DIR):
        return []
    capabilities = []
    for name in sorted(os.listdir(LOCAL_REGISTRY_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(LOCAL_REGISTRY_DIR, name)
        with open(path) as fh:
            manifest = json.load(fh)
        _validate_manifest(manifest, path)
        compat = manifest.get("harness_compat")
        if harness is not None and compat != "any" and harness not in (compat or []):
            continue
        capabilities.append(manifest)
    return capabilities

