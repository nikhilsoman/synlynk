"""Resolve the current repo's owner/name for gh_sync calls."""

import json
import subprocess


def resolve_owner_repo() -> tuple[str, str]:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh repo view failed: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    return info["owner"]["login"], info["name"]
