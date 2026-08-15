"""Delivery-of-effect verification for --requires-gh-write jobs."""

import json
import re
import subprocess
from typing import Optional


_TARGET_RE = re.compile(r"^(issue|pr):(\d+)$")
_EXPECT_FIELD = {
    "closed": ("state", "CLOSED"),
    "merged": ("state", "MERGED"),
}


def gh_write_verified(target: Optional[str], expect: str, timeout: int = 10) -> Optional[bool]:
    """Return whether a declared GitHub target has the expected state, or None if unknown."""
    if not target:
        return None
    match = _TARGET_RE.match(target)
    if not match or expect not in _EXPECT_FIELD:
        return None
    kind, number = match.groups()
    field, expected_value = _EXPECT_FIELD[expect]
    subcommand = "issue" if kind == "issue" else "pr"
    cmd = ["gh", subcommand, "view", number, "--json", field]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    actual = payload.get(field)
    return None if actual is None else actual == expected_value
