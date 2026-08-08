import json
import sqlite3
import pytest
from synlynk.events import emit_event, pending_events, advance_checkpoint


def test_emit_event_writes_row_and_returns_id(project_dir):
    event_id = emit_event(
        "story_done",
        {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]},
        emitted_by="cmd_story_done",
    )
    assert isinstance(event_id, int) and event_id > 0

    import synlynk
    conn = synlynk._get_db()
    row = conn.execute(
        "SELECT event_type, payload_json, emitted_by, parent_event_id FROM events WHERE id=?",
        (event_id,),
    ).fetchone()
    conn.close()
    assert row[0] == "story_done"
    assert json.loads(row[1]) == {"story_id": "story-abc123", "goal_ids": ["goal-xyz789"]}
    assert row[2] == "cmd_story_done"
    assert row[3] is None


def test_pending_events_returns_only_events_after_checkpoint(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [e2]
    assert pending[0]["payload"] == {"story_id": "s2"}


def test_pending_events_ignores_other_event_types(project_dir):
    emit_event("pr_merged", {"pr": 1}, emitted_by="test")
    story_event_id = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert [p["id"] for p in pending] == [story_event_id]


def test_advance_checkpoint_never_moves_backward(project_dir):
    e1 = emit_event("story_done", {"story_id": "s1"}, emitted_by="test")
    e2 = emit_event("story_done", {"story_id": "s2"}, emitted_by="test")
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e2)
    advance_checkpoint("workspace-lifecycle-nudge", "story_done", e1)

    pending = pending_events("workspace-lifecycle-nudge", "story_done")

    assert pending == []


def test_migration_adds_link_status_and_skip_reason_columns(project_dir):
    import synlynk
    conn = synlynk._get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(goal_contributions)")}
    conn.close()
    assert "link_status" in cols
    assert "skip_reason" in cols
