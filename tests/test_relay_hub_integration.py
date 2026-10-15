"""Local authenticated JetStream integration; requires nats-server on PATH.

Each CLI device owns a separate process, database and exported credential.
The child observer only records a real broker subscriber's deliveries.
"""

import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen

import pytest

from synlynk.cli import main
from synlynk.events import ActorIdentifier, EventEnvelope
from synlynk.relay import RelayBroker
from synlynk.relay_hub import DeviceCredentialStore, HubAdapter, NatsTransport, _stream_name

nats = pytest.importorskip("nats")
pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None,
    reason="install nats-server and put it on PATH",
)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolate_hub_state(tmp_path, monkeypatch):
    # An inherited explicit DB override takes precedence over conftest.DB_PATH.
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(tmp_path / "test-state.db"))


# Observe queue delivery without changing broker, adapter or transport behavior.
DEVICE = r'''
import json, threading
from synlynk.relay import RelayServer
from synlynk.cli import main
original = RelayServer.__init__
def observe(self, *args, **kwargs):
    original(self, *args, **kwargs)
    subscriber = self.broker.subscribe()
    def record():
        with open("deliveries.jsonl", "a", buffering=1) as output:
            while True:
                output.write(subscriber.get() + "\n")
    threading.Thread(target=record, daemon=True).start()
RelayServer.__init__ = observe
main()
'''


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def eventually(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    assert predicate(), "condition did not become true before deadline"


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


class Device:
    def __init__(self, directory, credential, source, url):
        self.directory, self.credential, self.url = directory, credential, url
        directory.mkdir()
        self.creds = directory / "device.creds"
        shutil.copyfile(source, self.creds)
        self.creds.chmod(0o600)
        self.port = free_port()
        self.process = None
        self.log = None

    def start(self, filters=None):
        if filters is not None:
            settings = self.directory / ".synlynk"
            settings.mkdir(exist_ok=True)
            (settings / "relay-subscriptions.json").write_text(json.dumps(filters))
        env = {**os.environ, "PYTHONPATH": str(ROOT),
               "HOME": str(self.directory), "SYNLYNK_ALLOW_CWD_FALLBACK": "1",
               "SYNLYNK_STATE_DB_PATH": str(self.directory / "state.db")}
        self.log = (self.directory / "device.log").open("a")
        self.process = subprocess.Popen(
            [sys.executable, "-c", DEVICE, "relay", "start", "--hub",
             "--credential-file", str(self.creds), "--workspace-id", "ws1",
             "--hub-url", self.url, "--port", str(self.port)],
            cwd=self.directory, env=env, stdout=self.log, stderr=self.log)

        def ready():
            assert self.process.poll() is None, (self.directory / "device.log").read_text()
            try:
                self.rpc("relay.peer_list")
                return True
            except OSError:
                return False
        eventually(ready)
        assert not (self.directory / "devices.json").exists()

    def stop(self):
        if self.process is not None:
            stop(self.process)
        if self.log is not None:
            self.log.close()

    def rpc(self, method, **params):
        request = Request(f"http://127.0.0.1:{self.port}/rpc",
                          json.dumps({"method": method, "params": {
                              "workspace_id": "ws1", **params}}).encode(),
                          {"Content-Type": "application/json"})
        with urlopen(request, timeout=0.5) as response:
            return json.load(response)["result"]

    def events(self):
        path = self.directory / "deliveries.jsonl"
        if not path.exists():
            return []
        # Ignore a final incomplete write while the observer is flushing.
        return [json.loads(line) for line in path.read_text().splitlines(keepends=True)
                if line.endswith("\n")]

    def received(self, *ids):
        eventually(lambda: set(ids) <= {e["event_id"] for e in self.events()})

    def cursor(self, category):
        with sqlite3.connect(self.directory / "state.db") as conn:
            row = conn.execute("SELECT seq FROM relay_hub_cursors WHERE stream=?",
                               (_stream_name("ws1", category),)).fetchone()
            return row[0] if row else None


@pytest.fixture
def hub(tmp_path):
    port = free_port()
    url = f"nats://127.0.0.1:{port}"
    admin = tmp_path / "admin"
    common = ["--workspace-id", "ws1", "--config-dir", str(admin)]
    main(["relay", "hub", "init", *common, "--listen", f"127.0.0.1:{port}", "--url", url])
    for name in ("a", "b"):
        main(["relay", "device", "add", name, *common])
    store = DeviceCredentialStore("ws1", admin)
    credentials = {c.name: c for c in store.list_devices()}
    devices = {name: Device(tmp_path / name, cred, admin / (cred.device_id + ".creds"), url)
               for name, cred in credentials.items()}
    monitor_port = free_port()
    for device in devices.values():
        device.monitor_url = f"http://127.0.0.1:{monitor_port}/connz?auth=1"
    log_path = tmp_path / "nats.log"
    with log_path.open("w") as log:
        process = subprocess.Popen([shutil.which("nats-server"), "-c", str(admin / "nats.conf"),
                                    "-m", str(monitor_port)],
                                   stdout=log, stderr=log)
        try:
            def ready():
                assert process.poll() is None, log_path.read_text()
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        return True
                except OSError:
                    return False
            eventually(ready)
            yield devices, store, process, common, log_path
        finally:
            for device in devices.values():
                device.stop()
            stop(process)


def test_two_cli_devices_exactly_once_replay_and_category_sequences(hub):
    devices, _, _, _, _ = hub
    a, b = devices["a"], devices["b"]
    a.start()
    b.start()
    first = a.rpc("relay.request_review")["event"]
    a.received(first["event_id"])
    b.received(first["event_id"])
    eventually(lambda: b.cursor("job") == 1)
    b.stop()
    offline = [a.rpc("relay.request_review")["event"] for _ in range(3)]
    agent = a.rpc("relay.runner_progress")["event"]
    eventually(lambda: a.cursor("job") == 4 and a.cursor("agent") == 1)
    # Publish a duplicate as a new JetStream sequence, after process restart
    # has discarded B's in-memory dedupe cache.
    transport = NatsTransport(a.url, user=a.credential.device_id, password=a.credential.token)
    try:
        transport.publish("synlynk.ws1.job.review_requested", json.dumps(first))
    finally:
        transport.close()
    b.start()
    ids = [first["event_id"], *(e["event_id"] for e in offline), agent["event_id"]]
    for device in (a, b):
        device.received(*ids)
        eventually(lambda: device.cursor("job") == 5 and device.cursor("agent") == 1)
    reverse = b.rpc("relay.request_review")["event_id"]
    for device in (a, b):
        device.received(reverse)
        eventually(lambda: device.cursor("job") == 6)
        assert Counter(e["event_id"] for e in device.events()) == Counter([*ids, reverse])


def test_real_retention_gap_and_subscription_filters(hub):
    devices, _, _, _, _ = hub
    a, b = devices["a"], devices["b"]
    # Provision a tiny real retention budget to exercise eviction deterministically.
    transport = NatsTransport(a.url, user=a.credential.device_id, password=a.credential.token)
    async def provision():
        from nats.js.api import StreamConfig
        await transport._client.jetstream().add_stream(config=StreamConfig(
            name=_stream_name("ws1", "job"), subjects=["synlynk.ws1.job.>"], max_msgs=2))
    try:
        transport._call(provision())
    finally:
        transport.close()
    a.start()
    b.start(filters=["job.>"])
    first = a.rpc("relay.request_review")["event_id"]
    b.received(first)
    eventually(lambda: b.cursor("job") == 1)
    b.stop()
    offline = []
    for seq in range(2, 6):
        offline.append(a.rpc("relay.request_review")["event_id"])
        eventually(lambda: a.cursor("job") == seq)
    b.start()
    b.received(*offline[-2:])
    eventually(lambda: b.cursor("job") == 5)
    gaps = [e for e in b.events() if e["event_type"] == "sync_gap_detected"]
    assert len(gaps) == 1
    assert gaps[0]["payload"] == {"stream": _stream_name("ws1", "job"),
                                  "last_delivered_seq": 1, "earliest_seq": 4}
    excluded = a.rpc("relay.runner_progress")["event_id"]
    eventually(lambda: b.cursor("agent") == 1)
    barrier = a.rpc("relay.request_review")["event_id"]
    b.received(barrier)
    assert Counter(e["event_id"] for e in b.events()) == Counter(
        [first, *offline[-2:], gaps[0]["event_id"], barrier])
    assert excluded not in {e["event_id"] for e in b.events()}
    assert not any(e["event_type"] == "sync_gap_detected" for e in a.events())


def test_revoked_credential_refused_after_real_config_reload(hub):
    devices, _, process, common, log_path = hub
    a, b = devices["a"], devices["b"]
    a.start()
    b.start()
    before = a.rpc("relay.request_review")["event_id"]
    b.received(before)
    def connected(device):
        with urlopen(device.monitor_url, timeout=1) as response:
            return device.credential.device_id in json.dumps(json.load(response))
    assert connected(a) and connected(b)
    main(["relay", "device", "revoke", b.credential.device_id, *common])
    process.send_signal(signal.SIGHUP)
    eventually(lambda: "Reloaded server configuration" in log_path.read_text())
    # Observe server-side disconnection of the previously authenticated user.
    eventually(lambda: not connected(b))
    assert connected(a)

    async def refused():
        async def ignore_error(error):
            pass
        with pytest.raises(nats.errors.Error, match="Authorization"):
            client = await nats.connect(a.url, user=b.credential.device_id,
                                        password=b.credential.token, allow_reconnect=False,
                                        connect_timeout=1, error_cb=ignore_error)
            await client.close()
    asyncio.run(refused())
    # The already connected active device still publishes and acknowledges.
    after = a.rpc("relay.request_review")["event_id"]
    a.received(after)
    eventually(lambda: a.cursor("job") == 2)
    # A new active connection also works after reload.
    active = NatsTransport(a.url, user=a.credential.device_id, password=a.credential.token,
                           allow_reconnect=False)
    active.close()
    assert after not in {e["event_id"] for e in b.events()}


def test_live_wrong_workspace_subject_and_envelope_rejected(hub):
    devices, _, _, _, _ = hub
    a, b = devices["a"], devices["b"]
    a.start()
    b.start()
    client = NatsTransport(a.url, user=a.credential.device_id,
                           password=a.credential.token)
    try:
        forged = hub_event().to_dict()
        forged["sender"]["workspace_id"] = "foreign"
        client.publish("synlynk.foreign.job.review_requested", json.dumps(forged))
        eventually(lambda: client.last_error is not None)
        assert "permissions violation" in str(client.last_error).lower()
        # A valid workspace subject cannot smuggle a foreign actor into the
        # receiving broker. Both devices consume/terminate this stream entry.
        client.publish("synlynk.ws1.job.review_requested", json.dumps(forged))
        eventually(lambda: a.cursor("job") == 1 and b.cursor("job") == 1)
        barrier = a.rpc("relay.request_review")["event_id"]
        for device in (a, b):
            device.received(barrier)
            eventually(lambda: device.cursor("job") == 2)
            assert forged["event_id"] not in {e["event_id"] for e in device.events()}
    finally:
        client.close()


def hub_event():
    return EventEnvelope.create(
        ActorIdentifier("ws1", "m", "dev", "codex", "j"),
        "review_requested", {"pr_url": "https://x"})


@pytest.mark.parametrize("cli_config", [False, True])
def test_authenticated_jetstream_transport_smoke(project_dir, tmp_path, cli_config):
    """Exercise both direct and CLI-generated server configuration."""
    import socket
    import time
    pytest.importorskip("nats")
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("optional local nats-server unavailable")
    store = DeviceCredentialStore("ws1", tmp_path / "credentials")
    receiver, sender = store.add_device("receiver"), store.add_device("sender")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = tmp_path / "server.conf"
    config.write_text(f"host: 127.0.0.1\nport: {port}\n"
                      + "jetstream { store_dir: " + json.dumps(str(tmp_path / "jetstream")) + " }\n"
                      + store.render_authorization_block())
    if cli_config:
        from synlynk.cli import main
        directory = tmp_path / "cli-credentials"
        common = ["--workspace-id", "ws1", "--config-dir", str(directory)]
        main(["relay", "hub", "init", *common, "--listen", f"127.0.0.1:{port}",
              "--url", f"nats://127.0.0.1:{port}"])
        main(["relay", "device", "add", "receiver", *common])
        main(["relay", "device", "add", "sender", *common])
        receiver, sender = DeviceCredentialStore("ws1", directory).list_devices()
        config = directory / "nats.conf"
    log = (tmp_path / "server.log").open("w+")
    process = subprocess.Popen([str(binary), "-c", str(config)], stdout=log, stderr=log)
    adapters, transports = [], []
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    log.seek(0)
                    pytest.fail(log.read())
                time.sleep(0.05)
        url = f"nats://127.0.0.1:{port}"
        broker = RelayBroker()
        subscriber = broker.subscribe()

        def attach():
            transport = NatsTransport(url, user=receiver.device_id, password=receiver.token)
            transports.append(transport)
            adapter = HubAdapter(broker, transport, "ws1", owns_client=True)
            adapters.append(adapter)
            adapter.attach()
            return adapter, transport

        adapter, transport = attach()
        publisher = NatsTransport(url, user=sender.device_id, password=sender.token)
        transports.append(publisher)
        event = hub_event()
        subject = "synlynk.ws1.job.review_requested"
        publisher.publish(subject, event.to_json())
        assert json.loads(subscriber.get(timeout=5))["event_id"] == event.event_id
        adapter.detach()
        offline = hub_event()
        publisher.publish(subject, offline.to_json())
        # Restart with the same credentials and local DB; replay an old event ID
        # as a new stream message too, proving persistent local deduplication.
        publisher.publish(subject, event.to_json())
        adapter, transport = attach()
        assert json.loads(subscriber.get(timeout=5))["event_id"] == offline.event_id
        barrier = hub_event()
        publisher.publish(subject, barrier.to_json())
        assert json.loads(subscriber.get(timeout=5))["event_id"] == barrier.event_id
        adapter.detach()
        assert subscriber.empty()
        assert transport.last_error is None
        assert publisher.last_error is None
    finally:
        for adapter in adapters:
            adapter.detach()
        for transport in transports:
            transport.close()
        stop(process)
        log.close()


@pytest.mark.parametrize("workspace", ["ws1", 'ws"quoted\\name'])
@pytest.mark.parametrize("active", [True, False])
def test_authorization_parses_with_real_nats(tmp_path, workspace, active):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("NATS config validation binary not installed")
    store = DeviceCredentialStore(workspace, tmp_path)
    cred = store.add_device("laptop")
    if not active:
        store.revoke_device(cred.device_id)
    config = store.write_authorization_config()
    result = subprocess.run([str(binary), "-t", "-c", str(config)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "token:" not in config.read_text()
