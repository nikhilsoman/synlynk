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


def list_agents() -> list:
    """Return all registry entries (agent_id, aliases, disabled, created_at, history)."""
    return _load_registry()["agents"]


def set_agent_disabled(agent_id: str, actor: str) -> None:
    """Idempotently mark an agent disabled, appending a history event."""
    registry = _load_registry()
    for entry in registry["agents"]:
        if entry["agent_id"] == agent_id:
            if entry.get("disabled"):
                return
            entry["disabled"] = True
            entry["history"].append(
                {"event": "disabled", "at": _now_iso(), "actor": actor}
            )
            _write_json_atomic(_registry_path(), registry)
            return


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


_ENTRY_CATEGORIES = ("memory", "statements-of-record")


def _entry_file_path(agent_id: str, category: str, entry_name: str) -> str:
    assert category in _ENTRY_CATEGORIES, f"unknown category {category}"
    return os.path.join(agent_store_path(agent_id), category, f"{entry_name}.md")


def _entry_revisions_path(agent_id: str, category: str) -> str:
    assert category in _ENTRY_CATEGORIES, f"unknown category {category}"
    return os.path.join(agent_store_path(agent_id), category, "revisions.jsonl")


def _current_entry_revision(revisions_path: str, entry_name: str) -> int:
    if not os.path.exists(revisions_path):
        return 0
    count = 0
    with open(revisions_path) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["entry"] == entry_name:
                count += 1
    return count


def _latest_entry_content_hash(revisions_path: str, entry_name: str):
    if not os.path.exists(revisions_path):
        return None
    latest = None
    with open(revisions_path) as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["entry"] == entry_name:
                latest = row
    return latest["content_hash"] if latest else None


def read_entry(agent_id: str, category: str, entry_name: str):
    """Return (content, current_revision) for one named entry in memory/ or statements-of-record/."""
    file_path = _entry_file_path(agent_id, category, entry_name)
    revisions_path = _entry_revisions_path(agent_id, category)
    if not os.path.exists(file_path):
        return "", 0
    with open(file_path) as f:
        content = f.read()
    return content, _current_entry_revision(revisions_path, entry_name)


def propose_entry_revision(
    agent_id: str,
    category: str,
    entry_name: str,
    content: str,
    actor: str,
    parent_revision: int,
) -> int:
    """Write a new revision of one named entry.

    Raises RevisionConflictError on stale parent_revision.
    """
    file_path = _entry_file_path(agent_id, category, entry_name)
    revisions_path = _entry_revisions_path(agent_id, category)

    current_revision = _current_entry_revision(revisions_path, entry_name)
    if parent_revision != current_revision:
        raise RevisionConflictError(
            f"parent_revision {parent_revision} does not match current head "
            f"{current_revision} for entry {entry_name}"
        )
    parent_hash = _latest_entry_content_hash(revisions_path, entry_name)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

    new_revision = current_revision + 1
    entry_row = {
        "entry": entry_name,
        "revision": new_revision,
        "parent_hash": parent_hash,
        "content_hash": _content_hash(content),
        "actor": actor,
        "timestamp": _now_iso(),
    }
    with open(revisions_path, "a") as f:
        f.write(json.dumps(entry_row) + "\n")
    return new_revision


def _dump_flat_yaml(data: dict, indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for key, value in data.items():
        if value is None:
            lines.append(f"{pad}{key}: null")
        elif isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key}: {{}}")
            else:
                lines.append(f"{pad}{key}:")
                lines.append(_dump_flat_yaml(value, indent + 1))
        else:
            lines.append(f"{pad}{key}: {value}")
    return "\n".join(lines)


def _agent_role(agent_id: str) -> str:
    registry = _load_registry()
    for agent in registry["agents"]:
        if agent["agent_id"] == agent_id:
            for alias in agent["aliases"]:
                if alias["kind"] == "role_slug":
                    return alias["value"]
    return ""


def regenerate_agent_projection(agent_id: str, repo_overrides: dict = None) -> None:
    workspace_id = get_workspace_id()
    payload = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "role": _agent_role(agent_id),
        "overrides": repo_overrides or {},
    }
    rendered = _dump_flat_yaml(payload) + "\n"

    projection_dir = os.path.join(".synlynk", "agents")
    os.makedirs(projection_dir, exist_ok=True)
    projection_path = os.path.join(projection_dir, f"{agent_id}.yaml")
    with open(projection_path, "w") as f:
        f.write(rendered)
