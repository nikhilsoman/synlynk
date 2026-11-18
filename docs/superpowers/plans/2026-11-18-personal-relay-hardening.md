# Personal Relay Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automated reconnect with exponential backoff & jitter, unified dual-tier status observability (`synlynk relay status` and `--json`), and fail-closed managed handshake preflight in `synlynk/relay_hub.py`.

**Architecture:** Builds on the existing `HubAdapter` and `DeviceCredentialStore` in `synlynk/relay_hub.py`. Introduces an internal `ConnectionSupervisor` for managing connection lifecycle states (`STOPPED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `AUTH_FAILED`), emits local `hub_disconnected` and `hub_reconnected` events, enriches `synlynk relay status` with hub bridge telemetry, and validates managed service tokens before writing `hub.json`.

**Tech Stack:** Python 3.10+ stdlib, `nats-py` (optional dependency via `[hub]`), SQLite (`state.db`).

**Source Spec:** `docs/superpowers/specs/2026-11-18-personal-relay-hardening-design.md` (gh:#2918, parent gh:#5123, goal `goal-f4ce526a`).

---

## File Structure

- **Modify `synlynk/events.py`** — Add `hub_reconnected` to `RELAY_EVENT_TYPES`.
- **Modify `synlynk/relay_hub.py`** — Implement `ConnectionSupervisor`, `HubStatusSnapshot`, wire reconnect/backoff into `HubAdapter`, add managed hub preflight handshake.
- **Modify `synlynk/relay.py` & `synlynk/cli.py`** — Upgrade `cmd_relay_status` to report dual-tier status and support `--json`.
- **Modify `tests/test_relay_hub.py`** — Add unit tests covering backoff calculations, jitter distribution, disconnect/reconnect event emission, status reporting, and handshake preflight.

---

### Task 1: Extend Event Whitelist for Reconnect Lifecycle

**Files:**
- Modify: `synlynk/events.py`
- Test: `tests/test_relay_hub.py`

- [x] **Step 1: Write the failing test**

```python
# In tests/test_relay_hub.py
def test_hub_reconnected_event_type_is_accepted_by_envelope():
    """EventEnvelope must accept hub_reconnected as a valid event type."""
    from synlynk.events import EventEnvelope, ActorIdentifier
    actor = ActorIdentifier("personal", "laptop", "relay", "nats", "")
    payload = {
        "origin_device_id": "laptop",
        "downtime_seconds": 12.5,
        "reconnect_attempt": 2,
        "resumed_streams": ["job", "agent"],
    }
    envelope = EventEnvelope.create(actor, "hub_reconnected", payload)
    assert envelope.event_type == "hub_reconnected"
    assert envelope.payload["downtime_seconds"] == 12.5
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_relay_hub.py -k test_hub_reconnected_event_type_is_accepted_by_envelope -v`
Expected: FAIL with `ValueError: Unknown event_type: hub_reconnected`

- [x] **Step 3: Update `synlynk/events.py`**

In `synlynk/events.py`, add `"hub_reconnected"` to `RELAY_EVENT_TYPES`:

```python
RELAY_EVENT_TYPES = (
    # ... existing events ...
    "hub_disconnected",
    "hub_reconnected",
    "sync_gap_detected",
    # ...
)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_relay_hub.py -k test_hub_reconnected_event_type_is_accepted_by_envelope -v`
Expected: PASS

---

### Task 2: Implement ConnectionSupervisor with Exponential Backoff & Jitter

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

- [x] **Step 1: Write tests for backoff calculation and state transitions**

```python
# In tests/test_relay_hub.py
def test_connection_supervisor_backoff_bounds():
    """Backoff intervals must increase exponentially up to max_backoff with jitter."""
    from synlynk.relay_hub import ConnectionSupervisor
    sup = ConnectionSupervisor(base_delay=1.0, multiplier=1.5, max_delay=30.0)
    
    # Attempt 0: delay between 0 and 1.0
    delay_0 = sup.calculate_delay(0)
    assert 0.0 <= delay_0 <= 1.0
    
    # Attempt 1: delay between 0 and 1.5
    delay_1 = sup.calculate_delay(1)
    assert 0.0 <= delay_1 <= 1.5
    
    # Large attempt: delay capped at max_delay
    delay_high = sup.calculate_delay(20)
    assert 0.0 <= delay_high <= 30.0

def test_connection_supervisor_state_transitions():
    """Supervisor must transition through lifecycle states correctly."""
    from synlynk.relay_hub import ConnectionSupervisor
    sup = ConnectionSupervisor()
    assert sup.state == "STOPPED"
    
    sup.set_connecting()
    assert sup.state == "CONNECTING"
    
    sup.set_connected()
    assert sup.state == "CONNECTED"
    assert sup.attempt_count == 0
    
    sup.set_reconnecting(error=ConnectionRefusedError())
    assert sup.state == "RECONNECTING"
    assert sup.attempt_count == 1
    
    sup.set_auth_failed(error=PermissionError("auth violation"))
    assert sup.state == "AUTH_FAILED"
```

- [x] **Step 2: Run test to verify failure**

Run: `pytest tests/test_relay_hub.py -k test_connection_supervisor -v`
Expected: FAIL with `ImportError: cannot import name 'ConnectionSupervisor'`

- [x] **Step 3: Implement `ConnectionSupervisor` in `synlynk/relay_hub.py`**

```python
class ConnectionSupervisor:
    """Manages connection lifecycle state, attempt tracking, and backoff jitter."""
    
    def __init__(self, base_delay: float = 1.0, multiplier: float = 1.5, max_delay: float = 60.0):
        self.base_delay = base_delay
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.state = "STOPPED"
        self.attempt_count = 0
        self.last_error = None
        self.connected_at = None
        self.disconnected_at = None
        self._lock = threading.Lock()

    def calculate_delay(self, attempt: int) -> float:
        ceiling = min(self.max_delay, self.base_delay * (self.multiplier ** attempt))
        return random.uniform(0.0, ceiling)

    def set_connecting(self):
        with self._lock:
            self.state = "CONNECTING"

    def set_connected(self):
        with self._lock:
            self.state = "CONNECTED"
            self.attempt_count = 0
            self.connected_at = time.time()
            self.last_error = None

    def set_reconnecting(self, error: Exception):
        with self._lock:
            if self.state == "CONNECTED":
                self.disconnected_at = time.time()
            self.state = "RECONNECTING"
            self.attempt_count += 1
            self.last_error = str(error) or type(error).__name__

    def set_auth_failed(self, error: Exception):
        with self._lock:
            self.state = "AUTH_FAILED"
            self.last_error = str(error) or type(error).__name__

    def set_stopped(self):
        with self._lock:
            self.state = "STOPPED"
```

- [x] **Step 4: Run test to verify passes**

Run: `pytest tests/test_relay_hub.py -k test_connection_supervisor -v`
Expected: PASS

---

### Task 3: Wire Reconnect & Lifecycle Events into HubAdapter

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

- [x] **Step 1: Write test for reconnect event emissions and terminal auth handling**

```python
# In tests/test_relay_hub.py
def test_hub_adapter_emits_reconnect_and_disconnect_events():
    """Adapter must emit hub_disconnected and hub_reconnected events."""
    # Test with mock transport triggering simulated drop and recovery
    ...
```

- [x] **Step 2: Implement reconnect loop in `HubAdapter`**
- [x] **Step 3: Run pytest on `tests/test_relay_hub.py` to verify passes**

---

### Task 4: HubStatusSnapshot & Dual-Tier Relay Status Output

**Files:**
- Modify: `synlynk/relay_hub.py`
- Modify: `synlynk/relay.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_relay_hub.py`

- [x] **Step 1: Write test for `cmd_relay_status` text and json formatting**
- [x] **Step 2: Add `get_status_snapshot()` to `HubAdapter` and inspect `hub.json` when stopped**
- [x] **Step 3: Implement `--json` flag on `synlynk relay status`**
- [x] **Step 4: Run pytest on status tests to verify passes**

---

### Task 5: Managed Hub Preflight Probe

**Files:**
- Modify: `synlynk/relay_hub.py`
- Test: `tests/test_relay_hub.py`

- [x] **Step 1: Write test for `cmd_relay_hub_connect` preflight validation**
- [x] **Step 2: Implement HTTP preflight probe prior to writing `hub.json`**
- [x] **Step 3: Verify rejection of invalid tokens and atomic storage on 200 OK**

---

### Task 6: Full Regression Verification

**Files:**
- All modified files

- [x] **Step 1: Run complete unit test suite**
  ```sh
  python3 -m pytest tests/test_relay_hub.py tests/test_relay.py tests/test_relay_p2p.py -v
  ```
- [x] **Step 2: Verify `synlynk relay status` in terminal**
- [x] **Step 3: Verify git status is clean and format complies with conventions**
