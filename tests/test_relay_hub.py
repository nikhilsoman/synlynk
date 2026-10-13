import json
import os
from pathlib import Path
import subprocess
import sys
import queue
import threading
from types import SimpleNamespace

import pytest

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay_hub import DeviceCredentialStore, RETENTION_POLICIES, category_for_subject, subject_for_event
from synlynk.relay import RelayBroker
from synlynk.relay_hub import HubAdapter, NatsTransport


class FakeNatsClient:
    def __init__(self):
        self.published = queue.Queue()
        self.subscriptions = {}
        self.fail_publish = False

    def publish(self, subject, payload):
        if self.fail_publish:
            raise OSError("publish failed")
        self.published.put((subject, payload))
        self.deliver(subject, payload)  # Simulate NATS own echo, synchronously.

    def subscribe(self, subject, callback):
        self.subscriptions[subject] = callback
        return subject

    def unsubscribe(self, subscription):
        self.subscriptions.pop(subscription)

    def deliver(self, subject, payload):
        for pattern, callback in list(self.subscriptions.items()):
            if subject.startswith(pattern[:-1]):
                callback(subject, payload)


@pytest.fixture
def bridge(project_dir):
    broker, client = RelayBroker(), FakeNatsClient()
    adapter = HubAdapter(broker, client, workspace_id="ws1", max_seen=512)
    adapter.attach()
    yield broker, client, adapter
    adapter.detach()


def hub_event(**overrides):
    values = EventEnvelope.create(
        ActorIdentifier("ws1", "m", "dev", "codex", "j"),
        "review_requested", {"pr_url": "https://x"},
    ).to_dict()
    values.update(overrides)
    return EventEnvelope.from_dict(values)


def test_adapter_forwards_and_suppresses_own_echo(bridge):
    broker, client, adapter = bridge
    subscriber = broker.subscribe()
    envelope = hub_event()
    broker.publish(envelope)
    subject, data = client.published.get(timeout=2)
    assert subject == "synlynk.ws1.job.review_requested"
    assert json.loads(data) == envelope.to_dict()
    assert json.loads(subscriber.get(timeout=2))["event_id"] == envelope.event_id
    adapter.detach()  # Join the pump before checking absence of duplicates.
    assert subscriber.empty()
    assert client.published.empty()


def test_adapter_inbound_dedupes_before_broker_delivery(bridge):
    broker, client, adapter = bridge
    subscriber = broker.subscribe()
    envelope = hub_event()
    for _ in range(3):
        client.deliver("synlynk.ws1.job.review_requested", envelope.to_json().encode())
    assert json.loads(subscriber.get(timeout=2)) == envelope.to_dict()
    # Barrier: the later local event proves the pump processed inbound copies.
    broker.publish(hub_event())
    assert client.published.get(timeout=2)
    adapter.detach()
    assert subscriber.qsize() == 1
    assert client.published.empty()


@pytest.mark.parametrize("method,suffix,params", [
    ("runner_progress", "agent.codex.progress", {"payload": {"harness": "wrong"}}),
    ("inject_steering", "device.dev-42.steering", {"target_device_id": "dev-42"}),
    ("request_review", "job.review_requested", {"pr_url": "https://x"}),
])
def test_adapter_real_broker_rpc_routing(bridge, method, suffix, params):
    broker, client, _ = bridge
    result = broker.rpc(method, {"sender": hub_event().sender.to_dict(), **params})
    subject, data = client.published.get(timeout=2)
    assert subject == f"synlynk.ws1.{suffix}"
    assert json.loads(data)["event_id"] == result["event_id"]


@pytest.mark.parametrize("mutation", [
    {"payload": []}, {"sender": None}, {"event_id": []},
    {"timestamp": None}, {"event_type": "invalid"},
    {"sender": {"workspace_id": "ws2"}},
    {"recipient": {"workspace_id": "ws2"}},
])
def test_adapter_rejects_bad_inbound_and_recovers(bridge, mutation):
    broker, client, adapter = bridge
    subscriber = broker.subscribe()
    raw = hub_event().to_dict()
    raw.update(mutation)
    client.deliver("synlynk.ws1.job.review_requested", json.dumps(raw))
    client.deliver("synlynk.ws1.job.review_requested", b"\xff")
    adapter._on_hub_message("synlynk.ws2.job.review_requested", hub_event().to_json())
    assert subscriber.empty()
    good = hub_event()
    client.deliver("synlynk.ws1.job.review_requested", good.to_json())
    assert json.loads(subscriber.get(timeout=2))["event_id"] == good.event_id
    assert adapter.last_error is not None


def test_adapter_rejects_cross_workspace_outgoing(bridge):
    broker, client, _ = bridge
    other = ActorIdentifier("ws2", "m", "dev", "codex", "j")
    broker.publish(hub_event(sender=other.to_dict()))
    broker.publish(hub_event(recipient=other.to_dict()))
    valid = hub_event()
    broker.publish(valid)
    assert json.loads(client.published.get(timeout=2)[1])["event_id"] == valid.event_id
    assert client.published.empty()


def test_adapter_lifecycle_and_bounded_ids(bridge):
    broker, client, adapter = bridge
    adapter.attach()
    assert len(client.subscriptions) == 1
    for index in range(600):
        event = hub_event(event_id=f"evt-{index}")
        broker.publish(event)
        client.published.get(timeout=2)
    assert len(adapter._seen) <= 512
    adapter.detach()
    adapter.detach()
    assert not adapter._bridge_thread.is_alive()
    assert not client.subscriptions
    assert not broker._subscribers
    adapter.attach()
    broker.publish(hub_event())
    assert client.published.get(timeout=2)


def test_adapter_publish_failure_observable_and_pump_survives(bridge):
    broker, client, adapter = bridge
    failed = threading.Event()
    def fail(subject, data):
        failed.set()
        raise OSError("publish failed")
    original = client.publish
    client.publish = fail
    broker.publish(hub_event())
    assert failed.wait(2)
    client.publish = original
    broker.publish(hub_event())
    assert client.published.get(timeout=2)
    assert isinstance(adapter.last_error, OSError)


def test_adapter_concurrent_inbound_is_delivered_once(bridge):
    from concurrent.futures import ThreadPoolExecutor
    broker, client, _ = bridge
    subscriber = broker.subscribe()
    data = hub_event().to_json()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: client.deliver("synlynk.ws1.job.review_requested", data), range(30)))
    assert subscriber.qsize() == 1


def test_adapter_owned_client_shutdown_and_attach_failure(project_dir):
    broker, client = RelayBroker(), FakeNatsClient()
    closed = []
    client.close = lambda: closed.append(True)
    adapter = HubAdapter(broker, client, "ws1", owns_client=True)
    adapter.attach()
    adapter.stop()
    adapter.stop()
    assert closed == [True]
    with pytest.raises(RuntimeError, match="closed"):
        adapter.attach()
    def fail(*args):
        raise OSError("subscribe failed")
    client.subscribe = fail
    adapter = HubAdapter(broker, client, "ws1", owns_client=True)
    with pytest.raises(OSError, match="subscribe failed"):
        adapter.attach()
    assert closed == [True, True]
    assert not broker._subscribers


@pytest.mark.parametrize("failure", ["connect", "timeout", "publish", "async_error"])
def test_nats_transport_failure_cleanup(monkeypatch, failure):
    import asyncio
    import synlynk.relay_hub as hub
    closed, cancelled = threading.Event(), threading.Event()
    class AsyncClient:
        async def connect(self, **kwargs):
            self.error_cb = kwargs["error_cb"]
            if failure == "connect":
                raise OSError("connect failed")
            if failure == "timeout":
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        async def publish(self, subject, payload):
            if failure == "publish":
                raise OSError("publish failed")
            await self.error_cb(OSError("async failure"))
        async def flush(self, **kwargs):
            pass
        async def close(self):
            closed.set()
    monkeypatch.setattr(hub, "_import_nats", lambda: SimpleNamespace(NATS=AsyncClient))
    previous = set(threading.enumerate())
    if failure in {"connect", "timeout"}:
        with pytest.raises((OSError, TimeoutError)):
            NatsTransport("nats://test", timeout=0.2)
    else:
        transport = NatsTransport("nats://test")
        try:
            if failure == "publish":
                with pytest.raises(OSError, match="publish failed"):
                    transport.publish("subject", "data")
            else:
                transport.publish("subject", "data")
            assert isinstance(transport.last_error, OSError)
        finally:
            transport.close()
    assert closed.is_set()
    if failure == "timeout":
        assert cancelled.is_set()
    assert not [t for t in threading.enumerate() if t not in previous and t.name == "relay-nats"]


def test_nats_transport_awaits_real_api_and_closes(monkeypatch):
    import synlynk.relay_hub as hub
    calls = []
    class AsyncClient:
        async def connect(self, **kwargs):
            calls.append(("connect", kwargs))
        async def subscribe(self, subject, *, cb):
            self.callback = cb
            calls.append(("subscribe", subject))
            return self
        async def publish(self, subject, payload):
            assert isinstance(payload, bytes)
            calls.append(("publish", payload))
            await self.callback(SimpleNamespace(subject=subject, data=payload))
        async def flush(self, **kwargs):
            calls.append(("flush", None))
        async def unsubscribe(self):
            calls.append(("unsubscribe", None))
        async def close(self):
            calls.append(("close", None))
    client = AsyncClient()
    monkeypatch.setattr(hub, "_import_nats", lambda: SimpleNamespace(NATS=lambda: client))
    transport = NatsTransport("nats://localhost:4222", user="dev-1", password="secret")
    received = []
    try:
        sub = transport.subscribe("synlynk.ws1.>", lambda s, p: received.append((s, p)))
        transport.publish("synlynk.ws1.job.review_requested", "hello")
        transport.unsubscribe(sub)
    finally:
        transport.close()
    transport.close()
    assert received == [("synlynk.ws1.job.review_requested", b"hello")]
    assert calls[0][1]["user"] == "dev-1"
    assert calls[0][1]["password"] == "secret"
    assert [c[0] for c in calls] == ["connect", "subscribe", "flush", "publish", "flush", "unsubscribe", "flush", "close"]
    assert not transport._thread.is_alive()
    assert transport._loop.is_closed()


def test_device_credentials_persist_with_private_files(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    other = store.add_device("desktop")
    assert cred.device_id != other.device_id
    assert len(cred.token) >= 32 and cred.token != other.token
    assert cred.publish_subjects == cred.subscribe_subjects == ["synlynk.ws1.>"]
    assert cred.revoked is False
    reopened = DeviceCredentialStore("ws1", tmp_path)
    assert reopened.get_device(cred.device_id) == cred
    assert reopened.list_devices() == [cred, other]
    assert reopened.get_device("missing") is None
    path = tmp_path / f"{cred.device_id}.creds"
    assert json.loads(path.read_text())["token"] == cred.token
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    for path in (path, tmp_path / "devices.json", store.write_authorization_config()):
        assert path.stat().st_mode & 0o777 == 0o600


def test_revocation_is_persistent_idempotent_and_excluded(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    active = store.add_device("laptop")
    revoked = store.add_device("old-vps")
    assert store.revoke_device(revoked.device_id) is True
    assert store.revoke_device(revoked.device_id) is False
    assert store.revoke_device("missing") is False
    store = DeviceCredentialStore("ws1", tmp_path)
    assert store.get_device(revoked.device_id).revoked is True
    block = store.render_authorization_block()
    assert active.token in block and active.device_id in block
    assert revoked.token not in block and revoked.device_id not in block
    assert json.loads((tmp_path / f"{revoked.device_id}.creds").read_text())["revoked"]


def test_registry_workspace_binding_even_when_empty(tmp_path):
    DeviceCredentialStore("ws1", tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        DeviceCredentialStore("ws2", tmp_path)


def test_empty_registry_still_requires_authentication(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    auth = json.loads(store.render_authorization_block().removeprefix("authorization "))
    # NATS treats an empty users list as authentication disabled.
    assert len(auth["users"]) == 1
    assert auth["users"][0]["permissions"] == {"publish": [], "subscribe": []}
    assert len(auth["users"][0]["password"]) >= 32


def test_registry_rejects_device_path_traversal(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    path = tmp_path / "devices.json"
    registry = json.loads(path.read_text())
    raw = registry["devices"].pop(cred.device_id)
    raw["device_id"] = "../outside"
    registry["devices"]["../outside"] = raw
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="identity"):
        store.revoke_device("../outside")


@pytest.mark.parametrize("workspace", ["", "ws.*", ">", "two words", "ws\n"])
def test_credential_store_rejects_unsafe_workspace(tmp_path, workspace):
    with pytest.raises(ValueError, match="workspace"):
        DeviceCredentialStore(workspace, tmp_path)


def test_registry_rejects_cross_workspace_permissions(tmp_path):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    path = tmp_path / "devices.json"
    registry = json.loads(path.read_text())
    registry["devices"][cred.device_id]["publish_subjects"] = ["synlynk.ws2.>"]
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError, match="scope"):
        store.render_authorization_block()


def test_atomic_registry_failure_keeps_previous_data(tmp_path, monkeypatch):
    store = DeviceCredentialStore("ws1", tmp_path)
    cred = store.add_device("laptop")
    original = (tmp_path / "devices.json").read_bytes()
    real_replace = os.replace

    def fail_registry(source, destination):
        assert Path(source).stat().st_mode & 0o777 == 0o600
        if Path(destination).name == "devices.json":
            raise OSError("simulated write failure")
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_registry)
    with pytest.raises(OSError, match="simulated"):
        store.add_device("desktop")
    assert (tmp_path / "devices.json").read_bytes() == original
    assert store.list_devices() == [cred]
    assert not list(tmp_path.glob("*.tmp"))


def test_secret_symlink_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("do not touch")
    directory = tmp_path / "hub"
    directory.mkdir()
    (directory / "devices.json").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        DeviceCredentialStore("ws1", directory)
    assert outside.read_text() == "do not touch"


@pytest.mark.parametrize("workspace", ["ws1", 'ws"quoted\\name'])
@pytest.mark.parametrize("active", [True, False])
def test_authorization_parses_with_real_nats(tmp_path, workspace, active):
    binary = Path("/private/tmp/synlynk-relay-bin/nats-server")
    if not binary.exists():
        pytest.skip("NATS config validation binary not installed")
    store = DeviceCredentialStore(workspace, tmp_path)
    cred = store.add_device("laptop")
    if not active:
        store.revoke_device(cred.device_id)
    config = store.write_authorization_config()
    result = subprocess.run([str(binary), "-t", "-c", str(config)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "token:" not in config.read_text()


@pytest.mark.parametrize("event_type,suffix", [
    ("review_requested", "job.review_requested"),
    ("agent_started", "job.agent_started"),
    ("agent_completed", "job.agent_completed"),
    ("governs_stage_advanced", "job.governs_stage_advanced"),
    ("task_progress", "job.task_progress"),
    ("runner_progress", "agent.unknown.progress"),
    ("steering_injected", "device.unknown.steering"),
    ("doc_drafted", "doc.drafted"),
    ("doc_updated", "doc.updated"),
    ("hub_disconnected", "device.local.hub_disconnected"),
    ("sync_gap_detected", "device.local.sync_gap_detected"),
    ("goal_realigned", "custom.goal_realigned"),
    ("artifact_published", "custom.artifact_published"),
])
def test_subject_event_taxonomy(event_type, suffix):
    assert subject_for_event("ws1", event_type, {}) == f"synlynk.ws1.{suffix}"


@pytest.mark.parametrize("payload,suffix", [
    ({"harness": "codex", "agent_role": "dev"}, "agent.codex.dev"),
    ({"harness": "codex"}, "agent.codex.unknown"),
    ({"agent_role": "dev"}, "agent.unknown.dev"),
])
def test_progress_payload_metadata(payload, suffix):
    original = dict(payload)
    assert subject_for_event("ws1", "task_progress", payload) == f"synlynk.ws1.{suffix}"
    assert payload == original


@pytest.mark.parametrize("serialized", [False, True])
def test_progress_sender_metadata_takes_precedence(serialized):
    actor = ActorIdentifier("ws1", "m", "dev", "codex", "j1")
    sender = actor.to_dict() if serialized else actor
    payload = {"harness": "other", "agent_role": "other"}
    assert subject_for_event("ws1", "task_progress", payload, sender=sender) == "synlynk.ws1.agent.codex.dev"
    assert subject_for_event("ws1", "runner_progress", {}, sender=sender) == "synlynk.ws1.agent.codex.progress"


def test_partial_sender_falls_back_to_payload_without_mutation():
    sender = {"harness": "codex"}
    payload = {"agent_role": "dev"}
    assert subject_for_event("ws1", "task_progress", payload, sender=sender) == "synlynk.ws1.agent.codex.dev"
    assert sender == {"harness": "codex"}
    assert payload == {"agent_role": "dev"}
    assert subject_for_event("ws1", "task_progress", {}, sender={}) == "synlynk.ws1.job.task_progress"


def test_runner_progress_uses_payload_harness():
    assert subject_for_event("ws1", "runner_progress", {"harness": "codex"}) == "synlynk.ws1.agent.codex.progress"


def test_steering_targets_device():
    assert subject_for_event("ws1", "steering_injected", {"target_device_id": "dev-42"}) == "synlynk.ws1.device.dev-42.steering"


@pytest.mark.parametrize("bad", ["", "a.b", "*", ">", "a b", "a\t", "a\n", "a\u00a0b", "a\x00b", None, 42])
@pytest.mark.parametrize("field", ["workspace_id", "event_type", "target_device_id", "harness", "agent_role"])
def test_subject_segments_reject_injection(field, bad):
    workspace, event, payload = "ws1", "task_progress", {}
    if field == "workspace_id":
        workspace = bad
    elif field == "event_type":
        event = bad
    else:
        payload[field] = bad
        if field == "target_device_id":
            event = "steering_injected"
    with pytest.raises(ValueError, match=field):
        subject_for_event(workspace, event, payload)


@pytest.mark.parametrize("field", ["harness", "agent_role"])
def test_sender_segments_are_validated(field):
    with pytest.raises(ValueError, match=field):
        subject_for_event("ws1", "task_progress", {}, sender={field: "bad.*"})


@pytest.mark.parametrize("category", ["job", "sentinel", "agent", "device", "doc", "custom"])
def test_category_for_subject(category):
    assert category_for_subject(f"synlynk.ws1.{category}.topic") == category


@pytest.mark.parametrize("subject", ["", "synlynk", "synlynk.ws1", "synlynk.ws1.job", "other.ws1.job.topic", "synlynk..job.topic", "synlynk.ws1.unknown.topic", "synlynk.ws1.job.*", "synlynk.ws1.job.bad topic"])
def test_category_for_malformed_subject_falls_back(subject):
    assert category_for_subject(subject) == "custom"


def test_all_retention_budgets():
    assert RETENTION_POLICIES == {
        "job": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
        "sentinel": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
        "agent": {"max_msgs": 2_000, "max_age_seconds": 48 * 3600},
        "device": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
        "doc": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
        "custom": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    }


@pytest.mark.parametrize("event_type", (
    "hub_disconnected",
    "sync_gap_detected",
    "doc_drafted",
    "doc_updated",
))
def test_hub_event_types_are_accepted_by_envelope(event_type):
    actor = ActorIdentifier(
        workspace_id="ws", member_id="m", agent_role="dev",
        harness="codex", job_id="j1",
    )
    envelope = EventEnvelope.create(actor, event_type, {})
    assert envelope.event_type == event_type


def test_core_cli_import_does_not_require_nats():
    """synlynk's core CLI must import cleanly with no nats-py installed --
    hub features are optional, the base CLI is stdlib-only (CLAUDE.md constraint).
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk; import synlynk.cli"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_relay_hub_module_importable_without_nats_installed():
    """Importing synlynk.relay_hub itself must not require nats-py at import time --
    only calling HubAdapter.connect() should need it.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk.relay_hub"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
