import json
import os
from pathlib import Path
import subprocess
import sys
import queue
import threading
from types import SimpleNamespace

import pytest

from synlynk.relay_hub import build_doc_event_payload, write_doc_preview, DOC_PREVIEW_MAX_BYTES


def test_doc_payload_size_and_metadata():
    for content in ('# Hello\n', 'x' * (DOC_PREVIEW_MAX_BYTES + 1),
                    '\x00' * (DOC_PREVIEW_MAX_BYTES // 6),
                    '\U0001f600' * (DOC_PREVIEW_MAX_BYTES // 12)):
        payload = build_doc_event_payload('docs/superpowers/specs/x.md', 'b', 'abc', content,
                                          origin_device_id='dev-1')
        assert payload['origin_device_id'] == 'dev-1'
        assert payload['commit_sha'] == 'abc'
        assert len(json.dumps(payload).encode()) <= DOC_PREVIEW_MAX_BYTES
        assert ('content' in payload) == (content == '# Hello\n')


@pytest.mark.parametrize('path', ['/tmp/x', '../x', 'docs/superpowers/specs/../x',
    'docs/superpowers/specs', 'docs/superpowers/specs//x', 'docs/brainstorm/./x',
    'src/x', 'docs/superpowers/specs-evil/x', 'docs/brainstorm/x\\y',
    'docs/brainstorm/x\n.md', 'docs/brainstorm/x\x00'])
def test_doc_preview_rejects_bad_paths(tmp_path, path):
    with pytest.raises(ValueError):
        write_doc_preview(str(tmp_path), 'dev-1', path, 'content')


@pytest.mark.parametrize('device', ['', '.', '..', '../escape', '/tmp', 'x/y', 'x\\y', 'x\n'])
def test_doc_preview_rejects_bad_devices(tmp_path, device):
    with pytest.raises(ValueError):
        write_doc_preview(str(tmp_path), device, 'docs/brainstorm/x.md', 'content')


@pytest.mark.parametrize('root', ['docs/superpowers/specs', 'docs/superpowers/plans', 'docs/brainstorm'])
def test_doc_preview_atomic_readonly_replacement(tmp_path, root):
    import stat
    path = root + '/x.md'
    target = Path(write_doc_preview(str(tmp_path), 'dev-1', path, '# first'))
    first_inode = target.stat().st_ino
    assert target == tmp_path / 'dev-1' / path
    write_doc_preview(str(tmp_path), 'dev-1', path, '# second')
    assert 'PREVIEW ONLY' in target.read_text()
    assert '# second' in target.read_text() and '# first' not in target.read_text()
    assert stat.S_IMODE(target.stat().st_mode) == 0o444
    assert target.stat().st_ino != first_inode


@pytest.mark.parametrize('component', ['dev-1', 'dev-1/docs', 'dev-1/docs/brainstorm',
                                      'dev-1/docs/brainstorm/x.md'])
def test_doc_preview_rejects_symlinks(tmp_path, component):
    outside = tmp_path / 'outside'
    outside.mkdir()
    base = tmp_path / 'previews'
    link = base / component
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        write_doc_preview(str(base), 'dev-1', 'docs/brainstorm/x.md', 'content')
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize('event_type', ['doc_drafted', 'doc_updated'])
def test_doc_receive_preview_and_dedupe(bridge, tmp_path, event_type):
    broker, client, adapter = bridge
    adapter.preview_dir = tmp_path / 'previews'
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', None, '# received',
                                      origin_device_id='dev-remote')
    event = hub_event(event_type=event_type, payload=payload)
    subject = 'synlynk.ws1.doc.' + event_type.removeprefix('doc_')
    assert adapter._on_hub_message(subject, event.to_json().encode()) == 'ack'
    target = adapter.preview_dir / 'dev-remote/docs/brainstorm/x.md'
    assert '# received' in target.read_text()
    inode = target.stat().st_ino
    assert adapter._on_hub_message(subject, event.to_json().encode()) == 'ack'
    assert target.stat().st_ino == inode


def test_doc_outbound_limits_whole_envelope(bridge):
    broker, client, adapter = bridge
    client.device_id = 'dev-local'
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', None,
                                      'x' * (DOC_PREVIEW_MAX_BYTES - 250))
    assert 'content' in payload  # Payload fits; enclosing event does not.
    broker.publish(hub_event(event_type='doc_updated', payload=payload))
    subject, data = client.published.get(timeout=2)
    assert subject == 'synlynk.ws1.doc.updated'
    assert len(data) <= DOC_PREVIEW_MAX_BYTES
    assert 'content' not in json.loads(data)['payload']
    assert json.loads(data)['payload']['origin_device_id'] == 'dev-local'


@pytest.mark.parametrize('change', [{'path': '../escape'}, {'origin_device_id': '../escape'},
    {'content': 42}, {'content': 'x' * DOC_PREVIEW_MAX_BYTES}, {'origin_device_id': None}])
def test_doc_receive_rejects_poison(bridge, tmp_path, change):
    broker, client, adapter = bridge
    adapter.preview_dir = tmp_path / 'previews'
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', None, 'ok',
                                      origin_device_id='dev-remote')
    payload.update(change)
    event = hub_event(event_type='doc_updated', payload=payload)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', event.to_json().encode()) == 'term'
    assert not adapter.preview_dir.exists()


@pytest.mark.parametrize('path', ['docs/brainstorm/' + 'x' * 300,
                                'docs/brainstorm/' + 'x' * 300 + '/valid.md'])
def test_doc_receive_overlong_path_terminates_without_blocking(bridge, tmp_path, path):
    _, _, adapter = bridge
    adapter.preview_dir = tmp_path / 'previews'
    payload = build_doc_event_payload(path, 'b', None, 'invalid',
                                      origin_device_id='dev-remote')
    event = hub_event(event_type='doc_updated', payload=payload)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', event.to_json()) == 'term'
    payload = build_doc_event_payload('docs/brainstorm/valid.md', 'b', None, 'valid',
                                      origin_device_id='dev-remote')
    following = hub_event(event_type='doc_updated', payload=payload)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', following.to_json()) == 'ack'
    assert 'valid' in (adapter.preview_dir / 'dev-remote/docs/brainstorm/valid.md').read_text()


def test_doc_preview_rejects_base_symlink(tmp_path):
    (tmp_path / 'real').mkdir()
    (tmp_path / 'link').symlink_to(tmp_path / 'real')
    with pytest.raises(ValueError):
        write_doc_preview(str(tmp_path / 'link'), 'dev-1', 'docs/brainstorm/x.md', 'x')
    assert list((tmp_path / 'real').iterdir()) == []


def test_doc_preview_failed_replace_preserves_previous(tmp_path, monkeypatch):
    target = Path(write_doc_preview(str(tmp_path), 'dev-1', 'docs/brainstorm/x.md', 'old'))
    previous = target.read_bytes()
    def fail_replace(*args, **kwargs):
        raise OSError('disk error')
    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError):
        write_doc_preview(str(tmp_path), 'dev-1', 'docs/brainstorm/x.md', 'new')
    assert target.read_bytes() == previous
    assert list(target.parent.iterdir()) == [target]


def test_doc_receive_metadata_only(bridge, tmp_path):
    broker, client, adapter = bridge
    adapter.preview_dir = tmp_path / 'previews'
    subscriber = broker.subscribe()
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', 'sha',
                                      'x' * DOC_PREVIEW_MAX_BYTES, origin_device_id='dev-remote')
    assert 'content' not in payload
    event = hub_event(event_type='doc_updated', payload=payload)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', event.to_json().encode()) == 'ack'
    assert json.loads(subscriber.get(timeout=2))['payload'] == payload
    assert not adapter.preview_dir.exists()


def test_doc_receive_storage_failure_is_retryable(bridge, tmp_path, monkeypatch):
    import synlynk.relay_hub as hub
    broker, client, adapter = bridge
    adapter.preview_dir = tmp_path / 'previews'
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', None, 'ok',
                                      origin_device_id='dev-remote')
    event = hub_event(event_type='doc_updated', payload=payload)
    writer = hub.write_doc_preview
    def fail_write(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(hub, 'write_doc_preview', fail_write)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', event.to_json().encode()) == 'retry'
    assert event.event_id not in adapter._seen
    monkeypatch.setattr(hub, 'write_doc_preview', writer)
    assert adapter._on_hub_message('synlynk.ws1.doc.updated', event.to_json().encode()) == 'ack'
    assert (adapter.preview_dir / 'dev-remote/docs/brainstorm/x.md').exists()


def test_doc_payload_rejects_oversized_metadata():
    with pytest.raises(ValueError, match='metadata exceeds'):
        build_doc_event_payload('docs/brainstorm/x.md', 'b' * DOC_PREVIEW_MAX_BYTES, None, 'ok')


def test_doc_outbound_counts_actor_metadata_and_escaping(bridge):
    broker, client, adapter = bridge
    client.device_id = 'dev-local'
    payload = build_doc_event_payload('docs/brainstorm/x.md', 'b', None, '\x00' * 100_000)
    event = hub_event(event_type='doc_drafted', payload=payload,
                      sender=ActorIdentifier('ws1', 'm' * 500_000, 'dev', 'codex', 'j'))
    broker.publish(event)
    _, data = client.published.get(timeout=2)
    assert len(data) <= DOC_PREVIEW_MAX_BYTES
    raw = json.loads(data)
    assert raw['sender']['member_id'] == event.sender.member_id
    assert 'content' not in raw['payload']


def test_hub_cli_config_and_credentials(tmp_path, capsys):
    from synlynk.cli import main, build_parser
    tmp_path = tmp_path / "credentials"
    common = ["--workspace-id", "ws1", "--config-dir", str(tmp_path)]
    args = build_parser().parse_args(["relay", "device", "add", "laptop", *common])
    assert (args.relay_action, args.relay_device_action, args.name) == ("device", "add", "laptop")
    main(["relay", "hub", "init", *common])
    assert "nats-server -c" in capsys.readouterr().out
    main(["relay", "device", "add", "laptop", *common])
    cred = DeviceCredentialStore("ws1", tmp_path).list_devices()[0]
    output = capsys.readouterr().out
    assert cred.device_id in output and "laptop" in output
    assert output.count("keep this file secret") == 1
    assert cred.token not in output
    config = (tmp_path / "nats.conf").read_text()
    assert "jetstream" in config and cred.token in config
    main(["relay", "device", "revoke", cred.device_id, *common])
    assert "reload" in capsys.readouterr().out.lower()
    assert cred.token not in (tmp_path / "nats.conf").read_text()
    main(["relay", "device", "revoke", "dev-unknown", *common])
    assert "not found" in capsys.readouterr().out.lower()
    for path in tmp_path.iterdir():
        if path.is_file():
            assert path.stat().st_mode & 0o777 == 0o600


def test_subscription_cli_before_init(tmp_path, monkeypatch):
    from synlynk.cli import main
    monkeypatch.chdir(tmp_path)
    main(["relay", "unsubscribe", "job.>"])
    path = tmp_path / ".synlynk/relay-subscriptions.json"
    assert json.loads(path.read_text()) == []
    main(["relay", "subscribe", "job.>"])
    main(["relay", "subscribe", "job.>"])
    assert json.loads(path.read_text()) == ["job.>"]


@pytest.mark.parametrize("patterns,delivered", [(None, True), ([], False), (["job.*"], True), (["doc.>"], False)])
def test_subscription_filters_delivery(project_dir, patterns, delivered):
    broker, client = RelayBroker(), FakeNatsClient()
    adapter = HubAdapter(broker, client, "ws1", subscriptions=patterns)
    subscriber = broker.subscribe()
    adapter.attach()
    try:
        assert adapter._on_hub_message("synlynk.ws1.job.review_requested", hub_event().to_json()) == "ack"
        assert (not subscriber.empty()) is delivered
    finally:
        adapter.detach()


def test_hub_daemon_rejected():
    from synlynk.cli import main
    from synlynk.cli import build_parser
    assert build_parser().parse_args(["relay", "start", "--hub", "--daemon"]).hub
    with pytest.raises(SystemExit, match="2"):
        main(["relay", "start", "--hub", "--daemon"])


def test_managed_connect_is_private_and_explicit(tmp_path, capsys):
    from synlynk.cli import main
    main(["relay", "hub", "connect", "private-token", "--workspace-id", "ws1", "--config-dir", str(tmp_path)])
    output = capsys.readouterr().out
    assert "not implemented" in output and "private-token" not in output
    assert (tmp_path / "hub.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("fail", [False, True])
def test_cli_hub_start_uses_server_broker_and_cleans_up(project_dir, tmp_path, monkeypatch, fail):
    from synlynk.cli import main
    import synlynk.relay_hub as hub
    import synlynk.relay as relay
    common = ["--workspace-id", "ws1", "--config-dir", str(tmp_path / "config")]
    main(["relay", "hub", "init", *common])
    main(["relay", "device", "add", "laptop", *common])
    cred = DeviceCredentialStore("ws1", tmp_path / "config").list_devices()[0]
    main(["relay", "unsubscribe", "job.>"])
    observed = {}

    class Server:
        def __init__(self, port):
            observed["port"] = port
            self.broker = object()
            observed["broker"] = self.broker
            self.httpd = SimpleNamespace(server_close=lambda: observed.update(closed=True))

        def start(self, background):
            assert not background and observed["attached"]
            if fail:
                raise KeyboardInterrupt

    class Adapter:
        def __init__(self, broker, client, workspace, **options):
            assert broker is observed["broker"] and workspace == "ws1"
            assert options == {"owns_client": True, "subscriptions": []}

        def attach(self):
            observed["attached"] = True

        def detach(self):
            observed["detached"] = True

    def transport(servers, **options):
        assert servers == ["nats://example:4223"]
        assert options == {"user": cred.device_id, "password": cred.token}
        return object()

    monkeypatch.setattr(relay, "RelayServer", Server)
    monkeypatch.setattr(hub, "HubAdapter", Adapter)
    monkeypatch.setattr(hub, "NatsTransport", transport)
    argv = ["relay", "start", "--hub", "--device-id", cred.device_id,
            "--config-dir", str(tmp_path / "config"), "--port", "8001",
            "--hub-url", "nats://example:4223"]
    if fail:
        with pytest.raises(KeyboardInterrupt):
            main(argv)
    else:
        main(argv)
    assert observed["closed"] and observed["detached"] and observed["port"] == 8001


@pytest.mark.parametrize("subcommand", ["hub", "device"])
def test_nested_relay_help(subcommand, capsys):
    from synlynk.cli import main
    main(["relay", subcommand])
    assert f"relay {subcommand}" in capsys.readouterr().out


def test_default_relay_start_stays_local(monkeypatch):
    from synlynk.cli import main
    import synlynk.relay as relay
    import synlynk.relay_hub as hub
    seen = {}

    class Server:
        def __init__(self, port):
            seen["port"] = port

        def start(self, background):
            seen["background"] = background

    monkeypatch.setattr(relay, "RelayServer", Server)
    monkeypatch.setattr(hub, "run_hub_relay", lambda args: pytest.fail("Unexpected opt-in"))
    main(["relay", "start"])
    assert seen == {"port": 7432, "background": False}


@pytest.mark.parametrize("pattern", ["", "job.>.x", "job.x*", "job..x", "job.bad token"])
def test_invalid_subscription_is_not_written(tmp_path, monkeypatch, pattern):
    from synlynk.cli import main
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        main(["relay", "subscribe", pattern])
    assert not (tmp_path / ".synlynk/relay-subscriptions.json").exists()

from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay_hub import DeviceCredentialStore, RETENTION_POLICIES, category_for_subject, subject_for_event
from synlynk.relay import RelayBroker
from synlynk.relay_hub import HubAdapter, NatsTransport
from synlynk.relay_hub import ReplayTracker


class FakeJetStreamConsumer:
    def __init__(self, messages, earliest_seq=1):
        self.messages = messages
        self.earliest_seq = earliest_seq

    def fetch_since(self, last_seq):
        return [message for message in self.messages if message[0] > last_seq]


def test_replay_tracker_resumes():
    tracker = ReplayTracker("dev-1")
    tracker.record_delivered(5)
    pending = tracker.replay(FakeJetStreamConsumer([(6, "subject", "a"), (7, "subject", "b")]))
    assert [item[0] for item in pending] == [6, 7]
    assert tracker.last_delivered_seq == 7


@pytest.mark.parametrize("last,earliest,gap", [(None, 50, False), (5, 50, True), (5, 6, False), (5, 1, False)])
def test_replay_gap_boundary(last, earliest, gap):
    tracker = ReplayTracker("dev-1")
    if last is not None:
        tracker.record_delivered(last)
    assert tracker.detect_sync_gap(FakeJetStreamConsumer([], earliest)) is gap


def test_adapter_restart_dedupes_persisted_events(project_dir):
    broker, client = RelayBroker(), FakeNatsClient()
    event = hub_event()
    broker.publish(event)
    subscriber = broker.subscribe()
    adapter = HubAdapter(broker, client, "ws1")
    adapter.attach()
    try:
        assert adapter._on_hub_message("synlynk.ws1.job.review_requested", event.to_json()) == "ack"
        assert subscriber.empty()
    finally:
        adapter.detach()


def test_adapter_delivery_dispositions(bridge, monkeypatch):
    broker, client, adapter = bridge
    event = hub_event()
    subject = "synlynk.ws1.job.review_requested"
    assert adapter._on_hub_message(subject, b"bad json") == "term"
    with monkeypatch.context() as patch:
        patch.setattr(broker, "publish", lambda event: (_ for _ in ()).throw(OSError("disk full")))
        assert adapter._on_hub_message(subject, event.to_json()) == "retry"
    assert adapter._on_hub_message(subject, event.to_json()) == "ack"
    adapter.detach()
    assert adapter._on_hub_message(subject, event.to_json()) == "retry"


def test_gap_marker_is_local_only(bridge):
    broker, client, adapter = bridge
    subscriber = broker.subscribe()
    adapter._on_sync_gap("job-stream", 5, 50)
    event = json.loads(subscriber.get(timeout=2))
    assert event["event_type"] == "sync_gap_detected"
    assert event["payload"]["earliest_seq"] == 50
    broker.publish(hub_event())  # Pump barrier.
    assert json.loads(client.published.get(timeout=2)[1])["event_type"] == "review_requested"
    adapter.detach()
    assert client.published.empty()


@pytest.fixture
def fake_jetstream(monkeypatch):
    import asyncio
    import synlynk.relay_hub as hub
    api = pytest.importorskip("nats.js.api")
    from nats.js.errors import NotFoundError
    from nats.errors import TimeoutError as NatsTimeout

    class Subscription:
        def __init__(self, stream, durable):
            self.stream, self.durable = stream, durable
            self.closed = False

        async def fetch(self, batch, timeout):
            assert batch == 1
            await asyncio.sleep(0.01)
            consumer = client.consumers[self.stream, self.durable]
            for message in client.messages.get(self.stream, []):
                if message.metadata.sequence.stream > consumer.ack_floor.stream_seq:
                    if self.stream in client.prune_on_fetch:
                        client.streams[self.stream].state.first_seq = client.prune_on_fetch[self.stream]
                    return [message]
            raise NatsTimeout()

        async def unsubscribe(self):
            self.closed = True

    class Client:
        def __init__(self):
            self.streams, self.consumers, self.messages = {}, {}, {}
            self.subscriptions = []
            self.published = []
            self.prune_on_fetch = {}
            self.closed = False

        async def connect(self, **kwargs):
            self.options = kwargs

        def jetstream(self, **kwargs):
            return self

        async def stream_info(self, stream):
            if stream not in self.streams:
                raise NotFoundError()
            return self.streams[stream]

        async def add_stream(self, config):
            assert isinstance(config, api.StreamConfig)
            self.streams[config.name] = SimpleNamespace(config=config, state=SimpleNamespace(first_seq=1))
            return self.streams[config.name]

        async def consumer_info(self, stream, durable):
            if (stream, durable) not in self.consumers:
                raise NotFoundError()
            return self.consumers[stream, durable]

        async def add_consumer(self, stream, config):
            self.consumers[stream, config.durable_name] = SimpleNamespace(
                config=config, ack_floor=SimpleNamespace(stream_seq=0))

        async def pull_subscribe_bind(self, *, stream, durable):
            sub = Subscription(stream, durable)
            self.subscriptions.append(sub)
            return sub

        async def publish(self, subject, data, **kwargs):
            self.published.append((subject, data))

        async def flush(self, **kwargs):
            pass

        async def close(self):
            self.closed = True

        def enqueue(self, stream, seq, data, subject="synlynk.ws1.job.review_requested"):
            message = SimpleNamespace(subject=subject, data=data,
                                      metadata=SimpleNamespace(sequence=SimpleNamespace(stream=seq)))
            message.dispositions = queue.Queue()

            async def ack_sync(**kwargs):
                # Persistence must precede positive acknowledgment.
                from synlynk.relay import _db
                conn = _db()
                try:
                    assert conn.execute("SELECT 1 FROM relay_events WHERE event_id=?",
                                        (json.loads(data)["event_id"],)).fetchone()
                finally:
                    conn.close()
                self.consumers[stream, hub._durable_name("dev-1")].ack_floor.stream_seq = seq
                message.dispositions.put("ack")

            async def term():
                self.consumers[stream, hub._durable_name("dev-1")].ack_floor.stream_seq = seq
                message.dispositions.put("term")

            async def nak(**kwargs):
                message.dispositions.put("retry")
            message.ack_sync, message.term, message.nak = ack_sync, term, nak
            self.messages.setdefault(stream, []).append(message)
            return message

    client = Client()
    monkeypatch.setattr(hub, "_import_nats", lambda: SimpleNamespace(NATS=lambda: client))
    return client


def test_wired_jetstream_restart_ack_and_independent_streams(project_dir, fake_jetstream):
    from synlynk.relay_hub import _stream_name, _durable_name, _inbox_prefix
    client = fake_jetstream
    broker = RelayBroker()
    subscriber = broker.subscribe()
    transport = NatsTransport("nats://fake", user="dev-1", password="secret")
    adapter = HubAdapter(broker, transport, "ws1", owns_client=True)
    adapter.attach()
    try:
        assert len(client.streams) == len(client.consumers) == 6
        assert client.options["inbox_prefix"] == _inbox_prefix("dev-1").encode()
        for category, budget in RETENTION_POLICIES.items():
            stream = _stream_name("ws1", category)
            assert client.streams[stream].config.max_msgs == budget["max_msgs"]
            assert client.streams[stream].config.max_age == budget["max_age_seconds"]
        event = hub_event()
        job = _stream_name("ws1", "job")
        message = client.enqueue(job, 5, event.to_json())
        assert message.dispositions.get(timeout=2) == "ack"
        assert json.loads(subscriber.get(timeout=2))["event_id"] == event.event_id
        assert client.consumers[_stream_name("ws1", "agent"), _durable_name("dev-1")].ack_floor.stream_seq == 0
    finally:
        adapter.detach()
    assert all(sub.closed for sub in client.subscriptions)
    # A new transport/adapter binds existing consumers and receives offline work.
    transport = NatsTransport("nats://fake", user="dev-1", password="secret")
    adapter = HubAdapter(broker, transport, "ws1", owns_client=True)
    client.streams[job].state.first_seq = 50
    # The server may advance its floor as retention deletes pending messages.
    # A local durable cursor must preserve what this device actually received.
    client.consumers[job, _durable_name("dev-1")].ack_floor.stream_seq = 49
    pending = client.enqueue(job, 50, hub_event().to_json())
    adapter.attach()
    try:
        gap = json.loads(subscriber.get(timeout=2))
        assert gap["event_type"] == "sync_gap_detected"
        assert gap["payload"]["last_delivered_seq"] == 5
        assert pending.dispositions.get(timeout=2) == "ack"
        assert message.dispositions.empty()
        assert not client.published
    finally:
        adapter.detach()


def test_wired_jetstream_never_acks_failed_persistence(project_dir, fake_jetstream, monkeypatch):
    import time
    from synlynk.relay_hub import _stream_name
    broker = RelayBroker()
    transport = NatsTransport("nats://fake", user="dev-1")
    adapter = HubAdapter(broker, transport, "ws1", owns_client=True)
    adapter.attach()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(broker, "publish", lambda event: (_ for _ in ()).throw(OSError("disk full")))
            message = fake_jetstream.enqueue(_stream_name("ws1", "job"), 1, hub_event().to_json())
            assert message.dispositions.get(timeout=2) == "retry"
            assert isinstance(adapter.last_error, OSError)
        deadline = time.monotonic() + 2
        while message.dispositions.get(timeout=2) == "retry":
            assert time.monotonic() < deadline
        poison = fake_jetstream.enqueue(_stream_name("ws1", "job"), 2, b"bad json")
        assert poison.dispositions.get(timeout=2) == "term"
        assert isinstance(adapter.last_error, ValueError)
    finally:
        adapter.detach()


def test_retention_race_during_fetch_emits_gap_before_delivery(project_dir, fake_jetstream):
    from synlynk.relay_hub import _stream_name
    client = fake_jetstream
    broker = RelayBroker()
    subscriber = broker.subscribe()
    transport = NatsTransport("nats://fake", user="dev-1")
    adapter = HubAdapter(broker, transport, "ws1", owns_client=True)
    adapter.attach()
    try:
        stream = _stream_name("ws1", "job")
        client.prune_on_fetch[stream] = 50
        message = client.enqueue(stream, 50, hub_event().to_json())
        assert message.dispositions.get(timeout=2) == "ack"
        assert json.loads(subscriber.get(timeout=2))["event_type"] == "sync_gap_detected"
        assert json.loads(subscriber.get(timeout=2))["event_type"] == "review_requested"
    finally:
        adapter.detach()


def test_jetstream_permissions_are_device_and_workspace_scoped(tmp_path):
    from synlynk.relay_hub import _stream_name, _durable_name, _inbox_prefix
    store = DeviceCredentialStore("ws1", tmp_path)
    first, second = store.add_device("first"), store.add_device("second")
    users = json.loads(store.render_authorization_block().removeprefix("authorization "))["users"]
    permissions = users[0]["permissions"]
    assert _inbox_prefix(first.device_id) + ".>" in permissions["subscribe"]
    assert _inbox_prefix(second.device_id) + ".>" not in permissions["subscribe"]
    for category in RETENTION_POLICIES:
        stream, durable = _stream_name("ws1", category), _durable_name(first.device_id)
        assert f"$JS.API.CONSUMER.MSG.NEXT.{stream}.{durable}" in permissions["publish"]
        assert f"$JS.ACK.{stream}.{durable}.>" in permissions["publish"]
    assert not {">", "$JS.>", "$JS.API.>", "$JS.ACK.>", "_INBOX.>"}.intersection(
        permissions["publish"] + permissions["subscribe"])


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
