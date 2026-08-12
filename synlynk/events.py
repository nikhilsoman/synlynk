"""Local event bus: append-only events table + per-agent subscription checkpoints.

Local-only for this build — authority_scope is reserved for future team/enterprise
delivery and is always written as NULL here (see plan Task 1 header note).
"""

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


def pending_events(agent_name: str, event_type: str) -> list:
    """Returns events of event_type with id greater than agent_name's checkpoint, oldest first."""
    from synlynk import _get_db
    conn = _get_db()
    row = conn.execute(
        "SELECT last_seen_event_id FROM subscriptions WHERE agent_name=? AND event_type=?",
        (agent_name, event_type),
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


def advance_checkpoint(agent_name: str, event_type: str, event_id: int) -> None:
    """Advances agent_name's checkpoint for event_type to event_id. Never moves backward."""
    from synlynk import _get_db
    conn = _get_db()
    conn.execute(
        "INSERT INTO subscriptions (agent_name, event_type, last_seen_event_id) VALUES (?, ?, ?) "
        "ON CONFLICT(agent_name, event_type) DO UPDATE SET "
        "last_seen_event_id=excluded.last_seen_event_id "
        "WHERE excluded.last_seen_event_id > subscriptions.last_seen_event_id",
        (agent_name, event_type, event_id),
    )
    conn.commit()
    conn.close()


def scan_local_events(agent_name: str) -> None:
    """Detect and emit local lifecycle events for this run.

    The pilot intentionally scans the latest merged PRs and recent relevant git
    paths on every run. Consumers use their own checkpoints to deduplicate the
    resulting events.
    """
    import subprocess

    heartbeat_id = emit_event("cron_heartbeat", {}, emitted_by="scan_local_events")
    advance_checkpoint(agent_name, "cron_heartbeat", heartbeat_id)

    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--limit", "20", "--json", "number,title,mergedAt"],
            capture_output=True,
            text=True,
            check=False,
        )
        merged_prs = json.loads(result.stdout) if result.returncode == 0 else []
    except (FileNotFoundError, json.JSONDecodeError):
        merged_prs = []

    last_event_id = None
    last_review_event_id = None
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
    if last_event_id is not None:
        advance_checkpoint(agent_name, "pr_merged", last_event_id)
    if last_review_event_id is not None:
        advance_checkpoint(agent_name, "review_submitted", last_review_event_id)

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
        advance_checkpoint(agent_name, "spec_or_plan_committed", last_event_id)
