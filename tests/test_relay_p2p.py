import json
import pytest
from unittest.mock import MagicMock, patch

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay import (
    RelayBroker,
    encode_websocket_frame,
    decode_websocket_frame,
    format_nats_pub,
    parse_nats_frame,
)


def test_websocket_framing_roundtrip():
    payload = "Hello P2P Mesh Agent Relay! 🚀"
    encoded = encode_websocket_frame(payload)
    assert len(encoded) > len(payload)
    decoded, length = decode_websocket_frame(encoded)
    assert decoded == payload
    assert length == len(encoded)


def test_websocket_masked_frame_decoding():
    # Masked frame simulation
    payload = "Masked payload test"
    data = payload.encode("utf-8")
    mask_key = b"\x12\x34\x56\x78"
    masked_bytes = bytearray(len(data))
    for i in range(len(data)):
        masked_bytes[i] = data[i] ^ mask_key[i % 4]
    
    frame = bytearray([0x81, 0x80 | len(data)]) + mask_key + masked_bytes
    decoded, length = decode_websocket_frame(bytes(frame))
    assert decoded == payload
    assert length == len(frame)


def test_nats_pub_framing_roundtrip():
    subject = "synlynk.events.task_progress"
    payload = json.dumps({"task_id": "task-001", "status": "running"})
    nats_frame = format_nats_pub(subject, payload)
    assert nats_frame.startswith(b"PUB synlynk.events.task_progress")
    assert nats_frame.endswith(b"\r\n")

    parsed_subject, parsed_payload = parse_nats_frame(nats_frame)
    assert parsed_subject == subject
    assert parsed_payload == payload


def test_relay_broker_peer_management():
    broker = RelayBroker()
    assert broker.list_peers() == []

    # Add peers
    assert broker.add_peer("http://127.0.0.1:7433") is True
    assert broker.add_peer("http://127.0.0.1:7433/") is False  # deduplicated
    assert broker.add_peer("http://192.168.1.100:7432") is True
    assert broker.list_peers() == ["http://127.0.0.1:7433", "http://192.168.1.100:7432"]

    # Remove peer
    assert broker.remove_peer("http://127.0.0.1:7433") is True
    assert broker.remove_peer("http://127.0.0.1:7433") is False
    assert broker.list_peers() == ["http://192.168.1.100:7432"]


def test_relay_broker_peer_rpc():
    broker = RelayBroker()
    res_add = broker.rpc("relay.peer_add", {"url": "http://127.0.0.1:8888"})
    assert res_add["added"] is True
    assert "http://127.0.0.1:8888" in res_add["peers"]

    res_list = broker.rpc("relay.peer_list", {})
    assert res_list["count"] == 1

    res_rem = broker.rpc("relay.peer_remove", {"url": "http://127.0.0.1:8888"})
    assert res_rem["removed"] is True
    assert res_rem["peers"] == []


def test_relay_broker_forward_to_peers_loop_prevention(tmp_path):
    broker = RelayBroker()
    broker.add_peer("http://mock-peer:7432")

    actor = ActorIdentifier("ws-1", "user-1", "dev", "codex", "job-1")
    envelope = EventEnvelope.create(actor, "task_progress", {"progress": 50})

    with patch("synlynk.relay.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        # First forward: successful
        forwarded = broker.forward_to_peers(envelope)
        assert forwarded == 1
        assert mock_urlopen.call_count == 1

        # Second forward with same event_id: suppressed by seen_events loop prevention
        forwarded_again = broker.forward_to_peers(envelope)
        assert forwarded_again == 0
        assert mock_urlopen.call_count == 1
