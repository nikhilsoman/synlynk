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


def _workspace_root(workspace_id: str) -> str:
    return os.path.expanduser(os.path.join("~", ".synlynk", "workspaces", workspace_id))


def agent_store_path(agent_id: str) -> str:
    """Resolve the canonical on-disk directory for one agent's artifacts."""
    workspace_id = get_workspace_id()
    return os.path.join(_workspace_root(workspace_id), "agents", agent_id)


def _registry_path() -> str:
    workspace_id = get_workspace_id()
    return os.path.join(_workspace_root(workspace_id), "agents", "registry.json")


def _load_registry() -> dict:
    path = _registry_path()
    if not os.path.exists(path):
        return {"agents": []}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"agents": []}


def register_agent(agent_id: str, aliases: list) -> None:
    """Register a new agent_id with its aliases. Fails loudly on any collision.

    aliases: list of {"kind": str, "value": str} dicts.
    """
    registry = _load_registry()
    existing_ids = {a["agent_id"] for a in registry["agents"]}
    if agent_id in existing_ids:
        raise ValueError(f"agent_id {agent_id!r} is already registered")

    existing_values = {
        alias["value"] for agent in registry["agents"] for alias in agent["aliases"]
    }
    for alias in aliases:
        if alias["value"] in existing_values:
            raise ValueError(f"alias {alias['value']!r} is already registered to another agent")

    registry["agents"].append({
        "agent_id": agent_id,
        "created_at": _now_iso(),
        "aliases": aliases,
        "history": [{"event": "created", "at": _now_iso()}],
    })
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _write_json_atomic(path, registry)


def resolve_agent_id(alias: str) -> str:
    """Resolve an alias to its canonical agent_id, or None if unregistered.

    Never guesses — an unregistered alias returns None, it does not fork a
    new agent record.
    """
    registry = _load_registry()
    for agent in registry["agents"]:
        for a in agent["aliases"]:
            if a["value"] == alias:
                return agent["agent_id"]
    return None


class RevisionConflictError(Exception):
    """Raised when a proposed revision's parent_revision doesn't match the current head."""


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_versioned_file(file_path: str, revisions_path: str):
    """Return (content, current_revision) for a single-file versioned artifact."""
    if not os.path.exists(file_path):
        return "", 0
    with open(file_path) as f:
        content = f.read()
    revision = 0
    if os.path.exists(revisions_path):
        with open(revisions_path) as f:
            revision = sum(1 for line in f if line.strip())
    return content, revision


def _write_versioned_file(
    file_path: str,
    revisions_path: str,
    content: str,
    actor: str,
    parent_revision: int,
) -> int:
    """Write a new revision of a single-file versioned artifact.

    Raises RevisionConflictError on stale parent_revision.
    """
    _, current_revision = _read_versioned_file(file_path, revisions_path)
    if parent_revision != current_revision:
        raise RevisionConflictError(
            f"parent_revision {parent_revision} does not match current head {current_revision}"
        )
    parent_hash = None
    if current_revision > 0:
        with open(file_path) as f:
            parent_hash = _content_hash(f.read())

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

    new_revision = current_revision + 1
    entry = {
        "revision": new_revision,
        "parent_hash": parent_hash,
        "content_hash": _content_hash(content),
        "actor": actor,
        "timestamp": _now_iso(),
    }
    with open(revisions_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return new_revision


def read_charter(agent_id: str):
    """Return (content, current_revision) for an agent's charter."""
    base = agent_store_path(agent_id)
    return _read_versioned_file(
        os.path.join(base, "charter.md"),
        os.path.join(base, "charter.revisions.jsonl"),
    )


def propose_charter_revision(
    agent_id: str, content: str, actor: str, parent_revision: int
) -> int:
    """Write a new charter revision if parent_revision matches the current head.

    No auto-approval logic is included; the gated mutability tier is out of scope.
    """
    base = agent_store_path(agent_id)
    return _write_versioned_file(
        os.path.join(base, "charter.md"),
        os.path.join(base, "charter.revisions.jsonl"),
        content,
        actor,
        parent_revision,
    )
