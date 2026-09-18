"""Fail-closed primitives for the bounded workspace-identity Wave 6 slice."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional


class MembershipUnavailable(RuntimeError):
    """Raised when membership cannot be verified by a configured minter."""


class GraphUnavailable(RuntimeError):
    """Raised when the product graph API has no configured minter."""


def accept_membership(invite: str, path: str = ".synlynk/membership.json") -> dict:
    """Record an explicit, opaque membership receipt without minting keys."""
    if not isinstance(invite, str) or not invite.strip():
        raise MembershipUnavailable("membership invite is required; join does not initialize identity material")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": 1, "status": "pending", "invite": invite.strip()}
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def connector_dispatch_allowed(role: str, grants: Optional[list[str]] = None) -> bool:
    """Allow connector roles only with an explicit connector grant."""
    if not role:
        return True
    try:
        from synlynk.product_store import identity_slug_from_config
        from synlynk.types_registry import load_types
        slug = identity_slug_from_config(".")
        kind = (load_types(slug).get(role) or {}).get("kind")
    except (OSError, ValueError, json.JSONDecodeError):
        kind = None
    if kind != "connector":
        return True
    try:
        from synlynk.connectors import connector_is_dispatchable
        if not connector_is_dispatchable(slug, role):
            return False
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return "connector" in set(grants or []) or "connector-dispatch" in set(grants or [])


def graph_read(fetch: Optional[Callable[[], dict]] = None) -> dict:
    """Read graph data through an API-shaped seam, failing closed by default."""
    if fetch is None:
        raise GraphUnavailable("graph minter/API is not configured; refusing local graph fallback")
    result = fetch()
    if not isinstance(result, dict):
        raise GraphUnavailable("graph API returned an invalid response")
    return result


def hosted_vizor_placeholder(slug: str) -> dict:
    """Return the named hosted Vizor placeholder without starting a host."""
    safe = re.sub(r"[^a-z0-9-]+", "-", str(slug).lower()).strip("-") or "product"
    return {"status": "unavailable", "url": f"https://synlynk.com/{safe}",
            "message": "Hosted Vizor is not available in this slice; no OAuth or hosting is configured."}
