import json

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay import RelayBroker, iter_sse_events


def test_relay_broker_persists_and_fans_out(project_dir):
    broker = RelayBroker()
    subscriber = broker.subscribe()
    actor = ActorIdentifier("workspace", "member", "dev", "codex", "job")
    envelope = EventEnvelope.create(actor, "agent_started", {"task": "relay"})

    assert broker.publish(envelope) == 1
    assert json.loads(subscriber.get_nowait()) == envelope.to_dict()

    from synlynk import _get_db
    conn = _get_db()
    assert conn.execute("SELECT event_type FROM relay_events WHERE event_id=?", (envelope.event_id,)).fetchone()[0] == "agent_started"
    conn.close()


def test_iter_sse_events_decodes_data_lines():
    lines = [b": keepalive\n", b"data: {\"event_id\": \"evt-1\"}\n"]
    assert list(iter_sse_events(lines)) == [{"event_id": "evt-1"}]
