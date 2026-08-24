"""Local event bus: append-only events table + per-agent subscription checkpoints.

Local-only for this build — authority_scope is reserved for future team/enterprise
delivery and is always written as NULL here (see plan Task 1 header note).
"""

from __future__ import annotations

import json
import re
import time


_ROLE_LOGIN_RE = re.compile(r"^synlynk-[a-z0-9]+-([a-z]+)\[bot\]$")


def _reviewer_role_from_login(login):
    """Derives the role slug from a synlynk-<repo-slug>-<role>[bot] GitHub App login."""
    if not login:
        return None
    match = _ROLE_LOGIN_RE.match(login)
    return match.group(1) if match else None


def _existing_review_submitted_keys(pr_number):
    """Returns the set of (reviewer_login, submitted_at) already emitted for pr_number."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE event_type='review_submitted'"
    ).fetchall()
    conn.close()
    keys = set()
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            continue
        if payload.get("pr_number") == pr_number:
            keys.add((payload.get("reviewer_login"), payload.get("submitted_at")))
    return keys


def _scan_pr_reviews(pr_number):
    """Fetches reviews for pr_number via gh, emits review_submitted for any not yet recorded.

    Returns the id of the last event emitted, or None if none were emitted.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "reviews"],
            capture_output=True,
            text=True,
            check=False,
        )
        parsed = json.loads(result.stdout) if result.returncode == 0 else {}
        reviews = parsed.get("reviews", []) if isinstance(parsed, dict) else []
    except (FileNotFoundError, json.JSONDecodeError):
        reviews = []

    existing_keys = _existing_review_submitted_keys(pr_number)
    last_event_id = None
    for review in reviews:
        login = (review.get("author") or {}).get("login")
        submitted_at = review.get("submittedAt")
        key = (login, submitted_at)
        if key in existing_keys:
            continue
        last_event_id = emit_event(
            "review_submitted",
            {
                "pr_number": pr_number,
                "reviewer_login": login,
                "reviewer_role": _reviewer_role_from_login(login),
                "verdict": review.get("state"),
                "submitted_at": submitted_at,
            },
            emitted_by="scan_local_events",
        )
        existing_keys.add(key)
    return last_event_id


def _existing_spec_verified_pr_numbers():
    """Returns the set of PR numbers that already have a spec_verified event."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE event_type='spec_verified'"
    ).fetchall()
    conn.close()
    numbers = set()
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            continue
        pr_number = payload.get("pr_number")
        if pr_number is not None:
            numbers.add(pr_number)
    return numbers


def _scan_pr_completion(pr_number, pr_body):
    """Computes and emits a spec_verified event for pr_number, if its body
    references a spec/plan/issue and a verdict can be computed. Returns the
    new event's id, or None if skipped (no reference found in the PR body, or
    the verdict couldn't be computed -- see compute_completion_verdict's
    docstring for why None isn't retried as a verdict).
    """
    from synlynk.completion_tracker import parse_spec_reference, compute_completion_verdict

    spec_reference = parse_spec_reference(pr_body)
    if spec_reference is None:
        return None

    verdict = compute_completion_verdict(pr_number, spec_reference)
    if verdict is None:
        return None

    return emit_event(
        "spec_verified",
        {
            "pr_number": pr_number,
            "spec_path": spec_reference,
            "verdict": verdict["verdict"],
            "rationale": verdict["rationale"],
            "reviewer_role": "qa",
        },
        emitted_by="scan_local_events",
    )


def _existing_approval_resolved_keys() -> set:
    """Returns the set of issue URLs that already have an approval_resolved event."""
    from synlynk import _get_db
    conn = _get_db()
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE event_type='approval_resolved'"
    ).fetchall()
    conn.close()
    keys = set()
    for (payload_json,) in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            continue
        issue_url = payload.get("issue_url")
        if issue_url is not None:
            keys.add(issue_url)
    return keys


def _scan_approval_tickets() -> int | None:
    """Poll approval issues and emit approval_resolved for newly resolved tickets.

    An issue is resolved when it is closed or has a comment beginning with
    ``approve``. Returns the id of the last event emitted, or None if none were
    emitted.
    """
    import subprocess

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                "[APPROVAL] in:title",
                "--state",
                "all",
                "--json",
                "url,state,comments",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        issues = json.loads(result.stdout) if result.returncode == 0 else []
    except (FileNotFoundError, json.JSONDecodeError, StopIteration):
        issues = []

    already = _existing_approval_resolved_keys()
    last_event_id = None
    for issue in issues:
        if issue["url"] in already:
            continue
        resolved = issue["state"] == "CLOSED" or any(
            comment.get("body", "").strip().lower().startswith("approve")
            for comment in issue.get("comments", [])
        )
        if resolved:
            from synlynk import _get_db
            conn = _get_db()
            conn.execute(
                "UPDATE approval_tickets SET status='resolved', resolved_at=CURRENT_TIMESTAMP "
                "WHERE issue_url=? AND status='open'",
                (issue["url"],),
            )
            conn.commit()
            conn.close()
            last_event_id = emit_event(
                "approval_resolved",
                {"issue_url": issue["url"]},
                emitted_by="_scan_approval_tickets",
            )
            already.add(issue["url"])
    return last_event_id


def emit_event(event_type: str, payload: dict, emitted_by: str,
               parent_event_id: int = None) -> int:
    """Writes an event row. Returns the new event's id."""
    from synlynk import _get_db
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO events (event_type, payload_json, created_at, emitted_by, parent_event_id, authority_scope) "
        "VALUES (?, ?, ?, ?, ?, NULL)",
        (event_type, json.dumps(payload), time.strftime("%Y-%m-%dT%H:%M:%S"), emitted_by, parent_event_id),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def emit_awaiting_approval(story_id: str, action: str, reason: str,
                           emitted_by: str = "tpm_sweep") -> int:
    """Emits an awaiting_approval GOVERNS event: an autonomous action was gated by
    policy.json's requires_approval and is parked pending a human decision.
    """
    return emit_event(
        "awaiting_approval",
        {"story_id": story_id, "action": action, "reason": reason},
        emitted_by=emitted_by,
    )


def pending_events(harness_name: str, event_type: str) -> list:
    """Returns events of event_type with id greater than harness_name's checkpoint, oldest first."""
    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT last_seen_event_id FROM subscriptions WHERE harness_name=? AND event_type=?",
        (harness_name, event_type),
    ).fetchone()
    checkpoint = row[0] if row else 0
    rows = conn.execute(
        "SELECT id, event_type, payload_json, created_at, emitted_by, parent_event_id "
        "FROM events WHERE event_type=? AND id>? ORDER BY id ASC",
        (event_type, checkpoint),
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "event_type": r[1], "payload": json.loads(r[2]),
         "created_at": r[3], "emitted_by": r[4], "parent_event_id": r[5]}
        for r in rows
    ]


def advance_checkpoint(harness_name: str, event_type: str, event_id: int) -> None:
    """Advances harness_name's checkpoint for event_type to event_id. Never moves backward."""
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO subscriptions (harness_name, event_type, last_seen_event_id) VALUES (?, ?, ?) "
        "ON CONFLICT(harness_name, event_type) DO UPDATE SET "
        "last_seen_event_id=excluded.last_seen_event_id "
        "WHERE excluded.last_seen_event_id > subscriptions.last_seen_event_id",
        (harness_name, event_type, event_id),
    )
    conn.commit()
    conn.close()


def scan_local_events(harness_name: str) -> None:
    """Detect and emit local lifecycle events for this run.

    The pilot intentionally scans the latest merged PRs and recent relevant git
    paths on every run. Consumers use their own checkpoints to deduplicate the
    resulting events.
    """
    import subprocess

    heartbeat_id = emit_event("cron_heartbeat", {}, emitted_by="scan_local_events")
    advance_checkpoint(harness_name, "cron_heartbeat", heartbeat_id)

    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--limit", "20", "--json", "number,title,mergedAt,body"],
            capture_output=True,
            text=True,
            check=False,
        )
        merged_prs = json.loads(result.stdout) if result.returncode == 0 else []
    except (FileNotFoundError, json.JSONDecodeError):
        merged_prs = []

    already_verified = _existing_spec_verified_pr_numbers()

    last_event_id = None
    last_review_event_id = None
    last_completion_event_id = None
    for pr in merged_prs:
        last_event_id = emit_event(
            "pr_merged",
            {
                "pr_number": pr["number"],
                "title": pr.get("title"),
                "merged_at": pr.get("mergedAt"),
            },
            emitted_by="scan_local_events",
        )
        review_event_id = _scan_pr_reviews(pr["number"])
        if review_event_id is not None:
            last_review_event_id = review_event_id
        if pr["number"] not in already_verified:
            completion_event_id = _scan_pr_completion(pr["number"], pr.get("body"))
            if completion_event_id is not None:
                last_completion_event_id = completion_event_id
    if last_event_id is not None:
        advance_checkpoint(harness_name, "pr_merged", last_event_id)
    if last_review_event_id is not None:
        advance_checkpoint(harness_name, "review_submitted", last_review_event_id)
    if last_completion_event_id is not None:
        advance_checkpoint(harness_name, "spec_verified", last_completion_event_id)
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--name-only",
                "--pretty=format:",
                "-20",
                "--",
                "docs/superpowers/specs",
                "docs/superpowers/plans",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        changed_paths = sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})
    except FileNotFoundError:
        changed_paths = []

    last_event_id = None
    for path in changed_paths:
        last_event_id = emit_event(
            "spec_or_plan_committed",
            {"path": path},
            emitted_by="scan_local_events",
        )
    if last_event_id is not None:
        advance_checkpoint(harness_name, "spec_or_plan_committed", last_event_id)

    last_approval_event_id = _scan_approval_tickets()
    if last_approval_event_id is not None:
        advance_checkpoint(harness_name, "approval_resolved", last_approval_event_id)


def cmd_events_tail(event_type: str = None, limit: int = 20) -> None:
    """Prints the most recent GOVERNS events, newest first. Read-only diagnostic."""
    from synlynk import _get_db

    conn = _get_db()
    if event_type:
        rows = conn.execute(
            "SELECT id, created_at, event_type, emitted_by, payload_json "
            "FROM events WHERE event_type=? ORDER BY id DESC LIMIT ?",
            (event_type, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, created_at, event_type, emitted_by, payload_json "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    for event_id, created_at, etype, emitted_by, payload_json in rows:
        try:
            payload = json.loads(payload_json)
            summary = json.dumps(payload, separators=(", ", ": "))
        except (TypeError, ValueError):
            summary = payload_json or ""
        print(f"{event_id}  {created_at}  {etype}  {emitted_by}  {summary}")
