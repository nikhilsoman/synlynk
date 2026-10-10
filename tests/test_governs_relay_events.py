import json
import sqlite3

from synlynk.db import _migrate_db
from synlynk.events import ActorIdentifier, EventEnvelope, RELAY_EVENT_TYPES
from synlynk.governs_engine import associate_story


def _db(tmp_path, product_id="prod-a"):
    conn = sqlite3.connect(str(tmp_path / f"{product_id}.db"))
    _migrate_db(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state_identity (product_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'repo', canonical_path TEXT NOT NULL DEFAULT '')"
    )
    conn.execute("INSERT INTO state_identity(product_id) VALUES (?)", (product_id,))
    conn.execute(
        "INSERT INTO goals (goal_id, outcome, criterion, product_id, status) VALUES (?, ?, ?, ?, 'active')",
        ("goal-a", "Payments reliability", "payments reliability", product_id),
    )
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('story-1', 'Payments reliability')")
    conn.commit()
    return conn


def test_governance_event_types_registered():
    assert "goal_realigned" in RELAY_EVENT_TYPES
    assert "governs_stage_advanced" in RELAY_EVENT_TYPES


def test_goal_realigned_envelope_construction():
    actor = ActorIdentifier("workspace-a", "member-a", "governs", "codex", "job-a")
    env = EventEnvelope.create(
        actor,
        "goal_realigned",
        {"story_id": "story-1", "product_id": "prod-a", "to_goal": "goal-a"},
    )
    assert env.event_type == "goal_realigned"
    assert env.payload["to_goal"] == "goal-a"


def test_association_emits_on_change_only(tmp_path, monkeypatch):
    emitted = []
    monkeypatch.setattr("synlynk.events.emit_event", lambda *args, **kwargs: emitted.append((args, kwargs)))
    conn = _db(tmp_path)

    associate_story(conn, "story-1", title="Payments reliability")
    associate_story(conn, "story-1", title="Payments reliability")

    assert len(emitted) == 1
    event_type, payload = emitted[0][0][:2]
    assert event_type == "goal_realigned"
    assert payload["product_id"] == "prod-a"
    assert payload["to_goal"] == "goal-a"
    assert emitted[0][1]["emitted_by"] == "governs_engine.associate_story"


def test_emit_false_suppresses(tmp_path, monkeypatch):
    emitted = []
    monkeypatch.setattr("synlynk.events.emit_event", lambda *args, **kwargs: emitted.append(args))
    conn = _db(tmp_path)

    associate_story(conn, "story-1", title="Payments reliability", emit=False)

    assert emitted == []


def test_foreign_product_event_is_identifiable_for_consumer_filter():
    actor = ActorIdentifier("workspace-a", "member-a", "governs", "codex", "job-a")
    env = EventEnvelope.create(actor, "goal_realigned", {"product_id": "prod-a"})
    decoded = json.loads(env.to_json())
    assert decoded["payload"]["product_id"] != "prod-b"


def test_gantt_contains_consume_side_product_filter():
    from synlynk.viz import generate_gantt_html

    html = generate_gantt_html({"product_id": "prod-b", "goals": [], "releases": []}, 8721)
    assert "currentWorkspaceProductId" in html
    assert "eventProductId" in html
