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
import errno
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import queue
import secrets
import shlex
import stat
import tempfile
import threading
from types import SimpleNamespace
import uuid

from synlynk.events import ActorIdentifier, EventEnvelope


_LOG = logging.getLogger(__name__)

DOC_PREVIEW_MAX_BYTES = 1_000_000
_DOC_EVENTS = {"doc_drafted", "doc_updated"}


def _doc_path_parts(path):
    if (not isinstance(path, str) or "\\" in path
            or any(ord(char) < 32 or ord(char) == 127 for char in path)):
        raise ValueError("Invalid document path")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts) or not any(
        path.startswith(root + "/") for root in
        ("docs/superpowers/specs", "docs/superpowers/plans", "docs/brainstorm")
    ):
        raise ValueError("Document path outside preview roots")
    return parts


def _doc_device(device_id):
    if not isinstance(device_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", device_id):
        raise ValueError("Invalid origin device ID")
    return device_id


def _validate_doc_payload(payload, *, require_origin=True):
    _doc_path_parts(payload.get("path"))
    if require_origin or "origin_device_id" in payload:
        _doc_device(payload.get("origin_device_id"))
    if (not isinstance(payload.get("branch"), str)
            or (payload.get("commit_sha") is not None
                and not isinstance(payload["commit_sha"], str))
            or ("content" in payload and not isinstance(payload["content"], str))):
        raise ValueError("Invalid document metadata/content")


def _fit_doc_content(value, serialize, payload):
    """Drop only content; metadata that cannot fit is an observable error."""
    data = serialize(value).encode("utf-8")
    if len(data) > DOC_PREVIEW_MAX_BYTES:
        payload.pop("content", None)
        data = serialize(value).encode("utf-8")
    if len(data) > DOC_PREVIEW_MAX_BYTES:
        raise ValueError("Document metadata exceeds envelope size limit")
    return data


def build_doc_event_payload(path: str, branch: str, commit_sha: str | None,
                            content: str, *, origin_device_id: str | None = None) -> dict:
    """Build a preview notification. The bridge adds its local origin identity.

    This preliminary payload limit includes JSON escaping. The outbound bridge
    applies the same limit to the actual envelope, including all actor metadata.
    """
    payload = dict(path=path, branch=branch, commit_sha=commit_sha, content=content)
    if origin_device_id is not None:
        payload["origin_device_id"] = origin_device_id
    _validate_doc_payload(payload, require_origin=False)
    _fit_doc_content(payload, json.dumps, payload)
    return payload


def write_doc_preview(base_dir: str, device_id: str, path: str, content: str) -> str:
    """Atomically replace a labeled, read-only copy under a private preview root.

    Walk using directory descriptors and O_NOFOLLOW, including the local base,
    so remote path components and destination symlinks are never followed.
    """
    parts = [_doc_device(device_id), *_doc_path_parts(path)]
    if not isinstance(content, str):
        raise ValueError("Invalid document content")
    base = os.path.abspath(base_dir)
    directories = [*Path(base).parts[1:], *parts[:-1]]
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    temporary = None
    try:
        for name in directories:
            try:
                os.mkdir(name, mode=0o700, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        try:
            destination = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(destination.st_mode):
                raise ValueError("Preview destination must be a regular file")
        name = ".preview-" + secrets.token_hex(16)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        temporary = name
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("<!-- PREVIEW ONLY - synced from another device; not merged. Do not edit. -->\n\n")
            output.write(content)
            output.flush()
            os.fchmod(output.fileno(), 0o444)
            os.fsync(output.fileno())
        os.replace(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory)
        temporary = None
    except OSError as error:
        if error.errno == errno.ENAMETOOLONG:
            raise ValueError("Document path exceeds filesystem limits") from error
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError("Symlink or non-directory in preview path") from error
        raise
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=directory)
        os.close(directory)
    return os.path.join(base, *parts)


class ReplayTracker:
    """One stream's confirmed delivery position (never a cross-stream counter)."""

    def __init__(self, device_id, *, stream=None):
        self.device_id = device_id
        self.stream = stream
        self.last_delivered_seq = None
        if stream is not None:
            from synlynk.relay import _db
            conn = _db()
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS relay_hub_cursors ("
                             "device_id TEXT NOT NULL, stream TEXT NOT NULL, seq INTEGER NOT NULL,"
                             "PRIMARY KEY(device_id, stream))")
                row = conn.execute("SELECT seq FROM relay_hub_cursors WHERE device_id=? AND stream=?",
                                   (device_id, stream)).fetchone()
                conn.commit()
                if row:
                    self.last_delivered_seq = row[0]
            finally:
                conn.close()

    def record_delivered(self, seq):
        seq = max(self.last_delivered_seq or 0, seq)
        if self.stream is not None:
            from synlynk.relay import _db
            conn = _db()
            try:
                conn.execute("INSERT INTO relay_hub_cursors(device_id,stream,seq) VALUES (?,?,?) "
                             "ON CONFLICT(device_id,stream) DO UPDATE SET seq=MAX(seq,excluded.seq)",
                             (self.device_id, self.stream, seq))
                conn.commit()
            finally:
                conn.close()
        self.last_delivered_seq = seq

    def replay(self, consumer):
        pending = sorted(consumer.fetch_since(self.last_delivered_seq or 0))
        if pending:
            self.record_delivered(pending[-1][0])
        return pending

    def detect_sync_gap(self, consumer):
        return (self.last_delivered_seq is not None
                and self.last_delivered_seq + 1 < consumer.earliest_seq)


def _stream_name(workspace_id, category):
    # Hash literal identities to legal, collision-resistant JetStream names.
    digest = hashlib.sha256(workspace_id.encode()).hexdigest()
    return f"synlynk_{digest}_{category}"


def _durable_name(device_id):
    return "device_" + hashlib.sha256(device_id.encode()).hexdigest()


def _inbox_prefix(device_id):
    return "_INBOX." + _durable_name(device_id)


class NatsTransport:
    """Synchronous bridge API backed by an owned nats-py loop and connection.

    Construct outside an asyncio callback. Operations have bounded waits and
    raise on failure; asynchronous NATS errors are logged and in last_error.
    Pass native user/password for DeviceCredentialStore bearer credentials.
    HubAdapter selects durable JetStream subscriptions. Standalone subscribe()
    retains the core NATS interface. Call close() when finished.
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
        self._js = None
        self._durable_tasks = set()
        self.device_id = connect_options.get("user")
        if isinstance(self.device_id, str):
            connect_options["inbox_prefix"] = _inbox_prefix(self.device_id).encode()

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
            if self._js is not None:
                await self._js.publish(subject, data, timeout=self.timeout)
            else:
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

    def subscribe_durable(self, workspace_id, callback, gap_callback):
        """Provision category streams and bind this device's persistent cursors.

        Pull one message at a time with one unacked message allowed, so a local
        write failure cannot be skipped by acknowledging a later delivery.
        Unsubscribe only releases local subscriptions; durable state survives.
        """
        from nats.js.api import AckPolicy, ConsumerConfig, StreamConfig
        from nats.js.errors import NotFoundError

        workspace_id = _subject_segment(workspace_id, "workspace_id")
        if not isinstance(self.device_id, str) or not self.device_id:
            raise ValueError("Durable hub transport requires a stable device user")

        async def setup():
            self._js = self._client.jetstream(timeout=self.timeout)
            subscriptions = []
            tasks = []
            try:
                for category, policy in RETENTION_POLICIES.items():
                    stream = _stream_name(workspace_id, category)
                    subject = f"synlynk.{workspace_id}.{category}.>"
                    try:
                        info = await self._js.stream_info(stream)
                    except NotFoundError:
                        info = await self._js.add_stream(config=StreamConfig(
                            name=stream, subjects=[subject], max_msgs=policy["max_msgs"],
                            max_age=policy["max_age_seconds"]))
                    if info.config.subjects != [subject]:
                        raise ValueError("Unexpected hub stream subjects")
                    durable = _durable_name(self.device_id)
                    tracker = ReplayTracker(self.device_id, stream=stream)
                    try:
                        consumer = await self._js.consumer_info(stream, durable)
                        if tracker.last_delivered_seq is None:
                            tracker.record_delivered(consumer.ack_floor.stream_seq)
                        if (consumer.config.ack_policy != AckPolicy.EXPLICIT
                                or consumer.config.max_ack_pending != 1
                                or consumer.config.filter_subject
                                or consumer.config.filter_subjects
                                or consumer.config.deliver_subject):
                            raise ValueError("Unexpected hub consumer configuration")
                    except NotFoundError:
                        await self._js.add_consumer(stream, config=ConsumerConfig(
                            durable_name=durable, ack_policy=AckPolicy.EXPLICIT,
                            max_ack_pending=1, ack_wait=30))
                        # First connect starts at currently retained history.
                        if tracker.last_delivered_seq is None:
                            tracker.record_delivered(max(0, info.state.first_seq - 1))
                    sub = await self._js.pull_subscribe_bind(stream=stream, durable=durable)
                    subscriptions.append(sub)
                    tasks.append(asyncio.create_task(self._consume(
                        sub, stream, tracker, callback, gap_callback)))
                self._durable_tasks.update(tasks)
                return subscriptions, tasks
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                for sub in subscriptions:
                    await sub.unsubscribe()
                raise

        return self._call(setup())

    async def _consume(self, sub, stream, tracker, callback, gap_callback):
        from nats.errors import TimeoutError as NatsTimeout

        reported_earliest = None

        async def check_gap():
            nonlocal reported_earliest
            info = await self._js.stream_info(stream)
            earliest = info.state.first_seq
            if (tracker.detect_sync_gap(SimpleNamespace(earliest_seq=earliest))
                    and reported_earliest != earliest):
                gap_callback(stream, tracker.last_delivered_seq, earliest)
                reported_earliest = earliest

        while True:
            try:
                await check_gap()
                messages = await sub.fetch(batch=1, timeout=1)
                for message in messages:
                    if message.metadata.sequence.stream > (tracker.last_delivered_seq or 0) + 1:
                        # Retention can advance while a pull request is waiting.
                        await check_gap()
                    disposition = callback(message.subject, message.data)
                    if disposition == "ack":
                        tracker.record_delivered(message.metadata.sequence.stream)
                        await message.ack_sync(timeout=self.timeout)
                    elif disposition == "term":
                        tracker.record_delivered(message.metadata.sequence.stream)
                        await message.term()
                        await self._client.flush(timeout=self.timeout)
                    else:
                        await message.nak(delay=1)
                        continue
            except NatsTimeout:
                continue
            except Exception as error:
                self.last_error = error
                _LOG.warning("JetStream delivery error: %s", type(error).__name__)
                await asyncio.sleep(1)

    def unsubscribe(self, subscription):
        async def unsubscribe():
            if isinstance(subscription, tuple):
                subscriptions, tasks = subscription
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                self._durable_tasks.difference_update(tasks)
                for sub in subscriptions:
                    await sub.unsubscribe()
            else:
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
                async def shutdown():
                    for task in self._durable_tasks:
                        task.cancel()
                    await asyncio.gather(*self._durable_tasks, return_exceptions=True)
                    self._durable_tasks.clear()
                    await self._client.close()
                self._call(shutdown())
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
    Replay dedupe checks persisted relay events before broker delivery.
    Transport failures are observable via last_error and logging, not retried.
    """

    def __init__(self, broker, client, workspace_id, *, owns_client=False,
                 max_seen=10_000, shutdown_timeout=10.0, subscriptions=None,
                 preview_dir=None):
        self.workspace_id = _subject_segment(workspace_id, "workspace_id")
        self.preview_dir = Path(preview_dir or ".synlynk/relay/previews").absolute()
        self.subscriptions = subscriptions
        if subscriptions is not None:
            for pattern in subscriptions:
                _validate_pattern(pattern)
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
                if isinstance(self.client, NatsTransport):
                    self._subscription = self.client.subscribe_durable(
                        self.workspace_id, self._on_hub_message, self._on_sync_gap)
                else:
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
                if envelope.event_type == "sync_gap_detected":
                    continue
                if envelope.event_type in _DOC_EVENTS:
                    raw = envelope.to_dict()
                    origin = getattr(self.client, "device_id", None)
                    if origin is not None:
                        raw["payload"]["origin_device_id"] = origin
                    _validate_doc_payload(raw["payload"])
                    data = _fit_doc_content(raw, lambda value: json.dumps(value, sort_keys=True),
                                            raw["payload"])
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
            if envelope.event_type in _DOC_EVENTS:
                if len(payload.encode("utf-8") if isinstance(payload, str) else payload) > DOC_PREVIEW_MAX_BYTES:
                    raise ValueError("Document envelope exceeds size limit")
                _validate_doc_payload(envelope.payload)
            suffix = subject[len(f"synlynk.{self.workspace_id}."):]
            if self.subscriptions is not None and not any(
                _matches_pattern(pattern, suffix) for pattern in self.subscriptions
            ):
                return "ack"
        except Exception as error:
            self._error(error)
            return "term"  # Poison input: observable, no redelivery/feedback loop.
        try:
            with self._lock:
                if not self._active:
                    return "retry"
                if envelope.event_id in self._seen:
                    return "ack"
                from synlynk.relay import _db
                conn = _db()
                try:
                    persisted = conn.execute(
                        "SELECT 1 FROM relay_events WHERE event_id=?", (envelope.event_id,)
                    ).fetchone()
                finally:
                    conn.close()
                self._remember(envelope.event_id)
                if persisted:
                    return "ack"
                try:
                    if envelope.event_type in _DOC_EVENTS and "content" in envelope.payload:
                        doc = envelope.payload
                        write_doc_preview(str(self.preview_dir), doc["origin_device_id"],
                                          doc["path"], doc["content"])
                    self.broker.publish(envelope)
                except Exception:
                    self._seen.pop(envelope.event_id, None)
                    raise
                return "ack"
        except Exception as error:
            self._error(error)
            if envelope.event_type in _DOC_EVENTS and isinstance(error, ValueError):
                return "term"
            return "retry"

    def _on_sync_gap(self, stream, last_seq, earliest_seq):
        event = EventEnvelope.create(
            ActorIdentifier(self.workspace_id, "local", "relay", "nats", ""),
            "sync_gap_detected", {"stream": stream, "last_delivered_seq": last_seq,
                                  "earliest_seq": earliest_seq})
        # The outbound pump excludes these markers even after its ID cache evicts.
        self.broker.publish(event)


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
                "publish": cred.publish_subjects + self._jetstream_permissions(cred.device_id),
                "subscribe": cred.subscribe_subjects + [_inbox_prefix(cred.device_id) + ".>"],
            }}
            for cred in self.list_devices() if not cred.revoked
        ]
        if not users:
            # NATS disables auth for users: []. Keep auth enabled with an
            # unissued random secret and no permissions, even after revoke-all.
            users = [{"user": "__disabled__", "password": secrets.token_hex(32),
                      "permissions": {"publish": [], "subscribe": []}}]
        return "authorization " + json.dumps({"users": users}, indent=2) + "\n"

    def _jetstream_permissions(self, device_id):
        durable = _durable_name(device_id)
        subjects = []
        for category in RETENTION_POLICIES:
            stream = _stream_name(self.workspace_id, category)
            subjects.extend([
                f"$JS.API.STREAM.INFO.{stream}",
                f"$JS.API.STREAM.CREATE.{stream}",
                f"$JS.API.CONSUMER.INFO.{stream}.{durable}",
                f"$JS.API.CONSUMER.DURABLE.CREATE.{stream}.{durable}",
                f"$JS.API.CONSUMER.MSG.NEXT.{stream}.{durable}",
                f"$JS.ACK.{stream}.{durable}.>",
            ])
        return subjects

    def write_authorization_config(self) -> Path:
        """Write a private config snapshot; does not reload a running server."""
        path = self.config_dir / "nats.conf"
        _atomic_secret_write(path, self.render_authorization_block())
        return path


def _default_config_dir():
    return Path.home() / ".synlynk" / "relay"


def _config_dir(args):
    return Path(getattr(args, "config_dir", None) or _default_config_dir()).absolute()


def _read_hub(config_dir):
    path = config_dir / "hub.json"
    _private_path(path)
    return json.loads(path.read_text())


def _write_server_config(store, config):
    content = ("listen: " + json.dumps(config["listen"]) + "\njetstream "
               + json.dumps({"store_dir": str(store.config_dir / "jetstream")}) + "\n"
               + store.render_authorization_block())
    path = store.config_dir / "nats.conf"
    _atomic_secret_write(path, content)
    return path


def _refresh_auth(store):
    if (store.config_dir / "hub.json").exists():
        config = _read_hub(store.config_dir)
        if config["mode"] == "managed":
            raise ValueError("Managed device registration is not implemented")
        path = _write_server_config(store, config)
    else:
        path = store.write_authorization_config()
    print(f"Authorization written to {path}. Reload the running nats-server to apply it; "
          "live revocation is not confirmed. Use nats-server --signal reload=<server-pid>.")


def _device_store(args):
    directory = _config_dir(args)
    if (directory / "hub.json").exists():
        config = _read_hub(directory)
        if config["workspace_id"] != args.workspace_id:
            raise ValueError("Hub workspace mismatch")
        if config["mode"] == "managed":
            raise ValueError("Managed device registration is not implemented")
    return DeviceCredentialStore(args.workspace_id, directory)


def cmd_relay_device_add(args):
    store = _device_store(args)
    cred = store.add_device(args.name)
    _refresh_auth(store)
    print(f"Added device '{cred.name}' ({cred.device_id})")
    print(f"Credential written to {store.config_dir / (cred.device_id + '.creds')}; keep this file secret.")


def cmd_relay_device_revoke(args):
    store = _device_store(args)
    existing = store.get_device(args.device_id)
    if existing is None:
        print(f"Device {args.device_id} not found.")
        return
    changed = store.revoke_device(args.device_id)
    _refresh_auth(store)
    print(f"Device {args.device_id} {'revoked' if changed else 'already revoked'} in local configuration.")


def cmd_relay_hub_init(args):
    store = _device_store(args)
    config = {"workspace_id": args.workspace_id, "mode": "self_hosted",
              "url": args.url, "listen": args.listen}
    _atomic_secret_write(store.config_dir / "hub.json", json.dumps(config, indent=2))
    path = _write_server_config(store, config)
    print(f"Start the hub: nats-server -c {shlex.quote(str(path))}")
    common = f"--workspace-id {shlex.quote(args.workspace_id)} --config-dir {shlex.quote(str(store.config_dir))}"
    print(f"Mint credentials: synlynk relay device add <name> {common}")
    print(f"Bridge this device: synlynk relay start --hub --device-id <device-id> "
          f"--config-dir {shlex.quote(str(store.config_dir))}")


def cmd_relay_hub_connect(args):
    directory = _config_dir(args)
    # Validate the workspace and reuse the existing private-directory contract.
    DeviceCredentialStore(args.workspace_id, directory)
    if (directory / "hub.json").exists():
        raise ValueError("Hub already configured; use a separate config directory")
    _atomic_secret_write(directory / "hub.json", json.dumps({
        "workspace_id": args.workspace_id, "mode": "managed", "token": args.token,
        "url": args.url,
    }, indent=2))
    print("Managed configuration saved locally. Managed service connection and device "
          "registration are not implemented; no service was contacted.")


def _validate_pattern(pattern):
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("Subscription must be a relative subject pattern, e.g. job.>")
    tokens = pattern.split(".")
    for index, token in enumerate(tokens):
        if token == "*" or (token == ">" and index == len(tokens) - 1):
            continue
        _subject_segment(token, "subscription pattern")


def _matches_pattern(pattern, subject):
    tokens, values = pattern.split("."), subject.split(".")
    for index, token in enumerate(tokens):
        if index >= len(values):
            return False
        if token == ">":
            return True
        if token != "*" and token != values[index]:
            return False
    return len(tokens) == len(values)


def _subscription_path():
    return Path.cwd() / ".synlynk" / "relay-subscriptions.json"


def _read_subscriptions():
    path = _subscription_path()
    if not path.exists():
        return None
    patterns = json.loads(path.read_text())
    if not isinstance(patterns, list):
        raise ValueError("Subscriptions must be a list")
    for pattern in patterns:
        _validate_pattern(pattern)
    return patterns


def _update_subscription(args, add):
    _validate_pattern(args.pattern)
    path = _subscription_path()
    patterns = _read_subscriptions() or []
    if add and args.pattern not in patterns:
        patterns.append(args.pattern)
    if not add and args.pattern in patterns:
        patterns.remove(args.pattern)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_secret_write(path, json.dumps(patterns, indent=2))
    print(f"{'Subscribed to' if add else 'Unsubscribed from'} {args.pattern}. "
          "Restart the hub bridge to apply; excluded events are acknowledged and skipped.")


def cmd_relay_subscribe(args):
    _update_subscription(args, True)


def cmd_relay_unsubscribe(args):
    _update_subscription(args, False)


def load_device_credential(path, workspace_id):
    """Read one exported secret without loading the hub administrator registry."""
    workspace_id = _subject_segment(workspace_id, "workspace_id")
    path = Path(path)
    _private_path(path)
    raw = json.loads(path.read_text())
    scope = [f"synlynk.{workspace_id}.>"]
    if (not isinstance(raw, dict)
            or not isinstance(raw.get("device_id"), str)
            or not re.fullmatch(r"dev-[0-9a-f]{32}", raw["device_id"])
            or not isinstance(raw.get("token"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", raw["token"])
            or raw.get("publish_subjects") != scope
            or raw.get("subscribe_subjects") != scope
            or raw.get("revoked") is not False):
        raise ValueError("Invalid, revoked, or incorrectly scoped device credential")
    return DeviceCredential(**raw)


def run_hub_relay(args):
    """Attach to the exact HTTP server broker; all resources are owned here."""
    from synlynk.relay import RelayServer
    if getattr(args, "credential_file", None):
        if not args.workspace_id or not args.hub_url:
            raise ValueError("--credential-file requires --workspace-id and --hub-url")
        if args.device_id or args.config_dir:
            raise ValueError("Use --credential-file independently of --device-id and --config-dir")
        config = {"workspace_id": args.workspace_id, "url": args.hub_url}
        cred = load_device_credential(args.credential_file, args.workspace_id)
    else:
        if getattr(args, "workspace_id", None):
            raise ValueError("--workspace-id requires --credential-file")
        directory = _config_dir(args)
        config = _read_hub(directory)
        if config["mode"] != "self_hosted":
            raise ValueError("Managed service connection is not implemented")
        if not args.device_id:
            raise ValueError("--device-id is required with --hub")
        store = DeviceCredentialStore(config["workspace_id"], directory)
        cred = store.get_device(args.device_id)
        if cred is None or cred.revoked:
            raise ValueError("Device credential missing or revoked")
    subscriptions = _read_subscriptions()
    server = RelayServer(port=args.port)
    adapter = None
    try:
        client = NatsTransport([args.hub_url or config["url"]], user=cred.device_id,
                               password=cred.token)
        adapter = HubAdapter(server.broker, client, config["workspace_id"],
                             owns_client=True, subscriptions=subscriptions)
        adapter.attach()
        server.start(background=False)
    finally:
        try:
            if adapter is not None:
                adapter.detach()
        finally:
            # serve_forever has returned (or never started); shutdown would deadlock.
            server.httpd.server_close()
