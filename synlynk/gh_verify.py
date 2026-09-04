"""Delivery-of-effect verification for --requires-gh-write jobs."""

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional


_TARGET_RE = re.compile(r"^(issue|pr):(\d+)$")
_EXPECT_FIELD = {
    "closed": ("state", "CLOSED"),
    "merged": ("state", "MERGED"),
    "pr_open": ("state", "OPEN"),
}
_LIST_EXPECT_FIELD = {
    "review_posted": "reviews",
    "comment_posted": "comments",
}
_LIST_VERIFY_ATTEMPTS = 3
_LIST_VERIFY_BACKOFF_SECONDS = (0.1, 0.25)


def _parse_iso8601(value: Optional[str]):
    """Parse an ISO8601 timestamp, normalizing a trailing ``Z`` for Python <3.11.

    Return None for missing or malformed input. Callers treat an unparseable
    timestamp as unknown, matching the contract of the rest of this module.
    """
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def gh_write_verified(
    target: Optional[str],
    expect: str,
    timeout: int = 10,
    since: Optional[str] = None,
    expect_author: Optional[str] = None,
    evidence: Optional[dict] = None,
) -> Optional[bool]:
    """Return whether a declared GitHub target reached the expected state, or None if unknown.

    ``expect='closed'``/``'merged'``/``'pr_open'`` checks a scalar state field
    (original #701 behavior). ``expect='created'`` checks that the target
    exists, regardless of its current state. ``expect='review_posted'``/``'comment_posted'`` checks
    whether a reviews/comments list entry exists at or after ``since``,
    optionally matching ``expect_author``'s login.

    ``since`` is required for the two list-based expect values. Without a time
    floor, a write from days earlier would false-positive every later job on
    the same PR.
    """
    if not target:
        return None
    match = _TARGET_RE.match(target)
    if not match:
        return None
    kind, number = match.groups()
    subcommand = "issue" if kind == "issue" else "pr"

    if expect == "created":
        field = "state"
        cmd = ["gh", subcommand, "view", number, "--json", field]
    elif expect in _EXPECT_FIELD:
        field, expected_value = _EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    elif expect in _LIST_EXPECT_FIELD:
        if not since:
            return None
        field = _LIST_EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    else:
        return None

    is_list_expect = expect in _LIST_EXPECT_FIELD
    attempts = _LIST_VERIFY_ATTEMPTS if is_list_expect else 1
    if evidence is not None:
        evidence.update({"target": target, "expect": expect, "field": field, "attempts": []})

    for attempt in range(attempts):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            if evidence is not None:
                evidence["attempts"].append({"error": type(exc).__name__, "matched": None})
            payload = None
        else:
            try:
                payload = json.loads(result.stdout) if result.returncode == 0 else None
            except (json.JSONDecodeError, ValueError):
                payload = None
            if evidence is not None:
                evidence["attempts"].append({
                    "raw": result.stdout,
                    "reviews": (payload or {}).get(field) if isinstance(payload, dict) else None,
                    "matched": None,
                })
        if payload is None:
            if attempt + 1 < attempts:
                time.sleep(_LIST_VERIFY_BACKOFF_SECONDS[min(attempt, len(_LIST_VERIFY_BACKOFF_SECONDS) - 1)])
                continue
            return None

        if expect == "created":
            return payload.get("state") is not None

        if expect in _EXPECT_FIELD:
            actual = payload.get(field)
            return None if actual is None else actual == expected_value

        entries = payload.get(field)
        if entries is None:
            matched = None
        else:
            since_dt = _parse_iso8601(since)
            matched = False if since_dt is not None else None
            if since_dt is not None:
                for entry in entries:
                    entry_time = entry.get("submittedAt") or entry.get("createdAt")
                    entry_dt = _parse_iso8601(entry_time)
                    if entry_dt is None or entry_dt < since_dt:
                        continue
                    if expect_author and (entry.get("author") or {}).get("login") != expect_author:
                        continue
                    matched = True
                    break
        if evidence is not None:
            evidence["attempts"][-1]["matched"] = matched
        if matched is True:
            if evidence is not None:
                evidence["matched"] = True
                evidence["attempt_count"] = attempt + 1
            return True
        if matched is None:
            if attempt + 1 < attempts:
                time.sleep(_LIST_VERIFY_BACKOFF_SECONDS[min(attempt, len(_LIST_VERIFY_BACKOFF_SECONDS) - 1)])
                continue
            return None
        if attempt + 1 < attempts:
            time.sleep(_LIST_VERIFY_BACKOFF_SECONDS[min(attempt, len(_LIST_VERIFY_BACKOFF_SECONDS) - 1)])
            continue
        if evidence is not None:
            evidence["matched"] = False
            evidence["attempt_count"] = attempt + 1
        return False
