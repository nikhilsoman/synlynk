"""Load repo-specific capability role mappings."""

import json
import os
from typing import Optional


def _load_capability_roles(config_dir: str = ".synlynk") -> Optional[dict]:
    """Load repo-specific capability roles if the committed file exists."""
    path = os.path.join(config_dir, "capability-roles.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            payload = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    roles = payload.get("roles")
    return roles if isinstance(roles, dict) else None
