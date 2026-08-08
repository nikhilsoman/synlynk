"""Local event bus: append-only events table + per-agent subscription checkpoints.

Local-only for this build — authority_scope is reserved for future team/enterprise
delivery and is always written as NULL here (see plan Task 1 header note).
"""

import json
import time


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
