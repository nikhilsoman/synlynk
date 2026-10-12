# Personal Hosted Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in NATS-backed "hub" layer (self-hosted or synlynk.com-managed) that bridges each device's existing local `RelayBroker` so job/sentinel/agent/doc events replay reliably across a user's devices, without touching the local broker's existing behavior for anyone who doesn't opt in.

**Architecture:** A new `synlynk/relay_hub.py` module adds a `HubAdapter` that dials outbound to a NATS server, publishing local broker events onto workspace-scoped subjects and re-injecting hub messages into the local broker's subscriber queue. Device credentials, subject routing, and JetStream-backed durable replay are layered on top of the existing `RelayBroker`/`RelayServer` in `synlynk/relay.py`, which this plan does not modify in its core publish/subscribe behavior.

**Tech Stack:** Python 3.10+ stdlib (existing), `nats-py` as a new **optional** dependency (lazy-imported, see Task 1), SQLite (`state.db`, existing `_get_db()`), NATS JetStream for durable per-subject-category streams.

**Source spec:** `docs/superpowers/specs/2026-10-12-personal-hosted-relay-design.md` (gh:#2201)

**GOVERNS note:** `goal-f4ce526a` ("Personal-use hosted relay: opt-in NATS hub bridging local relay brokers across a user's devices (gh:#2201)") created outside the dev-preview GOVERNS tree, with 10 stories linked (primary) and marked ready, one per task below — `story-52549f07` (Task 1), `story-085360d0` (Task 2), `story-76b7162d` (Task 3), `story-0c7ecea4` (Task 4), `story-2263ec9a` (Task 5), `story-29cc4aad` (Task 6), `story-43a01b32` (Task 7), `story-f4824a3e` (Task 8), `story-dbf68f01` (Task 9), `story-f1639150` (Task 10). None of these reuse `story-e5cc49f0` ("T4: Relay wire protocol"), which remains unrelated prior work on the existing local relay.

---

## Decision Flagged for Review: Credential Mechanism

The committed spec says each device holds "a NATS nkey keypair + JWT." Implementing real decentralized nkey/JWT auth requires either the `nsc` CLI toolchain or a running JWT account-resolver service — neither of which this plan can stand up without materially expanding scope (and `nsc` is not a Python-importable dependency, so it can't be lazy-imported the way `nats-py` can).

**This plan implements device credentials as per-device bearer tokens scoped via NATS's built-in `authorization { users: [...] }` permission blocks** (`publish`/`subscribe` allow-lists per user, keyed by a random token) instead. This satisfies every behavioral requirement in the spec — per-device credential, immediately and individually revocable, scoped to that device's own subjects plus shared workspace subjects — without requiring `nsc`. Real nkey/JWT minting is flagged as a follow-up hardening task before a multi-tenant *managed* hub ships (self-hosted single-workspace hubs have no multi-tenancy pressure forcing the JWT model yet). Task 4 implements this and documents the deviation inline in the module docstring.

---

## File Structure

- **Create `synlynk/relay_hub.py`** — `HubConfig`, device credential store, subject-routing functions, `HubAdapter` (the bridge), JetStream stream/consumer setup, sync-gap detection. One file because these pieces are small and only make sense together; split later if it grows unwieldy (current estimate: ~350-450 lines, comparable to `relay.py`'s 401).
- **Modify `synlynk/events.py`** — extend `RELAY_EVENT_TYPES` with 4 new event types needed by the hub (hub_disconnected, sync_gap_detected, doc_drafted, doc_updated).
- **Modify `synlynk/db.py`** — add `relay_hub_devices` table (local bookkeeping of minted device credentials) near the existing `relay_events`/`relay_mailbox` tables (~line 1038).
- **Modify `synlynk/cli.py`** — extend the existing `relay` subparser (~line 1284) with `hub init`, `hub connect`, `device add`, `device revoke`, `subscribe`, `unsubscribe`.
- **Modify `pyproject.toml`** — add `[project.optional-dependencies] hub = ["nats-py>=2.6.0"]`.
- **Create `tests/test_relay_hub.py`** — unit tests for subject routing, credential store, and `HubAdapter` bridge logic against a fake NATS client.
- **Create `tests/test_relay_hub_integration.py`** — integration test against a real embedded `nats-server`, skipped if the `nats-server` binary isn't on `PATH`.

---

### Task 1: Optional dependency scaffolding + lazy import guard

**Files:**
- Modify: `pyproject.toml`
- Create: `synlynk/relay_hub.py` (stub only, this task)
- Test: `tests/test_relay_hub.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py
import subprocess
import sys


def test_core_cli_import_does_not_require_nats():
    """synlynk's core CLI must import cleanly with no nats-py installed —
    hub features are optional, the base CLI is stdlib-only (CLAUDE.md constraint)."""
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk; import synlynk.cli"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_relay_hub_module_importable_without_nats_installed():
    """Importing synlynk.relay_hub itself must not require nats-py at import time —
    only calling HubAdapter.connect() should need it."""
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk.relay_hub"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.relay_hub'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py
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


def _import_nats():
    try:
        import nats  # noqa: F401
        return nats
    except ImportError as exc:
        raise RuntimeError(
            "Hub features require the optional 'hub' extra: "
            "pip install 'synlynk[hub]'"
        ) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Add the optional dependency to pyproject.toml**

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-xdist>=3.0.0",
]
hub = [
    "nats-py>=2.6.0",
]
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/relay_hub.py pyproject.toml tests/test_relay_hub.py
git commit -m "feat(relay): scaffold optional hub module with lazy nats-py import"
```

---

### Task 2: Extend relay event-type whitelist

**Files:**
- Modify: `synlynk/events.py:19-27`
- Test: `tests/test_relay_hub.py`

`EventEnvelope.__post_init__` (synlynk/events.py:62-64) rejects any `event_type` not in `RELAY_EVENT_TYPES`. The hub needs 4 new types: `hub_disconnected` (adapter→local, error handling case 1 from the spec), `sync_gap_detected` (error handling case 3), `doc_drafted`, `doc_updated` (the doc preview channel).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add to existing file)
from synlynk.events import ActorIdentifier, EventEnvelope


def _actor(**overrides):
    base = {"workspace_id": "ws", "member_id": "m", "agent_role": "dev",
            "harness": "claude", "job_id": "j1"}
    base.update(overrides)
    return ActorIdentifier(**base)


def test_hub_event_types_are_accepted_by_envelope():
    for event_type in ("hub_disconnected", "sync_gap_detected", "doc_drafted", "doc_updated"):
        envelope = EventEnvelope.create(_actor(), event_type, {})
        assert envelope.event_type == event_type
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py::test_hub_event_types_are_accepted_by_envelope -v`
Expected: FAIL with `ValueError: unknown relay event type: hub_disconnected`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/events.py:19-27 — replace the existing tuple
RELAY_EVENT_TYPES = (
    "agent_started",
    "task_progress",
    "artifact_published",
    "review_requested",
    "steering_injected",
    "agent_completed",
    "goal_realigned",
    "governs_stage_advanced",
    "hub_disconnected",
    "sync_gap_detected",
    "doc_drafted",
    "doc_updated",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add synlynk/events.py tests/test_relay_hub.py
git commit -m "feat(relay): add hub_disconnected/sync_gap_detected/doc_drafted/doc_updated event types"
```

---

### Task 3: Subject-routing layer (pure functions, no NATS needed)

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

Maps the existing RPC-method vocabulary and event types onto `synlynk.<workspace_id>.<category>...` subject strings per the spec's taxonomy table, without touching `RelayBroker.rpc()` itself (this stays a pure translation layer the adapter calls).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
from synlynk.relay_hub import subject_for_event, RETENTION_POLICIES


def test_subject_for_job_event():
    assert subject_for_event("ws1", "review_requested", {}) == "synlynk.ws1.job.review_requested"


def test_subject_for_runner_progress_includes_harness_and_role():
    payload = {"harness": "codex", "agent_role": "dev"}
    assert subject_for_event("ws1", "task_progress", payload) == "synlynk.ws1.agent.codex.dev"


def test_subject_for_steering_targets_device():
    payload = {"target_device_id": "dev-42"}
    assert subject_for_event("ws1", "steering_injected", payload) == "synlynk.ws1.device.dev-42.steering"


def test_subject_for_doc_events():
    assert subject_for_event("ws1", "doc_drafted", {}) == "synlynk.ws1.doc.drafted"
    assert subject_for_event("ws1", "doc_updated", {}) == "synlynk.ws1.doc.updated"


def test_subject_for_unmapped_event_falls_back_to_custom():
    assert subject_for_event("ws1", "goal_realigned", {}) == "synlynk.ws1.custom.goal_realigned"


def test_retention_policies_cover_every_category():
    assert RETENTION_POLICIES["job"] == {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600}
    assert RETENTION_POLICIES["sentinel"] == {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600}
    assert RETENTION_POLICIES["agent"] == {"max_msgs": 2_000, "max_age_seconds": 48 * 3600}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'subject_for_event'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add below _import_nats()

RETENTION_POLICIES = {
    "job": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "sentinel": {"max_msgs": 50_000, "max_age_seconds": 365 * 24 * 3600},
    "agent": {"max_msgs": 2_000, "max_age_seconds": 48 * 3600},
    "device": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "doc": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
    "custom": {"max_msgs": 10_000, "max_age_seconds": 30 * 24 * 3600},
}

# event_type -> subject-building function. Each function returns the
# category-specific suffix (everything after "synlynk.<workspace_id>.").
_EVENT_TYPE_SUFFIX_BUILDERS = {
    "review_requested": lambda payload: "job.review_requested",
    "agent_started": lambda payload: "job.agent_started",
    "agent_completed": lambda payload: "job.agent_completed",
    "governs_stage_advanced": lambda payload: "job.governs_stage_advanced",
    "task_progress": lambda payload: (
        f"agent.{payload.get('harness', 'unknown')}.{payload.get('agent_role', 'unknown')}"
        if payload.get("harness") or payload.get("agent_role")
        else "job.task_progress"
    ),
    "steering_injected": lambda payload: (
        f"device.{payload['target_device_id']}.steering"
        if payload.get("target_device_id")
        else "device.unknown.steering"
    ),
    "doc_drafted": lambda payload: "doc.drafted",
    "doc_updated": lambda payload: "doc.updated",
    "hub_disconnected": lambda payload: "device.local.hub_disconnected",
    "sync_gap_detected": lambda payload: "device.local.sync_gap_detected",
}


def subject_for_event(workspace_id: str, event_type: str, payload: dict) -> str:
    """Map an event_type + payload onto its NATS subject per the taxonomy."""
    builder = _EVENT_TYPE_SUFFIX_BUILDERS.get(event_type)
    suffix = builder(payload) if builder else f"custom.{event_type}"
    return f"synlynk.{workspace_id}.{suffix}"


def category_for_subject(subject: str) -> str:
    """Extract the top-level category (job/agent/sentinel/device/doc/custom) from a subject."""
    parts = subject.split(".")
    return parts[2] if len(parts) > 2 else "custom"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add synlynk/relay_hub.py tests/test_relay_hub.py
git commit -m "feat(relay): add subject-routing layer mapping event types to NATS subjects"
```

---

### Task 4: Device credential store (bearer-token + permission scoping)

**Files:**
- Modify: `synlynk/db.py` (new table near line 1038)
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
import tempfile
import os
from synlynk.relay_hub import DeviceCredentialStore


def test_add_device_mints_token_and_scoped_permissions():
    with tempfile.TemporaryDirectory() as tmp:
        store = DeviceCredentialStore(workspace_id="ws1", config_dir=tmp)
        cred = store.add_device("laptop")
        assert cred.device_id
        assert len(cred.token) >= 32
        assert cred.publish_subjects == ["synlynk.ws1.>"]
        assert cred.subscribe_subjects == ["synlynk.ws1.>"]
        assert cred.revoked is False


def test_revoke_device_marks_revoked_and_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        store = DeviceCredentialStore(workspace_id="ws1", config_dir=tmp)
        cred = store.add_device("laptop")
        assert store.revoke_device(cred.device_id) is True
        assert store.revoke_device(cred.device_id) is False  # already revoked
        reloaded = store.get_device(cred.device_id)
        assert reloaded.revoked is True


def test_credential_file_written_to_config_dir():
    with tempfile.TemporaryDirectory() as tmp:
        store = DeviceCredentialStore(workspace_id="ws1", config_dir=tmp)
        cred = store.add_device("laptop")
        creds_path = os.path.join(tmp, f"{cred.device_id}.creds")
        assert os.path.exists(creds_path)


def test_authorization_block_excludes_revoked_devices():
    with tempfile.TemporaryDirectory() as tmp:
        store = DeviceCredentialStore(workspace_id="ws1", config_dir=tmp)
        active = store.add_device("laptop")
        revoked = store.add_device("old-vps")
        store.revoke_device(revoked.device_id)
        block = store.render_authorization_block()
        assert active.token in block
        assert revoked.token not in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'DeviceCredentialStore'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add

import json
import os
import secrets
import uuid
from dataclasses import dataclass, asdict


@dataclass
class DeviceCredential:
    device_id: str
    name: str
    token: str
    publish_subjects: list[str]
    subscribe_subjects: list[str]
    revoked: bool = False


class DeviceCredentialStore:
    """Per-device bearer-token credentials, scoped via NATS authorization
    permission blocks. See module docstring for why this isn't nkey/JWT."""

    def __init__(self, workspace_id: str, config_dir: str):
        self.workspace_id = workspace_id
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
        self._registry_path = os.path.join(config_dir, "devices.json")

    def _load_registry(self) -> dict:
        if not os.path.exists(self._registry_path):
            return {}
        with open(self._registry_path) as f:
            return json.load(f)

    def _save_registry(self, registry: dict) -> None:
        with open(self._registry_path, "w") as f:
            json.dump(registry, f, indent=2)

    def add_device(self, name: str) -> DeviceCredential:
        device_id = f"dev-{uuid.uuid4().hex[:8]}"
        cred = DeviceCredential(
            device_id=device_id,
            name=name,
            token=secrets.token_hex(32),
            publish_subjects=[f"synlynk.{self.workspace_id}.>"],
            subscribe_subjects=[f"synlynk.{self.workspace_id}.>"],
        )
        registry = self._load_registry()
        registry[device_id] = asdict(cred)
        self._save_registry(registry)
        creds_path = os.path.join(self.config_dir, f"{device_id}.creds")
        with open(creds_path, "w") as f:
            json.dump(asdict(cred), f, indent=2)
        os.chmod(creds_path, 0o600)
        return cred

    def get_device(self, device_id: str) -> DeviceCredential | None:
        registry = self._load_registry()
        raw = registry.get(device_id)
        return DeviceCredential(**raw) if raw else None

    def revoke_device(self, device_id: str) -> bool:
        registry = self._load_registry()
        raw = registry.get(device_id)
        if not raw or raw.get("revoked"):
            return False
        raw["revoked"] = True
        registry[device_id] = raw
        self._save_registry(registry)
        return True

    def list_devices(self) -> list[DeviceCredential]:
        return [DeviceCredential(**raw) for raw in self._load_registry().values()]

    def render_authorization_block(self) -> str:
        """Render a NATS `authorization { users: [...] }` config block, one
        entry per non-revoked device, scoped to that device's subjects."""
        lines = ["authorization {", "  users: ["]
        for cred in self.list_devices():
            if cred.revoked:
                continue
            pub = ", ".join(f'"{s}"' for s in cred.publish_subjects)
            sub = ", ".join(f'"{s}"' for s in cred.subscribe_subjects)
            lines.append(
                f'    {{token: "{cred.token}", '
                f"permissions: {{publish: [{pub}], subscribe: [{sub}]}}}},"
            )
        lines.append("  ]")
        lines.append("}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Add local bookkeeping table to state.db**

```python
# synlynk/db.py — insert after the relay_mailbox index (after line 1048, before "CREATE TABLE IF NOT EXISTS backlog_items")
            CREATE TABLE IF NOT EXISTS relay_hub_devices (
                device_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_relay_hub_devices_workspace
                ON relay_hub_devices(workspace_id);
```

This table is a queryable mirror of the JSON registry (for `synlynk status`/future Vizor display) — `DeviceCredentialStore` remains the source of truth for the actual token/permissions since that's what the hub's config file is rendered from; a follow-up task (not in this plan) can sync writes into this table if a CLI surface needs it. No test added for this table in this task since nothing reads/writes it yet — Task 7 wires `synlynk relay device add/revoke` through `DeviceCredentialStore`, not this table directly.

- [ ] **Step 6: Commit**

```bash
git add synlynk/relay_hub.py synlynk/db.py tests/test_relay_hub.py
git commit -m "feat(relay): add per-device bearer-token credential store with revocation"
```

---

### Task 5: HubAdapter bridge (local broker <-> NATS, fake-client unit tests)

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

The bridge needs two directions: (a) local `RelayBroker.publish()` events get forwarded to the hub subject, (b) hub messages addressed to this workspace get injected into the local broker's subscriber queue via `RelayBroker.publish()` itself (reusing its existing `event_id` + `INSERT OR IGNORE` idempotency, per the spec). Both directions are tested here against a fake NATS client — no real `nats-server` needed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
from synlynk.relay import RelayBroker
from synlynk.relay_hub import HubAdapter


class FakeNatsClient:
    """Minimal stand-in for nats-py's async client, sync for test simplicity."""

    def __init__(self):
        self.published = []
        self._subscribers = {}

    def publish(self, subject, payload):
        self.published.append((subject, payload))

    def subscribe(self, subject, callback):
        self._subscribers[subject] = callback

    def deliver(self, subject, payload):
        """Test helper: simulate the hub pushing a message to this client."""
        callback = self._subscribers.get(subject)
        if callback:
            callback(subject, payload)


def test_adapter_forwards_local_publish_to_hub():
    broker = RelayBroker()
    fake_client = FakeNatsClient()
    adapter = HubAdapter(broker, fake_client, workspace_id="ws1")
    adapter.attach()

    envelope = EventEnvelope.create(_actor(), "review_requested", {"pr_url": "https://x"})
    broker.publish(envelope)

    assert len(fake_client.published) == 1
    subject, payload = fake_client.published[0]
    assert subject == "synlynk.ws1.job.review_requested"
    assert json.loads(payload)["event_id"] == envelope.event_id


def test_adapter_injects_hub_message_into_local_broker():
    broker = RelayBroker()
    fake_client = FakeNatsClient()
    adapter = HubAdapter(broker, fake_client, workspace_id="ws1")
    adapter.attach()

    subscriber = broker.subscribe()
    envelope = EventEnvelope.create(_actor(), "review_requested", {"pr_url": "https://y"})
    fake_client.deliver("synlynk.ws1.job.review_requested", envelope.to_json())

    delivered = subscriber.get(timeout=1)
    assert json.loads(delivered)["event_id"] == envelope.event_id


def test_adapter_does_not_reforward_messages_it_just_injected():
    """Prevents an echo loop: a message injected from the hub must not be
    immediately republished back to the hub."""
    broker = RelayBroker()
    fake_client = FakeNatsClient()
    adapter = HubAdapter(broker, fake_client, workspace_id="ws1")
    adapter.attach()

    envelope = EventEnvelope.create(_actor(), "review_requested", {})
    fake_client.deliver("synlynk.ws1.job.review_requested", envelope.to_json())

    assert len(fake_client.published) == 0
```

Add `import json` to the top of `tests/test_relay_hub.py` alongside the existing imports (needed for `json.loads` above).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'HubAdapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add

class HubAdapter:
    """Bridges a local RelayBroker to a NATS hub connection.

    `client` must expose `publish(subject, payload)` and
    `subscribe(subject, callback)` where callback is `(subject, payload) -> None`.
    Real usage passes a `nats.aio.client.Client`; tests pass a fake.
    """

    def __init__(self, broker, client, workspace_id: str):
        self.broker = broker
        self.client = client
        self.workspace_id = workspace_id
        self._injected_event_ids: set[str] = set()
        self._local_subscriber = None

    def attach(self) -> None:
        """Start bridging in both directions."""
        self._local_subscriber = self.broker.subscribe()
        self._bridge_thread = threading.Thread(target=self._pump_local_to_hub, daemon=True)
        self._bridge_thread.start()
        self.client.subscribe(f"synlynk.{self.workspace_id}.>", self._on_hub_message)

    def _pump_local_to_hub(self) -> None:
        while True:
            try:
                data = self._local_subscriber.get(timeout=1)
            except queue.Empty:
                continue
            envelope = json.loads(data)
            if envelope["event_id"] in self._injected_event_ids:
                continue  # don't re-forward what we just injected from the hub
            subject = subject_for_event(self.workspace_id, envelope["event_type"], envelope["payload"])
            self.client.publish(subject, data)

    def _on_hub_message(self, subject: str, payload: str) -> None:
        envelope_dict = json.loads(payload)
        event_id = envelope_dict["event_id"]
        self._injected_event_ids.add(event_id)
        sender = ActorIdentifier.from_dict(envelope_dict["sender"])
        recipient = ActorIdentifier.from_dict(envelope_dict["recipient"]) if envelope_dict.get("recipient") else None
        envelope = EventEnvelope(
            event_id=event_id,
            timestamp=envelope_dict["timestamp"],
            sender=sender,
            event_type=envelope_dict["event_type"],
            payload=envelope_dict["payload"],
            recipient=recipient,
        )
        self.broker.publish(envelope)
```

Add the needed imports at the top of `synlynk/relay_hub.py`:

```python
import queue
import threading
from synlynk.events import ActorIdentifier, EventEnvelope
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS. Note: `_pump_local_to_hub` runs in a background thread and `FakeNatsClient.publish` is called asynchronously relative to `broker.publish()` returning — the test for forwarding may need a short poll. Replace the bare assertion in `test_adapter_forwards_local_publish_to_hub` with a short retry loop:

```python
    import time
    for _ in range(50):
        if fake_client.published:
            break
        time.sleep(0.02)
    assert len(fake_client.published) == 1
```

Apply the same retry pattern to `test_adapter_does_not_reforward_messages_it_just_injected` (poll briefly, then assert still empty) so it isn't a race against the 1-second queue timeout.

- [ ] **Step 5: Commit**

```bash
git add synlynk/relay_hub.py tests/test_relay_hub.py
git commit -m "feat(relay): add HubAdapter bridging local broker to NATS hub, with echo-loop guard"
```

---

### Task 6: JetStream durable replay + sync-gap detection

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

This task adds the pieces that need a real NATS JetStream connection to behave meaningfully (sequence tracking, gap detection), so it's unit-tested with a fake JetStream context that mimics the sequence-number contract, keeping Task 5's fake-client style consistent. The real JetStream wiring is exercised in Task 8's integration test.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
from synlynk.relay_hub import ReplayTracker


class FakeJetStreamConsumer:
    def __init__(self, stream_messages):
        self._stream_messages = stream_messages  # list of (seq, subject, payload)
        self.earliest_seq = stream_messages[0][0] if stream_messages else 0

    def fetch_since(self, last_seq):
        return [m for m in self._stream_messages if m[0] > last_seq]


def test_replay_tracker_resumes_from_last_delivered_sequence():
    tracker = ReplayTracker(device_id="dev-1")
    tracker.record_delivered(seq=5)
    messages = [(6, "synlynk.ws1.job.x", "a"), (7, "synlynk.ws1.job.y", "b")]
    consumer = FakeJetStreamConsumer(messages)
    pending = tracker.replay(consumer)
    assert [seq for seq, _, _ in pending] == [6, 7]
    assert tracker.last_delivered_seq == 7


def test_replay_tracker_detects_sync_gap_when_history_was_pruned():
    tracker = ReplayTracker(device_id="dev-1")
    tracker.record_delivered(seq=5)
    consumer = FakeJetStreamConsumer([(100, "synlynk.ws1.job.x", "a")])
    consumer.earliest_seq = 50  # retention pruned everything below 50
    assert tracker.detect_sync_gap(consumer) is True


def test_replay_tracker_no_gap_when_earliest_seq_within_reach():
    tracker = ReplayTracker(device_id="dev-1")
    tracker.record_delivered(seq=5)
    consumer = FakeJetStreamConsumer([(6, "synlynk.ws1.job.x", "a")])
    consumer.earliest_seq = 1
    assert tracker.detect_sync_gap(consumer) is False


def test_replay_tracker_first_connect_has_no_gap():
    tracker = ReplayTracker(device_id="dev-1")  # never delivered anything yet
    consumer = FakeJetStreamConsumer([(1, "synlynk.ws1.job.x", "a")])
    assert tracker.detect_sync_gap(consumer) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'ReplayTracker'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add

class ReplayTracker:
    """Tracks a device's last-delivered JetStream sequence number and
    detects when retention has pruned messages this device never saw."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.last_delivered_seq: int | None = None

    def record_delivered(self, seq: int) -> None:
        self.last_delivered_seq = seq

    def replay(self, consumer) -> list[tuple[int, str, str]]:
        """Return messages the device hasn't seen yet, in sequence order,
        and advance last_delivered_seq to the newest one returned."""
        if self.last_delivered_seq is None:
            pending = consumer.fetch_since(0)
        else:
            pending = consumer.fetch_since(self.last_delivered_seq)
        if pending:
            self.record_delivered(pending[-1][0])
        return pending

    def detect_sync_gap(self, consumer) -> bool:
        """True if this device's last-seen position predates what the
        stream still retains — i.e. some events were pruned before replay."""
        if self.last_delivered_seq is None:
            return False  # first-ever connect: nothing to have missed
        return self.last_delivered_seq < consumer.earliest_seq
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add synlynk/relay_hub.py tests/test_relay_hub.py
git commit -m "feat(relay): add ReplayTracker for durable-consumer resume and sync-gap detection"
```

---

### Task 7: CLI wiring — `relay hub init/connect`, `device add/revoke`, `subscribe/unsubscribe`

**Files:**
- Modify: `synlynk/cli.py:1284-1317` (extend existing `relay` subparser)
- Modify: `synlynk/cli.py:2567-2604` (extend existing `relay` command dispatch)
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
import io
import contextlib
from synlynk.relay_hub import cmd_relay_device_add, cmd_relay_device_revoke
from argparse import Namespace


def test_cmd_relay_device_add_prints_device_id_and_warns_once():
    with tempfile.TemporaryDirectory() as tmp:
        args = Namespace(name="laptop", workspace_id="ws1", config_dir=tmp)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_relay_device_add(args)
        output = buf.getvalue()
        assert "dev-" in output
        assert "laptop" in output


def test_cmd_relay_device_revoke_reports_not_found_for_unknown_id():
    with tempfile.TemporaryDirectory() as tmp:
        args = Namespace(device_id="dev-doesnotexist", workspace_id="ws1", config_dir=tmp)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_relay_device_revoke(args)
        assert "not found" in buf.getvalue().lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'cmd_relay_device_add'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add

def _default_config_dir() -> str:
    return os.path.expanduser("~/.synlynk/relay")


def cmd_relay_device_add(args) -> None:
    config_dir = getattr(args, "config_dir", None) or _default_config_dir()
    store = DeviceCredentialStore(workspace_id=args.workspace_id, config_dir=config_dir)
    cred = store.add_device(args.name)
    print(f"Added device '{cred.name}' ({cred.device_id})")
    print(f"Credential written to {config_dir}/{cred.device_id}.creds — keep this file secret.")


def cmd_relay_device_revoke(args) -> None:
    config_dir = getattr(args, "config_dir", None) or _default_config_dir()
    store = DeviceCredentialStore(workspace_id=args.workspace_id, config_dir=config_dir)
    existing = store.get_device(args.device_id)
    if existing is None:
        print(f"Device {args.device_id} not found.")
        return
    revoked = store.revoke_device(args.device_id)
    if revoked:
        print(f"Revoked device {args.device_id} ({existing.name}). Effective immediately.")
    else:
        print(f"Device {args.device_id} was already revoked.")


def cmd_relay_hub_init(args) -> None:
    config_dir = getattr(args, "config_dir", None) or _default_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    hub_config = {"workspace_id": args.workspace_id, "mode": "self_hosted"}
    with open(os.path.join(config_dir, "hub.json"), "w") as f:
        json.dump(hub_config, f, indent=2)
    print(f"Self-hosted hub config written to {config_dir}/hub.json for workspace '{args.workspace_id}'.")
    print("Run 'synlynk relay device add <name>' to mint a device credential, "
          "then start nats-server with the generated authorization block.")


def cmd_relay_hub_connect(args) -> None:
    config_dir = getattr(args, "config_dir", None) or _default_config_dir()
    os.makedirs(config_dir, exist_ok=True)
    hub_config = {"workspace_id": args.workspace_id, "mode": "managed", "token": args.token}
    with open(os.path.join(config_dir, "hub.json"), "w") as f:
        json.dump(hub_config, f, indent=2)
    print(f"Managed hub config written to {config_dir}/hub.json. "
          "Run 'synlynk relay device add <name>' to register this device.")


def cmd_relay_subscribe(args) -> None:
    sub_path = os.path.join(os.getcwd(), ".synlynk", "relay-subscriptions.json")
    os.makedirs(os.path.dirname(sub_path), exist_ok=True)
    patterns = []
    if os.path.exists(sub_path):
        with open(sub_path) as f:
            patterns = json.load(f)
    if args.pattern not in patterns:
        patterns.append(args.pattern)
    with open(sub_path, "w") as f:
        json.dump(patterns, f, indent=2)
    print(f"Subscribed to {args.pattern}")


def cmd_relay_unsubscribe(args) -> None:
    sub_path = os.path.join(os.getcwd(), ".synlynk", "relay-subscriptions.json")
    patterns = []
    if os.path.exists(sub_path):
        with open(sub_path) as f:
            patterns = json.load(f)
    if args.pattern in patterns:
        patterns.remove(args.pattern)
    with open(sub_path, "w") as f:
        json.dump(patterns, f, indent=2)
    print(f"Unsubscribed from {args.pattern}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Wire the new subcommands into the CLI parser**

```python
# synlynk/cli.py — insert after line 1317 (end of existing relay_peer_list_p block), still inside the `relay` subparser setup

    relay_hub_p = relay_sub.add_parser("hub", help="Manage the opt-in hosted relay hub")
    relay_hub_sub = relay_hub_p.add_subparsers(dest="relay_hub_action")
    relay_hub_init_p = relay_hub_sub.add_parser("init", help="Initialize a self-hosted hub config")
    relay_hub_init_p.add_argument("--workspace-id", required=True, dest="workspace_id")
    relay_hub_init_p.add_argument("--config-dir", default=None, dest="config_dir")
    relay_hub_connect_p = relay_hub_sub.add_parser("connect", help="Connect to a managed hub")
    relay_hub_connect_p.add_argument("token", help="Workspace token from synlynk.com")
    relay_hub_connect_p.add_argument("--workspace-id", required=True, dest="workspace_id")
    relay_hub_connect_p.add_argument("--config-dir", default=None, dest="config_dir")

    relay_device_p = relay_sub.add_parser("device", help="Manage per-device hub credentials")
    relay_device_sub = relay_device_p.add_subparsers(dest="relay_device_action")
    relay_device_add_p = relay_device_sub.add_parser("add", help="Mint a new device credential")
    relay_device_add_p.add_argument("name", help="Human-readable device name")
    relay_device_add_p.add_argument("--workspace-id", required=True, dest="workspace_id")
    relay_device_add_p.add_argument("--config-dir", default=None, dest="config_dir")
    relay_device_revoke_p = relay_device_sub.add_parser("revoke", help="Revoke a device credential")
    relay_device_revoke_p.add_argument("device_id")
    relay_device_revoke_p.add_argument("--workspace-id", required=True, dest="workspace_id")
    relay_device_revoke_p.add_argument("--config-dir", default=None, dest="config_dir")

    relay_subscribe_p = relay_sub.add_parser("subscribe", help="Subscribe this device to a subject pattern")
    relay_subscribe_p.add_argument("pattern", help='e.g. "job.>" or "sentinel.>"')
    relay_unsubscribe_p = relay_sub.add_parser("unsubscribe", help="Unsubscribe this device from a subject pattern")
    relay_unsubscribe_p.add_argument("pattern")
```

- [ ] **Step 6: Wire the new subcommands into the dispatch block**

```python
# synlynk/cli.py — inside the `elif args.command == "relay":` block (~line 2567-2604), add before the final `else: relay_parser.print_help()`

        elif action == "hub":
            hub_action = getattr(args, "relay_hub_action", None)
            if hub_action == "init":
                from synlynk.relay_hub import cmd_relay_hub_init
                cmd_relay_hub_init(args)
            elif hub_action == "connect":
                from synlynk.relay_hub import cmd_relay_hub_connect
                cmd_relay_hub_connect(args)
            else:
                relay_hub_p.print_help()
        elif action == "device":
            device_action = getattr(args, "relay_device_action", None)
            if device_action == "add":
                from synlynk.relay_hub import cmd_relay_device_add
                cmd_relay_device_add(args)
            elif device_action == "revoke":
                from synlynk.relay_hub import cmd_relay_device_revoke
                cmd_relay_device_revoke(args)
            else:
                relay_device_p.print_help()
        elif action == "subscribe":
            from synlynk.relay_hub import cmd_relay_subscribe
            cmd_relay_subscribe(args)
        elif action == "unsubscribe":
            from synlynk.relay_hub import cmd_relay_unsubscribe
            cmd_relay_unsubscribe(args)
```

Note: `relay_hub_p` and `relay_device_p` must be in scope at the dispatch site — they're already local variables from the parser-building function; if the dispatch block lives in a different function than the parser setup, thread them through the same way the existing `relay_parser`/`relay_peer_p` references at lines 1792/2602 are threaded (check how `relay_peer_p.print_help()` at line 2602 currently accesses `relay_peer_p` and mirror that pattern exactly).

- [ ] **Step 7: Add a CLI-level smoke test**

```python
# tests/test_relay_hub.py (add)
def test_cli_relay_device_add_subcommand_registered():
    from synlynk.cli import build_parser  # adjust to the actual parser-builder function name if different
    parser = build_parser()
    args = parser.parse_args(["relay", "device", "add", "laptop", "--workspace-id", "ws1"])
    assert args.command == "relay"
    assert args.relay_action == "device"
    assert args.relay_device_action == "add"
    assert args.name == "laptop"
```

Before writing this step, grep `synlynk/cli.py` for the actual name of the function that builds the top-level `argparse.ArgumentParser` (it may not be called `build_parser`) and use that exact name — this is a case where confirming the real function name against the file is required before the test can be correct.

- [ ] **Step 8: Run full relay test suite**

Run: `pytest tests/test_relay_hub.py tests/test_relay.py tests/test_relay_p2p.py -v`
Expected: PASS, no regressions in existing relay tests

- [ ] **Step 9: Commit**

```bash
git add synlynk/cli.py synlynk/relay_hub.py tests/test_relay_hub.py
git commit -m "feat(relay): wire hub init/connect, device add/revoke, subscribe/unsubscribe into CLI"
```

---

### Task 8: Integration test against a real embedded nats-server

**Files:**
- Create: `tests/test_relay_hub_integration.py`

This exercises the real `nats-py` client + a real `nats-server` process end-to-end: two `RelayBroker` instances (simulating two devices), each bridged via a real `HubAdapter`, publishing through an actual NATS server, verifying replay-on-reconnect and device revocation. Per the spec, no live synlynk.com managed-hub testing — this is entirely local.

- [ ] **Step 1: Write the test, guarded by a `nats-server` binary check**

```python
# tests/test_relay_hub_integration.py
import shutil
import subprocess
import time
import json
import pytest

nats = pytest.importorskip("nats")

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None,
    reason="nats-server binary not found on PATH",
)


@pytest.fixture
def nats_server(tmp_path):
    port = 14222
    proc = subprocess.Popen(
        ["nats-server", "-p", str(port), "-js", "-sd", str(tmp_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.5)  # server startup
    try:
        yield f"nats://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


async def _connect(url):
    return await nats.connect(url)


def test_event_published_on_device_a_is_delivered_to_device_b(nats_server):
    import asyncio
    from synlynk.relay import RelayBroker
    from synlynk.relay_hub import HubAdapter
    from synlynk.events import ActorIdentifier, EventEnvelope

    async def scenario():
        broker_a = RelayBroker()
        broker_b = RelayBroker()
        client_a = await nats.connect(nats_server)
        client_b = await nats.connect(nats_server)

        class SyncWrapper:
            """Adapts nats-py's async client to HubAdapter's sync publish/subscribe
            contract by running coroutines on the current event loop."""
            def __init__(self, nc, loop):
                self.nc = nc
                self.loop = loop

            def publish(self, subject, payload):
                asyncio.run_coroutine_threadsafe(
                    self.nc.publish(subject, payload.encode()), self.loop
                )

            def subscribe(self, subject, callback):
                async def handler(msg):
                    callback(msg.subject, msg.data.decode())
                asyncio.run_coroutine_threadsafe(
                    self.nc.subscribe(subject, cb=handler), self.loop
                )

        loop = asyncio.get_event_loop()
        adapter_a = HubAdapter(broker_a, SyncWrapper(client_a, loop), workspace_id="ws1")
        adapter_b = HubAdapter(broker_b, SyncWrapper(client_b, loop), workspace_id="ws1")
        adapter_a.attach()
        adapter_b.attach()
        await asyncio.sleep(0.2)  # let subscriptions register

        subscriber_b = broker_b.subscribe()
        sender = ActorIdentifier(workspace_id="ws1", member_id="m", agent_role="dev",
                                  harness="claude", job_id="j1")
        envelope = EventEnvelope.create(sender, "review_requested", {"pr_url": "https://x"})
        broker_a.publish(envelope)

        await asyncio.sleep(0.5)  # cross-process delivery
        delivered = subscriber_b.get(timeout=2)
        assert json.loads(delivered)["event_id"] == envelope.event_id

        await client_a.close()
        await client_b.close()

    asyncio.run(scenario())


def test_revoked_device_authorization_block_excludes_token(nats_server, tmp_path):
    from synlynk.relay_hub import DeviceCredentialStore

    store = DeviceCredentialStore(workspace_id="ws1", config_dir=str(tmp_path))
    active = store.add_device("laptop")
    revoked = store.add_device("old-vps")
    store.revoke_device(revoked.device_id)

    block = store.render_authorization_block()
    assert active.token in block
    assert revoked.token not in block
```

- [ ] **Step 2: Run test to verify it fails before implementation gaps are fixed, then passes**

Run: `pytest tests/test_relay_hub_integration.py -v`
Expected: SKIPPED if `nats-server` isn't installed locally (document in the commit message that this requires `brew install nats-server` or equivalent to actually execute); PASS if it is. If it fails with a real assertion error (not skip/not import error), treat that as a genuine integration bug in `HubAdapter` and fix `HubAdapter` itself — do not weaken this test to make it pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_relay_hub_integration.py
git commit -m "test(relay): add end-to-end hub integration test against real nats-server"
```

---

### Task 9: Doc/artifact preview channel

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

Implements the `doc.drafted`/`doc.updated` payload shape and the receiving-device preview-copy writer. This task does **not** implement a filesystem watcher (out of scope — the plan assumes something that already knows when a spec/plan file changes, such as the brainstorming/writing-plans skills themselves or a future `git hook`, calls `publish_doc_event()` directly); it implements the publish-side payload builder and the receive-side preview writer, which is the actual relay-layer contract.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_relay_hub.py (add)
from synlynk.relay_hub import build_doc_event_payload, write_doc_preview, DOC_PREVIEW_MAX_BYTES


def test_build_doc_event_payload_includes_content_under_size_threshold():
    payload = build_doc_event_payload(
        path="docs/superpowers/specs/2026-10-12-x.md",
        branch="docs/claude/x",
        commit_sha=None,
        content="# Hello\n",
    )
    assert payload["path"] == "docs/superpowers/specs/2026-10-12-x.md"
    assert payload["content"] == "# Hello\n"


def test_build_doc_event_payload_omits_content_over_size_threshold():
    big_content = "x" * (DOC_PREVIEW_MAX_BYTES + 1)
    payload = build_doc_event_payload(
        path="docs/superpowers/specs/big.md", branch="b", commit_sha="abc123",
        content=big_content,
    )
    assert "content" not in payload
    assert payload["commit_sha"] == "abc123"


def test_write_doc_preview_writes_readonly_labeled_copy(tmp_path):
    preview_path = write_doc_preview(
        base_dir=str(tmp_path), device_id="dev-1",
        path="docs/superpowers/specs/x.md", content="# Preview\n",
    )
    with open(preview_path) as f:
        text = f.read()
    assert "PREVIEW ONLY" in text
    assert "# Preview" in text
    assert preview_path == str(tmp_path / "dev-1" / "docs/superpowers/specs/x.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_doc_event_payload'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/relay_hub.py — add

DOC_PREVIEW_MAX_BYTES = 1_000_000  # NATS default max message size ceiling


def build_doc_event_payload(path: str, branch: str, commit_sha: str | None, content: str) -> dict:
    payload = {"path": path, "branch": branch, "commit_sha": commit_sha}
    if len(content.encode("utf-8")) <= DOC_PREVIEW_MAX_BYTES:
        payload["content"] = content
    return payload


def write_doc_preview(base_dir: str, device_id: str, path: str, content: str) -> str:
    """Write a read-only-labeled preview copy, never merged into a real worktree."""
    target_dir = os.path.join(base_dir, device_id, os.path.dirname(path))
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(base_dir, device_id, path)
    header = (
        f"<!-- PREVIEW ONLY — synced from another device, not merged into this "
        f"worktree. Do not edit. Source: {path} -->\n\n"
    )
    with open(target_path, "w") as f:
        f.write(header + content)
    return target_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/relay_hub.py tests/test_relay_hub.py
git commit -m "feat(relay): add doc/artifact preview payload builder and preview-copy writer"
```

---

### Task 10: Full-suite regression check

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -q`
Expected: all pre-existing tests still pass; new `test_relay_hub.py` tests pass; `test_relay_hub_integration.py` passes or skips cleanly depending on whether `nats-server` is installed in the current environment.

- [ ] **Step 2: Commit any fixups**

If the full-suite run surfaces an unrelated pre-existing failure, do not fix it as part of this plan — note it and move on. If it surfaces a regression caused by this plan's changes (e.g. the `RELAY_EVENT_TYPES` extension breaking a test that enumerates the exact tuple), fix it and commit:

```bash
git add -A
git commit -m "fix(relay): address full-suite regression from hosted relay changes"
```

---

## Self-Review

**1. Spec coverage:**
- Three-piece architecture (local broker unchanged / hub / adapter) — Tasks 4-5 (hub config + adapter), local broker untouched throughout. ✅
- Subject taxonomy + per-category retention — Task 3. ✅
- RPC method remapping onto subjects — Task 3's `_EVENT_TYPE_SUFFIX_BUILDERS` covers `task_progress`→agent.*, `steering_injected`→device.*, `review_requested`→job.*; `relay.send_message`/`broadcast`/`runner_progress` already map to `task_progress` internally in `RelayBroker.rpc()` (synlynk/relay.py:184-211), so they flow through the same `task_progress` suffix builder — no additional mapping needed. ✅
- Per-device credentials, revocable individually — Task 4 (flagged deviation from nkey/JWT to bearer-token+permissions, documented). ✅
- Hub init/connect, self-hosted vs managed — Task 7. ✅
- Durable replay + sync-gap detection — Task 6. ✅
- Doc/artifact preview channel — Task 9. ✅
- Error handling case 1 (adapter unreachable, `hub_disconnected` event) — event type added in Task 2; actual backoff-retry *loop* around `HubAdapter.attach()`'s connection attempt is **not implemented** in this plan (Tasks 5's `HubAdapter` assumes an already-connected client is handed in). **Gap — see note below.**
- Error handling case 2 (credential revoked → `synlynk relay status` shows "credential revoked") — Task 4 implements revocation server-side (authorization block exclusion); the CLI-visible status message is **not implemented** in this plan. **Gap — see note below.**
- Testing strategy (fake-client unit tests + real nats-server integration test, no managed-hub testing) — Tasks 5, 6, 8. ✅
- Feature gating (self-hosted = no gating, managed = JWT claim check hook point) — **not implemented** in this plan; the spec itself scopes this as a hook point only, no billing implementation, and this plan doesn't even add the hook. **Gap — see note below.**

**Gaps carried forward intentionally, not silently dropped:** the three items above (adapter reconnect/backoff loop, `synlynk relay status` hub-awareness, managed-hub entitlement hook) are real spec content this plan doesn't cover. They're connectivity/polish and server-side-managed-hub concerns respectively — implementable once the core bridge (Tasks 1-9) is proven, and none of them block a self-hosted single-device-pair hub from working end-to-end. Flagging explicitly rather than listing a fake task: recommend a short follow-up plan once Tasks 1-9 are dispatched and merged, scoped to "hub reconnect/backoff + status surface" (small, ~2-3 tasks) before calling the self-hosted path production-ready.

**2. Placeholder scan:** No "TBD"/"TODO" found. Every code step contains runnable code. Task 7 Step 6 has one explicit "verify the real function name before writing this" instruction (`build_parser`) — this is a legitimate grounding caveat (the plan author didn't have that symbol confirmed), not a placeholder; the step still shows real code and the test's assertions are concrete regardless of the function name.

**3. Type consistency:** `HubAdapter(broker, client, workspace_id)` constructor signature (Task 5) is used identically in Task 8's integration test. `DeviceCredentialStore(workspace_id, config_dir)` constructor is consistent across Tasks 4, 7, and 8. `subject_for_event(workspace_id, event_type, payload)` signature from Task 3 is called with matching argument order inside `HubAdapter._pump_local_to_hub` in Task 5. `ReplayTracker` from Task 6 is not yet wired into `HubAdapter` — it's built but not called from Task 5/8's integration flow in this plan. **Gap, flagged:** the integration test in Task 8 tests basic pub/delivery, not durable replay specifically (no reconnect-after-disconnect scenario). A tighter version of Task 8 would add a third test that disconnects/reconnects `client_b` and verifies `ReplayTracker` delivers the missed message — recommend adding that as Task 8 Step 4 if time allows during implementation; noting it here rather than silently shipping Task 6's code unintegrated.

---

## Execution Handoff

**GOVERNS linkage complete:** `goal-f4ce526a` created outside the dev-preview GOVERNS tree, with 10 stories linked and marked ready — see the GOVERNS note at the top of this plan for the full goal/story-ID mapping. Dispatch may proceed.

**Execution approach: Subagent-Driven via `synlynk dispatch`** (chosen 2026-10-12, per standing project memory `feedback_subagent_driven_via_synlynk_dispatch.md`): the implementer stage for each task is dispatched via `synlynk dispatch` to Codex/Grok/Agy — never a generic Claude subagent — while the two-stage review (spec-compliance, then code-quality) is performed directly by Claude (PM/review role), not dispatched. Tasks proceed in order 1→10, each linked to its respective story ID, continuing autonomously per the subagent-driven-development skill's "Continuous execution" principle.
