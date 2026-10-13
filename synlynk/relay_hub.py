"""Opt-in NATS-backed hub bridge for the local relay (synlynk/relay.py).

Credential model deviation from the design spec (docs/superpowers/specs/
2026-10-12-personal-hosted-relay-design.md): per-device bearer tokens scoped
via NATS `authorization { users: [...] }` permission blocks, not nkey+JWT.
Real nkey/JWT minting needs the `nsc` toolchain and is deferred until a
multi-tenant managed hub actually requires it. See plan's "Decision Flagged
for Review" section for full rationale.

`nats-py` is an optional dependency (pyproject.toml `[hub]` extra) and is
imported lazily inside functions that need it, so importing this module
(or synlynk's core CLI) never requires it to be installed.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import queue
import secrets
import tempfile
import threading
import uuid

from synlynk.events import ActorIdentifier, EventEnvelope


_LOG = logging.getLogger(__name__)


class NatsTransport:
    """Synchronous bridge API backed by an owned nats-py loop and connection.

    Construct outside an asyncio callback. Operations have bounded waits and
    raise on failure; asynchronous NATS errors are logged and in last_error.
    Pass native user/password for DeviceCredentialStore bearer credentials.
    Call close() when finished. This is core NATS, not durable JetStream.
    """

    def __init__(self, servers, *, timeout=5.0, **connect_options):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        nats = _import_nats()
        self.timeout = timeout
        self.last_error = None
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="relay-nats", daemon=True)
        self._thread.start()
        self._client = None

        async def connect():
            self._client = nats.NATS()
            supplied_error_cb = connect_options.pop("error_cb", None)

            async def error_cb(error):
                self.last_error = error
                _LOG.error("NATS transport asynchronous error: %s", type(error).__name__)
                if supplied_error_cb:
                    await supplied_error_cb(error)

            await self._client.connect(servers=servers, error_cb=error_cb, **connect_options)

        try:
            self._call(connect())
        except BaseException:
            self.close()
            raise

    def _run(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    def _call(self, coroutine):
        if self._closed or threading.current_thread() is self._thread:
            coroutine.close()
            raise RuntimeError("NATS transport is closed or called from its own loop")
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=self.timeout)
        except BaseException as error:
            future.cancel()
            self.last_error = error
            raise

    def publish(self, subject, payload):
        async def publish():
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            await self._client.publish(subject, data)
            await self._client.flush(timeout=self.timeout)
        return self._call(publish())

    def subscribe(self, subject, callback):
        async def subscribe():
            async def receive(message):
                callback(message.subject, message.data)
            subscription = await self._client.subscribe(subject, cb=receive)
            try:
                await self._client.flush(timeout=self.timeout)
            except BaseException:
                await subscription.unsubscribe()
                raise
            return subscription
        return self._call(subscribe())

    def unsubscribe(self, subscription):
        async def unsubscribe():
            await subscription.unsubscribe()
            await self._client.flush(timeout=self.timeout)
        return self._call(unsubscribe())

    def close(self):
        if self._closed:
            return
        if threading.current_thread() is self._thread:
            raise RuntimeError("Close NATS transport from outside its loop")
        try:
            if self._client is not None:
                self._call(self._client.close())
        finally:
            self._closed = True
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(self.timeout)
            if self._thread.is_alive():
                raise TimeoutError("NATS loop did not stop")


class HubAdapter:
    """Bridge broker queues through a synchronous transport (or injected fake).

    For production pass NatsTransport, NOT a raw async nats-py Client. Injected
    clients are borrowed unless owns_client=True; an owned client is closed on
    detach, making that adapter terminal. Local queues retain broker semantics.
    Dedupe is bounded, in-memory only; persistent replay belongs to Task 6.
    Transport failures are observable via last_error and logging, not retried.
    """

    def __init__(self, broker, client, workspace_id, *, owns_client=False,
                 max_seen=10_000, shutdown_timeout=10.0):
        self.workspace_id = _subject_segment(workspace_id, "workspace_id")
        if max_seen < 512 or shutdown_timeout <= 0:
            raise ValueError("max_seen must be >=512 and shutdown_timeout positive")
        self.broker, self.client = broker, client
        self.owns_client = owns_client
        self.max_seen = max_seen
        self.shutdown_timeout = shutdown_timeout
        self.last_error = None
        self._seen = OrderedDict()
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._stop = threading.Event()
        self._active = False
        self._closed = False
        self._local_subscriber = None
        self._subscription = None
        self._bridge_thread = None

    def _error(self, error):
        self.last_error = error
        # Do not log untrusted payloads, connection URLs or credentials.
        _LOG.warning("Hub bridge error: %s", type(error).__name__)

    def _remember(self, event_id):
        self._seen[event_id] = None
        self._seen.move_to_end(event_id)
        while len(self._seen) > self.max_seen:
            self._seen.popitem(last=False)

    def _decode(self, data):
        raw = json.loads(data)
        if not isinstance(raw, dict) or not isinstance(raw.get("payload"), dict):
            raise ValueError("Invalid envelope or payload")
        for field in ("event_id", "timestamp", "event_type"):
            if not isinstance(raw.get(field), str) or not raw[field]:
                raise ValueError(f"Invalid {field}")
        for field in ("sender", "recipient"):
            actor = raw.get(field)
            if field == "recipient" and actor is None:
                continue
            if not isinstance(actor, dict) or any(
                not isinstance(actor.get(key), str)
                for key in ActorIdentifier.__dataclass_fields__
            ):
                raise ValueError("Invalid actor")
            if actor["workspace_id"] != self.workspace_id:
                raise ValueError("Cross-workspace envelope")
        envelope = EventEnvelope.from_dict(raw)
        subject = subject_for_event(self.workspace_id, envelope.event_type,
                                    envelope.payload, sender=envelope.sender)
        return envelope, subject

    def attach(self):
        with self._lifecycle_lock:
            if self._active:
                return
            if self._closed:
                raise RuntimeError("Owned transport has been closed")
            self._stop.clear()
            self._local_subscriber = self.broker.subscribe()
            with self._lock:
                self._active = True
            try:
                self._subscription = self.client.subscribe(
                    f"synlynk.{self.workspace_id}.>", self._on_hub_message)
                self._bridge_thread = threading.Thread(
                    target=self._pump_local_to_hub, name="relay-hub", daemon=True)
                self._bridge_thread.start()
            except BaseException:
                with self._lock:
                    self._active = False
                self.broker.unsubscribe(self._local_subscriber)
                if self.owns_client:
                    self._closed = True
                    self.client.close()
                raise

    def detach(self):
        with self._lifecycle_lock:
            if not self._active:
                return
            with self._lock:
                self._active = False
            self._stop.set()
            self.broker.unsubscribe(self._local_subscriber)
            try:
                self.client.unsubscribe(self._subscription)
            except Exception as error:
                self._error(error)
                raise
            finally:
                try:
                    self._bridge_thread.join(self.shutdown_timeout)
                finally:
                    if self.owns_client:
                        self._closed = True
                        self.client.close()
                if self._bridge_thread.is_alive():
                    raise TimeoutError("Hub bridge did not stop")

    stop = detach

    def _pump_local_to_hub(self):
        while not self._stop.is_set():
            try:
                data = self._local_subscriber.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                envelope, subject = self._decode(data)
                with self._lock:
                    if envelope.event_id in self._seen:
                        continue
                    self._remember(envelope.event_id)
                # Never hold the ID lock across client I/O (callbacks may echo).
                self.client.publish(subject, data)
            except Exception as error:
                self._error(error)

    def _on_hub_message(self, subject, payload):
        try:
            envelope, expected = self._decode(payload)
            if subject != expected:
                raise ValueError("Subject does not match envelope routing")
            with self._lock:
                if not self._active or envelope.event_id in self._seen:
                    return
                self._remember(envelope.event_id)
                try:
                    self.broker.publish(envelope)
                except Exception:
                    self._seen.pop(envelope.event_id, None)
                    raise
        except Exception as error:
            self._error(error)


def _import_nats():
    try:
        import nats  # noqa: F401
        return nats
    except ImportError as exc:
        raise RuntimeError(
            "Hub features require the optional 'hub' extra: "
            "pip install 'synlynk[hub]'"
        ) from exc


RETENTION_POLICIES = {
    "job": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "sentinel": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "agent": {"max_msgs": 2_000, "max_age_seconds": 48 * 3600},
    "device": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "doc": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "custom": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
}

_EVENT_SUFFIXES = {
    "review_requested": "job.review_requested",
    "agent_started": "job.agent_started",
    "agent_completed": "job.agent_completed",
    "governs_stage_advanced": "job.governs_stage_advanced",
    "doc_drafted": "doc.drafted",
    "doc_updated": "doc.updated",
    "hub_disconnected": "device.local.hub_disconnected",
    "sync_gap_detected": "device.local.sync_gap_detected",
}


def _subject_segment(value: str, field: str) -> str:
    """Require one literal subject token; never normalize an invalid identity."""
    if not isinstance(value, str) or not value or any(
        char in ".*>" or char.isspace() or not char.isprintable()
        for char in value
    ):
        raise ValueError(f"{field} must be a non-empty literal subject segment")
    return value


def subject_for_event(
    workspace_id: str,
    event_type: str,
    payload: dict,
    sender: ActorIdentifier | Mapping | None = None,
) -> str:
    """Translate an event into a concrete workspace-scoped publish subject.

    Sender identity takes precedence over payload metadata, with missing keys
    falling back to the payload, then 'unknown'. Explicit invalid values fail.
    Plain task_progress remains a job event; runner_progress uses the spec's
    agent.<harness>.progress route. This does not validate EventEnvelope types.
    """
    workspace_id = _subject_segment(workspace_id, "workspace_id")
    event_type = _subject_segment(event_type, "event_type")
    suffix = _EVENT_SUFFIXES.get(event_type, f"custom.{event_type}")
    if event_type in {"task_progress", "runner_progress"}:
        metadata = sender.to_dict() if isinstance(sender, ActorIdentifier) else sender
        metadata = metadata if metadata is not None else {}
        identity = {
            key: _subject_segment(metadata.get(key, payload.get(key, "unknown")), key)
            for key in ("harness", "agent_role")
        }
        if event_type == "runner_progress":
            suffix = f"agent.{identity['harness']}.progress"
        elif any(key in metadata or key in payload for key in identity):
            suffix = f"agent.{identity['harness']}.{identity['agent_role']}"
        else:
            suffix = "job.task_progress"
    elif event_type == "steering_injected":
        device = _subject_segment(payload.get("target_device_id", "unknown"), "target_device_id")
        suffix = f"device.{device}.steering"
    return f"synlynk.{workspace_id}.{suffix}"


def category_for_subject(subject: str) -> str:
    """Return a known category of a concrete subject, or custom if malformed."""
    parts = subject.split(".")
    if len(parts) < 4 or parts[0] != "synlynk" or parts[2] not in RETENTION_POLICIES:
        return "custom"
    try:
        for part in parts:
            _subject_segment(part, "subject")
    except ValueError:
        return "custom"
    return parts[2]


def _private_path(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Secret path must not be a symlink: {path.name}")
    if path.exists():
        path.chmod(0o600)


def _atomic_secret_write(path: Path, content: str) -> None:
    """Publish a complete file, private from creation through replacement."""
    _private_path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass
class DeviceCredential:
    device_id: str
    name: str
    token: str
    publish_subjects: list[str]
    subscribe_subjects: list[str]
    revoked: bool = False


class DeviceCredentialStore:
    """Workspace-bound registry of random per-device bearer secrets.

    NATS uses device_id as user and token as password, with workspace-level
    app permissions. JSON .creds files are NOT NATS JWT credentials; clients
    must use native user/password authentication. Revocation only changes
    bookkeeping and future config output; applying it requires server reload.
    The registry is authoritative; relay_hub_devices is reserved bookkeeping.
    """

    def __init__(self, workspace_id: str, config_dir: str | Path):
        self.workspace_id = _subject_segment(workspace_id, "workspace_id")
        self.config_dir = Path(config_dir)
        if self.config_dir.is_symlink():
            raise ValueError("Credential directory must not be a symlink")
        self.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.config_dir.chmod(0o700)
        self._registry_path = self.config_dir / "devices.json"
        with self._locked():
            if self._registry_path.exists() or self._registry_path.is_symlink():
                self._load_registry()
            else:
                self._save_registry({})

    @contextmanager
    def _locked(self):
        path = self.config_dir / ".devices.lock"
        _private_path(path)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _load_registry(self) -> dict:
        _private_path(self._registry_path)
        registry = json.loads(self._registry_path.read_text(encoding="utf-8"))
        if registry.get("workspace_id") != self.workspace_id:
            raise ValueError("Credential registry workspace mismatch")
        devices = registry["devices"]
        scope = [f"synlynk.{self.workspace_id}.>"]
        for device_id, raw in devices.items():
            if raw["device_id"] != device_id or not re.fullmatch(r"dev-[0-9a-f]{32}", device_id):
                raise ValueError("Credential device identity mismatch")
            if raw["publish_subjects"] != scope or raw["subscribe_subjects"] != scope:
                raise ValueError("Credential scope does not match workspace")
            _private_path(self.config_dir / f"{device_id}.creds")
        return devices

    def _save_registry(self, devices: dict) -> None:
        _atomic_secret_write(self._registry_path, json.dumps({
            "workspace_id": self.workspace_id, "devices": devices,
        }, indent=2))

    def add_device(self, name: str) -> DeviceCredential:
        with self._locked():
            registry = self._load_registry()
            cred = DeviceCredential(
                device_id=f"dev-{uuid.uuid4().hex}", name=name,
                token=secrets.token_hex(32),
                publish_subjects=[f"synlynk.{self.workspace_id}.>"],
                subscribe_subjects=[f"synlynk.{self.workspace_id}.>"],
            )
            path = self.config_dir / f"{cred.device_id}.creds"
            _atomic_secret_write(path, json.dumps(asdict(cred), indent=2))
            registry[cred.device_id] = asdict(cred)
            try:
                self._save_registry(registry)
            except BaseException:
                path.unlink()
                raise
            return cred

    def get_device(self, device_id: str) -> DeviceCredential | None:
        with self._locked():
            raw = self._load_registry().get(device_id)
            return DeviceCredential(**raw) if raw else None

    def revoke_device(self, device_id: str) -> bool:
        with self._locked():
            registry = self._load_registry()
            raw = registry.get(device_id)
            if not raw or raw["revoked"]:
                return False
            raw["revoked"] = True
            # Commit revocation before updating the exported local copy.
            self._save_registry(registry)
            _atomic_secret_write(self.config_dir / f"{device_id}.creds", json.dumps(raw, indent=2))
            return True

    def list_devices(self) -> list[DeviceCredential]:
        with self._locked():
            return [DeviceCredential(**raw) for raw in self._load_registry().values()]

    def render_authorization_block(self) -> str:
        """Render NATS user/password auth; JSON quoting prevents config injection."""
        users = [
            {"user": cred.device_id, "password": cred.token, "permissions": {
                "publish": cred.publish_subjects, "subscribe": cred.subscribe_subjects,
            }}
            for cred in self.list_devices() if not cred.revoked
        ]
        if not users:
            # NATS disables auth for users: []. Keep auth enabled with an
            # unissued random secret and no permissions, even after revoke-all.
            users = [{"user": "__disabled__", "password": secrets.token_hex(32),
                      "permissions": {"publish": [], "subscribe": []}}]
        return "authorization " + json.dumps({"users": users}, indent=2) + "\n"

    def write_authorization_config(self) -> Path:
        """Write a private config snapshot; does not reload a running server."""
        path = self.config_dir / "nats.conf"
        _atomic_secret_write(path, self.render_authorization_block())
        return path
