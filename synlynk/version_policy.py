"""Version negotiation and upgrade planning across workspaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _parse_version(v_str: str) -> Tuple[int, ...]:
    """Parse a dotted version, ignoring a leading ``v`` and prerelease suffix."""

    clean = str(v_str).strip().lstrip("v").split("-", 1)[0]
    try:
        return tuple(int(part) for part in clean.split("."))
    except (TypeError, ValueError):
        return (0, 0, 0)


def check_version_policy(repo_dir: str, current_version: str) -> Tuple[bool, str]:
    """Check whether ``current_version`` meets a repository's minimum version."""

    config_path = Path(repo_dir) / ".synlynk" / "config.json"
    if not config_path.is_file():
        return True, "No version policy defined"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, "Invalid config"

    policy = config.get("version_policy", {}) if isinstance(config, dict) else {}
    minimum = policy.get("min_version") if isinstance(policy, dict) else None
    if not minimum:
        return True, "No min_version specified"

    if _parse_version(current_version) < _parse_version(minimum):
        return False, (
            f"Installed synlynk {current_version} is below workspace "
            f"required min_version {minimum}"
        )
    return True, "Version requirement satisfied"


def plan_upgrade(repo_dirs: List[str], dry_run: bool = True) -> Dict[str, Any]:
    """Return an explicit upgrade plan for each requested workspace.

    This function only describes targets; applying upgrades remains an explicit
    operation owned by the lifecycle CLI.
    """

    targets = [
        {"path": repo_dir, "current_status": "ready", "dry_run": dry_run}
        for repo_dir in repo_dirs
    ]
    return {"dry_run": dry_run, "targets": targets, "safe_to_apply": True}
