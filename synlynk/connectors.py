"""Product-scoped connector catalog and secret-isolation primitives (W8)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from synlynk.product_store import connectors_dir, ensure_product_dirs
from synlynk.types_registry import TypeExists, load_types, type_create


SUPPORTED_PROTOCOLS = frozenset({"api_key", "bearer_token", "basic", "oauth", "gateway"})
REACH_VALUES = frozenset({"home_repo", "all_product_repos"})


class ConnectorInvalid(ValueError):
    """Raised when a connector is not safe to catalog or dispatch."""


def _normalize_reach(home_repo: str, reach: str | list[str] | tuple[str, ...]) -> dict[str, Any]:
    if isinstance(reach, str):
        values = [item.strip() for item in reach.split(",") if item.strip()]
    else:
        values = [str(item).strip() for item in reach if str(item).strip()]
    if not values:
        raise ConnectorInvalid("connector reach is required")
    if len(values) == 1 and values[0] in REACH_VALUES:
        return {"mode": values[0], "repos": [home_repo]}
    if any(value in REACH_VALUES for value in values):
        raise ConnectorInvalid("connector reach must be home_repo, all_product_repos, or explicit repositories")
    return {"mode": "explicit_repos", "repos": values}


def validate_connector_spec(
    *, type_id: str, home_repo: str, reach: str | list[str], allowlist: list[str],
    protocol: str, provider: str | None = None,
) -> dict[str, Any]:
    if not type_id.strip():
        raise ConnectorInvalid("connector type_id is required")
    if not home_repo.strip():
        raise ConnectorInvalid("connector home repo is required")
    if not allowlist or not all(isinstance(item, str) and item.strip() for item in allowlist):
        raise ConnectorInvalid("connector allowlist must not be empty")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ConnectorInvalid(f"unknown connector protocol: {protocol}")
    if protocol == "gateway" and provider is not None and not provider.strip():
        raise ConnectorInvalid("gateway provider must be non-empty when supplied")
    return {
        "type_id": type_id,
        "kind": "connector",
        "home_repo": home_repo,
        "reach": _normalize_reach(home_repo, reach),
        "allowlist": sorted({item.strip() for item in allowlist}),
        "protocol": protocol,
        **({"provider": provider} if provider else {}),
    }


def connector_metadata_path(slug: str, type_id: str) -> Path:
    return connectors_dir(slug) / type_id / "credentials.json"


def connector_secret_path(slug: str, type_id: str) -> Path:
    return connectors_dir(slug) / type_id / "secret"


def add_connector(
    slug: str, *, type_id: str, home_repo: str, reach: str | list[str],
    allowlist: list[str], protocol: str, provider: str | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Catalog a connector and optionally write its secret without returning it."""
    metadata = validate_connector_spec(
        type_id=type_id, home_repo=home_repo, reach=reach,
        allowlist=allowlist, protocol=protocol, provider=provider,
    )
    types = load_types(slug)
    existing = types.get(type_id)
    if existing is None:
        type_create(slug, type_id, "connector")
    elif existing.get("kind") != "connector":
        raise ConnectorInvalid(f"type {type_id!r} already exists with kind {existing.get('kind')!r}")
    ensure_product_dirs(slug)
    target = connectors_dir(slug) / type_id
    target.mkdir(parents=True, exist_ok=True)
    connector_metadata_path(slug, type_id).write_text(json.dumps(metadata, indent=2) + "\n")
    if secret is not None:
        secret_path = connector_secret_path(slug, type_id)
        secret_path.write_text(secret)
        os.chmod(secret_path, 0o600)
    return metadata


def connector_is_dispatchable(slug: str, type_id: str) -> bool:
    """Return whether catalog metadata is valid; never reads the secret."""
    entry = load_types(slug).get(type_id, {})
    if entry.get("kind") != "connector":
        return True
    try:
        metadata = json.loads(connector_metadata_path(slug, type_id).read_text())
        validate_connector_spec(
            type_id=type_id, home_repo=metadata["home_repo"], reach=metadata["reach"]["mode"],
            allowlist=metadata["allowlist"], protocol=metadata["protocol"],
            provider=metadata.get("provider"),
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ConnectorInvalid):
        return False
    return True
