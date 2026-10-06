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
    "pr_open": ("state", "OPEN"),
}
_LIST_EXPECT_FIELD = {
    "review_posted": "reviews",
    "comment_posted": "comments",
}
_LIST_VERIFY_ATTEMPTS = 3
_LIST_VERIFY_BACKOFF_SECONDS = (0.1, 0.25)
_READ_QUORUM = 1


def local_commits_pushed(worktree_path: Optional[str], branch: Optional[str], base_sha: Optional[str] = None) -> bool:
    """Return whether local commits beyond *base_sha* are reachable on origin."""
    if not worktree_path or not branch:
        return False
    try:
        if base_sha:
            ahead = subprocess.run(
                ["git", "-C", worktree_path, "rev-list", "--count", f"{base_sha}..HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            if ahead.returncode != 0 or int((ahead.stdout or "0").strip() or "0") == 0:
                return True
        head = subprocess.run(
            ["git", "-C", worktree_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        remote = subprocess.run(
            ["git", "-C", worktree_path, "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            capture_output=True, text=True, timeout=10,
        )
        if head.returncode != 0 or remote.returncode != 0 or not (remote.stdout or "").strip():
            return False
        fetch = subprocess.run(
            ["git", "-C", worktree_path, "fetch", "--quiet", "origin", f"refs/heads/{branch}"],
            capture_output=True, text=True, timeout=20,
        )
        if fetch.returncode == 0:
            ancestor = subprocess.run(
                ["git", "-C", worktree_path, "merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            return ancestor.returncode == 0
        return (head.stdout or "").strip() == remote.stdout.split()[0]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def github_branch_effect_verified(
    branch: Optional[str],
    *,
    since: Optional[str] = None,
    timeout: int = 10,
    accepted_states: Optional[set[str]] = None,
    evidence: Optional[dict] = None,
) -> Optional[bool]:
    """Check GitHub ground truth when the source branch is no longer local.

    A merged PR normally deletes its head branch.  In that case
    ``local_commits_pushed`` must return false even though the work landed.
    Only accept a PR whose head ref matches the job branch and whose creation
    time is after the dispatch (when a start time is available).
    """
    if not branch:
        return None
    cmd = [
        "gh", "pr", "list", "--state", "all", "--head", branch,
        "--limit", "20", "--json", "state,createdAt,headRefName,mergedAt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if evidence is not None:
            evidence["github_branch_check"] = {"matched": None, "error": type(exc).__name__}
        return None
    if result.returncode != 0:
        if evidence is not None:
            evidence["github_branch_check"] = {"matched": None, "raw": result.stderr or result.stdout}
        return None
    try:
        rows = json.loads(result.stdout or "[]")
    except (TypeError, ValueError):
        return None
    if not isinstance(rows, list):
        return None
    since_dt = _parse_iso8601(since, naive_as="local") if since else None
    states = accepted_states or {"OPEN", "MERGED"}
    matched = False
    for row in rows:
        if not isinstance(row, dict) or row.get("headRefName") not in (None, branch):
            continue
        created = _parse_iso8601(row.get("createdAt"), naive_as="utc")
        if since_dt is not None and (created is None or _compare_dt_lt(created, since_dt)):
            continue
        if str(row.get("state") or "").upper() in states:
            matched = True
            break
    if evidence is not None:
        evidence["github_branch_check"] = {"matched": matched, "raw": result.stdout}
    return matched


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
    expect_review_state: Optional[str] = None,
    expected_sha: Optional[str] = None,
    expected_target: Optional[str] = None,
    evidence: Optional[dict] = None,
) -> Optional[bool]:
    """Return whether a declared GitHub target reached the expected state, or None if unknown.

    ``expect='closed'``/``'merged'``/``'pr_open'`` checks a scalar state field
    (original #701 behavior). ``expect='created'`` checks that the target
    exists, regardless of its current state. ``expect='review_posted'``/``'comment_posted'`` checks
    whether a reviews/comments list entry exists at or after ``since``,
    optionally matching ``expect_author``'s login and
    ``expect_review_state`` (for example, ``APPROVED``).

    ``since`` is required for the two list-based expect values. Without a time
    floor, a write from days earlier would false-positive every later job on
    the same PR.
    """
    if not target:
        return None
    if expected_target is not None and expected_target != target:
        if evidence is not None:
            evidence.update({"target": target, "expected_target": expected_target,
                             "matched": False, "reason": "target_mismatch"})
        return False
    match = _TARGET_RE.match(target)
    if not match:
        return None
    kind, number = match.groups()
    subcommand = "issue" if kind == "issue" else "pr"

    if expect == "created":
        field = "state"
        cmd = ["gh", subcommand, "view", number, "--json", field]
    elif expect == "merged":
        field = "state"
        expected_value = "MERGED"
        cmd = ["gh", subcommand, "view", number, "--json", "state,mergedBy,mergeCommit"]
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
    is_scalar_expect = expect in _EXPECT_FIELD or expect == "merged"
    attempts = _LIST_VERIFY_ATTEMPTS if (is_list_expect or is_scalar_expect) else 1
    if evidence is not None:
        evidence.update({
            "target": target,
            "expected_target": expected_target or target,
            "expect": expect,
            "field": field,
            "expected_actor": expect_author,
            "expected_sha": expected_sha,
            "attempts": [],
            "retry": {"max_attempts": attempts, "backoff_seconds": list(_LIST_VERIFY_BACKOFF_SECONDS),
                      "read_after_write": attempts > 1},
            "quorum": {"required": _READ_QUORUM, "observed": 0},
        })

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

        if expect in _EXPECT_FIELD or expect == "merged":
            actual = payload.get(field)
            state_match = None if actual is None else actual == expected_value
            actor_match = True
            sha_match = True
            if expect == "merged":
                actor_match = _gh_logins_match(
                    _author_login({"author": payload.get("mergedBy")}), expect_author
                )
                sha_match = (
                    True
                    if not expected_sha
                    else _entry_matches_sha(payload.get("mergeCommit") or {}, expected_sha)
                )
                matched = (
                    None
                    if state_match is None or actor_match is None
                    else bool(state_match and actor_match and sha_match)
                )
                if evidence is not None:
                    evidence.update({
                        "target_match": True,
                        "actor_match": actor_match,
                        "sha_match": sha_match,
                        "state": actual,
                        "mergedBy": payload.get("mergedBy"),
                        "mergeCommit": payload.get("mergeCommit"),
                        "merge_state": actual,
                        "merged_by": payload.get("mergedBy"),
                        "merge_commit": payload.get("mergeCommit"),
                    })
                    evidence["attempts"][-1].update({
                        "target_match": True,
                        "actor_match": actor_match,
                        "sha_match": sha_match,
                        "merge_state": actual,
                    })
            else:
                matched = state_match
            if evidence is not None:
                evidence["attempts"][-1]["matched"] = matched
            if matched is True:
                if evidence is not None:
                    evidence["matched"] = True
                    evidence["attempt_count"] = attempt + 1
                    evidence["quorum"]["observed"] = 1
                return True
            if attempt + 1 < attempts:
                time.sleep(_LIST_VERIFY_BACKOFF_SECONDS[min(attempt, len(_LIST_VERIFY_BACKOFF_SECONDS) - 1)])
                continue
            if evidence is not None:
                evidence["matched"] = matched
                evidence["attempt_count"] = attempt + 1
            return matched

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
                    if expect_review_state and entry.get("state") != expect_review_state:
                        continue
                    if expected_sha and not _entry_matches_sha(entry, expected_sha):
                        continue
                    matched = True
                    break
        if evidence is not None:
            evidence["attempts"][-1]["matched"] = matched
        if matched is True:
            if evidence is not None:
                evidence["matched"] = True
                evidence["attempt_count"] = attempt + 1
                evidence["quorum"]["observed"] = 1
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


def cross_branch_pr_effect_verified(
    target: Optional[str],
    *,
    since: Optional[str] = None,
    worktree_branch: Optional[str] = None,
    expect_author: Optional[str] = None,
    accept_reviews: bool = True,
    accept_commits: bool = True,
    timeout: int = 10,
    evidence: Optional[dict] = None,
) -> Optional[bool]:
    """Primary evidence when a job's effect is a PR other than its own branch.

    Queries ``gh pr view <N> --json reviews,commits,headRefName`` and accepts a
    review or commit at or after ``since``. ``headRefName`` is included so a PR
    whose head is this job's own branch stays on the local-diff path.

    Returns True when a fresh event is present, False when the PR is a different
    branch and no fresh event is present, and None when the target is not a
    cross-branch PR (missing target, same branch, or GitHub could not be read).
    """
    if not target or not since or not (accept_reviews or accept_commits):
        return None
    match = _TARGET_RE.match(target)
    if not match or match.group(1) != "pr":
        return None
    number = match.group(2)
    cmd = ["gh", "pr", "view", number, "--json", "reviews,commits,headRefName"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if evidence is not None:
            evidence.update({
                "target": target,
                "github_unknown": True,
                "error": type(exc).__name__,
            })
        return None
    if evidence is not None:
        evidence.update({"target": target, "raw": result.stdout, "command": cmd})
    if result.returncode != 0:
        if evidence is not None:
            evidence["github_unknown"] = True
            evidence["raw"] = result.stderr or result.stdout
        return None
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError):
        if evidence is not None:
            evidence["github_unknown"] = True
        return None
    if not isinstance(payload, dict):
        if evidence is not None:
            evidence["github_unknown"] = True
        return None
    head = payload.get("headRefName")
    if worktree_branch and head and head == worktree_branch:
        if evidence is not None:
            evidence.update({"same_branch": True, "cross_branch": False, "head_ref": head})
        return None
    since_dt = _parse_iso8601(since, naive_as="local")
    if since_dt is None:
        if evidence is not None:
            evidence["github_unknown"] = True
        return None
    if evidence is not None:
        evidence.update({"cross_branch": True, "head_ref": head, "target_match": True})

    def _is_fresh(entry: dict, *fields: str) -> bool:
        entry_dt = _parse_iso8601(next((entry.get(field) for field in fields if entry.get(field)), None))
        return entry_dt is not None and not _compare_dt_lt(entry_dt, since_dt)

    matched = False
    actor_match = expect_author is None
    if accept_reviews:
        for entry in payload.get("reviews") or []:
            if not isinstance(entry, dict) or not _is_fresh(entry, "submittedAt", "createdAt"):
                continue
            if expect_author and not _gh_logins_match(_author_login(entry), expect_author):
                continue
            matched = True
            actor_match = True
            if evidence is not None:
                evidence["matched_event"] = "review"
            break
    if not matched and accept_commits:
        for entry in payload.get("commits") or []:
            if not isinstance(entry, dict) or not _is_fresh(entry, "committedDate", "authoredDate"):
                continue
            matched = True
            if evidence is not None:
                evidence["matched_event"] = "commit"
            break
    if evidence is not None:
        evidence["matched"] = matched
        evidence["actor_match"] = actor_match
    return matched


def _entry_matches_sha(entry: dict, expected_sha: str) -> bool:
    """Return whether a review/comment carries the causal commit identity."""
    candidates = [
        entry.get("oid"), entry.get("commitOid"), entry.get("commit_oid"),
        entry.get("sha"), entry.get("headSha"),
    ]
    commit = entry.get("commit")
    if isinstance(commit, dict):
        candidates.extend((commit.get("oid"), commit.get("sha")))
    return any(value and str(value).startswith(str(expected_sha)) for value in candidates)
