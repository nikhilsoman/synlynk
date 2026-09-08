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


def _naive_local_tz():
    """Timezone used when daemon_jobs.started_at is stored without an offset."""
    return datetime.now().astimezone().tzinfo


def _parse_iso8601(value, naive_as: str = "utc"):
    """Parse an ISO8601 timestamp, normalizing a trailing ``Z`` for Python <3.11.
    Also accepts datetime instances and normalizes to timezone-aware UTC.

    Return None for missing or malformed input. Callers treat an unparseable
    timestamp as unknown, matching the contract of the rest of this module.

    ``naive_as`` is ``utc`` (default, historical contract) or ``local``
    (daemon_jobs.started_at is local wall time with no offset).
    """
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            tz = timezone.utc if naive_as != "local" else _naive_local_tz()
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            tz = timezone.utc if naive_as != "local" else _naive_local_tz()
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _compare_dt_lt(a: Optional[datetime], b: Optional[datetime]) -> bool:
    """Return True if a < b, safely normalizing both operands to timezone-aware UTC."""
    if a is None or b is None:
        return False
    try:
        a_utc = a if a.tzinfo is not None else a.replace(tzinfo=timezone.utc)
        b_utc = b if b.tzinfo is not None else b.replace(tzinfo=timezone.utc)
        return a_utc.astimezone(timezone.utc) < b_utc.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return False


def _normalize_gh_login(login: Optional[str]) -> str:
    value = (login or "").strip().lower()
    if value.endswith("[bot]"):
        return value[:-5]
    return value


def _gh_logins_match(actual: Optional[str], expected: Optional[str]) -> bool:
    if not expected:
        return True
    actual_n = _normalize_gh_login(actual)
    expected_n = _normalize_gh_login(expected)
    return bool(actual_n) and actual_n == expected_n


def _author_login(entry: dict) -> Optional[str]:
    author = entry.get("author") if isinstance(entry, dict) else None
    if isinstance(author, dict):
        return author.get("login")
    if isinstance(author, str):
        return author
    return None


def _verify_pr_opened_for_issue(
    issue_number: str,
    since: Optional[str],
    expect_author: Optional[str],
    timeout: int,
    evidence: Optional[dict],
) -> Optional[bool]:
    """#1442: ``pr:<issue>`` is not a pull request; find a PR linked to that issue."""
    cmd = [
        "gh", "pr", "list",
        "--state", "all",
        "--limit", "20",
        "--search", f"linked:issue-{issue_number}",
        "--json", "number,createdAt,author,body,title",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        if evidence is not None:
            evidence.setdefault("attempts", []).append(
                {"error": type(exc).__name__, "fallback": "linked-issue", "matched": None}
            )
        return None
    if result.returncode != 0:
        if evidence is not None:
            evidence.setdefault("attempts", []).append(
                {"raw": result.stderr or result.stdout, "fallback": "linked-issue", "matched": None}
            )
        return None
    try:
        rows = json.loads(result.stdout or "[]")
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(rows, list):
        return None
    since_dt = _parse_iso8601(since, naive_as="local") if since else None
    matched = False
    for row in rows:
        created = _parse_iso8601(row.get("createdAt"), naive_as="utc") if isinstance(row, dict) else None
        if since_dt is not None and (created is None or _compare_dt_lt(created, since_dt)):
            continue
        if expect_author and not _gh_logins_match(_author_login(row or {}), expect_author):
            continue
        matched = True
        break
    if evidence is not None:
        evidence.setdefault("attempts", []).append(
            {"fallback": "linked-issue", "matched": matched, "raw": result.stdout}
        )
        evidence["matched"] = matched
    return matched


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
            if expect == "pr_open" and kind == "pr":
                linked = _verify_pr_opened_for_issue(
                    number, since, expect_author, timeout, evidence,
                )
                if linked is True:
                    return True
                if linked is False:
                    return False
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
            since_dt = _parse_iso8601(since, naive_as="local")
            matched = False if since_dt is not None else None
            if since_dt is not None:
                for entry in entries:
                    entry_time = entry.get("submittedAt") or entry.get("createdAt")
                    entry_dt = _parse_iso8601(entry_time)
                    if entry_dt is None or _compare_dt_lt(entry_dt, since_dt):
                        continue
                    if expect_author and not _gh_logins_match(_author_login(entry), expect_author):
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
