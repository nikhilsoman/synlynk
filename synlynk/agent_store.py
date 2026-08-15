"""Workspace-level storage for durable agents' charter, memory, and
Statements of Record. See docs/superpowers/specs/2026-08-15-workspace-agent-artifact-storage-design.md.
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from synlynk import _write_json_atomic

_CONFIG_PATH = os.path.join(".synlynk", "config.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_raw_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return {}
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def get_workspace_id() -> str:
    """Return this repo's workspace_id, minting and persisting one on first call.

    Each repo currently gets its own workspace_id (no cross-repo sharing yet —
    see design spec Conflict B). Never overwrites an existing value.
    """
    config = _load_raw_config()
    existing = config.get("workspace_id")
    if existing:
        return existing
    workspace_id = str(uuid.uuid4())
    config["workspace_id"] = workspace_id
    _write_json_atomic(_CONFIG_PATH, config)
    return workspace_id
