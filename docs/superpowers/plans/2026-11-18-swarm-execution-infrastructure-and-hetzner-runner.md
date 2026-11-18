# Hetzner Cloud Swarm Runner Driver & Vertical Milestone Host Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Hetzner Cloud Swarm Runner Driver (`HetznerRunnerDriver`) and the Vertical Milestone Host Orchestration Pattern to enable high-velocity, scale-to-zero milestone builds with strict single-tenant KVM isolation and zero cross-workspace state leakage.

**Architecture:** A new `synlynk/runners/hetzner.py` module implements `SwarmRunnerDriver` using Python standard library HTTP over the Hetzner Cloud REST API (`https://api.hetzner.cloud/v1`). Milestone leasing (`synlynk swarm lease`) dynamically sizes dedicated vertical hosts (`cpx21`, `cpx31`, `cpx51`), runs tasks concurrently across local git worktrees on NVMe, and uses NATS Relay for encrypted bundle sync. Triple-layer watchdogs (OS cloud-init, shell trap, client supervisor) guarantee scale-to-zero destruction, and structured telemetry is emitted for consumption by the monetization epic ([gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359)).

**Tech Stack:** Python 3.10+ stdlib (urllib, json, threading, dataclasses), SQLite (`state.db`), Hetzner Cloud REST API, NATS JetStream Relay Hub. Zero new external dependencies.

**Source Spec:** `docs/superpowers/specs/2026-11-18-swarm-execution-infrastructure-and-hetzner-runner-design.md` ([gh:#5360](https://github.com/nikhilsoman/synlynk/issues/5360))  
**Governing Goal:** `arc-goal-01C3FA0F` (Theme 6: Hetzner Cloud Swarm Runner & Vertical Milestone Host Orchestration; corrected 2026-11-18 from a stale `goal-d5323df6` reference that was never created in `goals` — see gh:#5373)  
**Milestone:** `v0.39.1` (Theme 6 Fast-Follow)

---

## File Structure

- **Create `synlynk/runners/hetzner.py`** — `HetznerRunnerDriver` implementation (`provision`, `stream_telemetry`, `collect_results`, `destroy`), dynamic server sizing matrix, cloud-init user-data builder, watchdog timer supervisor.
- **Modify `synlynk/runners/manager.py`** — register `hetzner` driver in `RunnerManager._load_drivers()` when present in config or enabled drivers.
- **Modify `synlynk/swarm.py`** — add `calculate_vertical_host_size(task_count)`, `cmd_swarm_lease_dispatch()`, `cmd_swarm_lease_list()`, `cmd_swarm_lease_destroy()`, and `milestone_lease_completed` event emission.
- **Modify `synlynk/cli.py`** — add `lease` subparser under `swarm` with `--epic`, `--size`, `--driver`, `--nodes`, `--drain-on-empty`.
- **Create `tests/test_runners_hetzner.py`** — unit tests for Hetzner runner driver, REST payload construction, dynamic sizing, mock HTTP responses, and watchdog timers.
- **Modify `tests/test_swarm.py`** — tests for vertical host sizing calculation and milestone lease lifecycle commands.

---

### Task 1: `HetznerRunnerDriver` Scaffolding & Schema

**Files:**
- Create: `synlynk/runners/hetzner.py`
- Modify: `synlynk/runners/manager.py`
- Create: `tests/test_runners_hetzner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runners_hetzner.py
import pytest
from synlynk.runners.base import SwarmRunnerDriver
from synlynk.runners.hetzner import HetznerRunnerDriver
from synlynk.runners.manager import RunnerManager


def test_hetzner_driver_implements_interface():
    driver = HetznerRunnerDriver(config={"token": "test-token"})
    assert isinstance(driver, SwarmRunnerDriver)
    assert driver.base_url == "https://api.hetzner.cloud/v1"
    assert driver.token == "test-token"
    assert driver.location == "nbg1"


def test_hetzner_driver_registered_in_manager():
    config = {
        "swarm_runners": {
            "enabled": ["local", "hetzner"],
            "hetzner": {"token": "mock-token", "location": "fsn1"},
        }
    }
    manager = RunnerManager(config=config)
    driver = manager.driver("hetzner")
    assert isinstance(driver, HetznerRunnerDriver)
    assert driver.token == "mock-token"
    assert driver.location == "fsn1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runners_hetzner.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.runners.hetzner'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/runners/hetzner.py
"""Hetzner Cloud ephemeral swarm runner driver using Python stdlib HTTP."""

from __future__ import annotations

import json
import os
import threading
import urllib.request
import urllib.error
from typing import Any, Callable

from synlynk.runners.base import SwarmRunnerDriver


class HetznerRunnerDriver(SwarmRunnerDriver):
    """Provisions, supervises, and tears down ephemeral single-tenant Hetzner Cloud VMs."""

    SERVER_TYPES = {
        "small": "cpx21",    # 3 vCPU, 4 GB RAM, 80 GB NVMe (~€0.010/hr)
        "medium": "cpx31",   # 4 vCPU, 8 GB RAM, 160 GB NVMe (~€0.019/hr)
        "large": "cpx51",    # 16 vCPU, 32 GB RAM, 360 GB NVMe (~€0.045/hr)
        "arm_large": "cax41",# 16 Arm, 32 GB RAM, 320 GB NVMe (~€0.038/hr)
    }

    def __init__(self, config: dict | None = None, opener: Any = None):
        self.config = config or {}
        self.base_url = self.config.get("base_url", "https://api.hetzner.cloud/v1")
        self.token = self.config.get("token") or os.environ.get("HCLOUD_TOKEN")
        self.location = self.config.get("location", "nbg1")
        self.image = self.config.get("image", "ubuntu-24.04")
        self.ssh_key = self.config.get("ssh_key")
        self.timeout_seconds = int(self.config.get("timeout_seconds", 3600))
        self.opener = opener or urllib.request.urlopen
        self._watchdogs: dict[str, threading.Timer] = {}

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.token:
            raise ValueError("Hetzner runner requires swarm_runners.hetzner.token or HCLOUD_TOKEN")
        url = self.base_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with self.opener(req, timeout=30) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def provision(self, job_spec: dict) -> str:
        raise NotImplementedError

    def stream_telemetry(self, runner_id: str, callback: Callable) -> None:
        raise NotImplementedError

    def collect_results(self, runner_id: str) -> dict:
        raise NotImplementedError

    def destroy(self, runner_id: str) -> bool:
        raise NotImplementedError
```

Wire into `synlynk/runners/manager.py`:
```python
        if "hetzner" in enabled or "hetzner" in runner_config:
            from synlynk.runners.hetzner import HetznerRunnerDriver
            self.drivers["hetzner"] = HetznerRunnerDriver(runner_config.get("hetzner", {}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runners_hetzner.py -v`  
Expected: PASS

---

### Task 2: Server Provisioning, Dynamic Sizing & Mock Unit Tests

**Files:**
- Modify: `synlynk/runners/hetzner.py`
- Modify: `tests/test_runners_hetzner.py`

- [ ] **Step 1: Write failing tests for provisioning and auto-sizing**

```python
# Add to tests/test_runners_hetzner.py
from io import BytesIO
import json
import urllib.response


class MockHTTPResponse:
    def __init__(self, data: dict, status: int = 200):
        self.body = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_hetzner_provisioning_constructs_correct_payload(monkeypatch):
    sent_requests = []

    def mock_opener(req, timeout=30):
        sent_requests.append(req)
        return MockHTTPResponse({
            "server": {
                "id": 998877,
                "name": "synlynk-lease-abc123",
                "status": "initializing",
                "server_type": {"name": "cpx31"},
                "public_net": {"ipv4": {"ip": "159.69.1.2"}},
            }
        })

    driver = HetznerRunnerDriver(config={"token": "test-token"}, opener=mock_opener)
    job_spec = {
        "runner_id": "synlynk-lease-abc123",
        "size": "medium",
        "task_count": 6,
        "env": {"SYNLYNK_LEASE_ID": "lease-abc123"},
    }
    server_id = driver.provision(job_spec)
    assert server_id == "998877"
    assert len(sent_requests) == 1
    req = sent_requests[0]
    assert req.method == "POST"
    assert req.full_url == "https://api.hetzner.cloud/v1/servers"
    body = json.loads(req.data.decode("utf-8"))
    assert body["name"] == "synlynk-lease-abc123"
    assert body["server_type"] == "cpx31"
    assert body["location"] == "nbg1"
    assert "user_data" in body
    assert "shutdown -h" in body["user_data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runners_hetzner.py -k test_hetzner_provisioning -v`  
Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `provision()` and cloud-init builder**

In `synlynk/runners/hetzner.py`:
- Implement `_build_user_data(runner_id, ttl_seconds, env)` generating a self-contained cloud-init script with OS watchdog (`shutdown -h +{ttl_minutes}`) and container/worktree setup.
- Implement server type resolution based on `size` or `task_count`:
  - 1–3 tasks: `cpx21`
  - 4–8 tasks: `cpx31`
  - 9+ tasks: `cpx51`
- Issue POST `/servers` and return `str(server["id"])`.
- Arm local fallback watchdog timer.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runners_hetzner.py -k test_hetzner_provisioning -v`  
Expected: PASS

---

### Task 3: Watchdogs, Teardown & Results Harvesting

**Files:**
- Modify: `synlynk/runners/hetzner.py`
- Modify: `tests/test_runners_hetzner.py`

- [ ] **Step 1: Write failing tests for destroy and results collection**

```python
# Add to tests/test_runners_hetzner.py
def test_hetzner_destroy_issues_delete_request():
    deleted_urls = []

    def mock_opener(req, timeout=30):
        deleted_urls.append(req.full_url)
        return MockHTTPResponse({"action": {"command": "delete_server", "status": "success"}})

    driver = HetznerRunnerDriver(config={"token": "test-token"}, opener=mock_opener)
    driver._watchdogs["998877"] = threading.Timer(100, lambda: None)
    success = driver.destroy("998877")
    assert success is True
    assert deleted_urls == ["https://api.hetzner.cloud/v1/servers/998877"]
    assert "998877" not in driver._watchdogs


def test_hetzner_collect_results_computes_telemetry():
    def mock_opener(req, timeout=30):
        return MockHTTPResponse({
            "server": {
                "id": 998877,
                "name": "synlynk-lease-abc123",
                "status": "running",
                "server_type": {"name": "cpx51", "cores": 16, "memory": 32},
                "created": "2026-11-18T10:00:00Z",
            }
        })

    driver = HetznerRunnerDriver(config={"token": "test-token"}, opener=mock_opener)
    results = driver.collect_results("998877")
    assert results["server_id"] == 998877
    assert results["server_type"] == "cpx51"
    assert results["vcpus"] == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runners_hetzner.py -k "test_hetzner_destroy or test_hetzner_collect" -v`  
Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `destroy()`, `collect_results()`, and `stream_telemetry()`**

In `synlynk/runners/hetzner.py`:
- `destroy(runner_id)`: Cancels watchdog timer, executes `DELETE /servers/{runner_id}`, handles HTTP 404 cleanly (already destroyed), returns boolean.
- `collect_results(runner_id)`: Fetches server metadata, parses timestamps, calculates active runtime and raw estimated cost, returns structured receipt dictionary.
- `stream_telemetry(runner_id, callback)`: Connects to NATS relay telemetry subject or polls Hetzner server actions.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runners_hetzner.py -v`  
Expected: ALL PASS

---

### Task 4: Vertical Swarm Host Worktree Striping & Sizing Logic

**Files:**
- Modify: `synlynk/swarm.py`
- Modify: `tests/test_swarm.py`

- [ ] **Step 1: Write failing test for vertical host sizing calculation**

```python
# Add to tests/test_swarm.py
from synlynk.swarm import calculate_vertical_host_size


def test_calculate_vertical_host_size():
    assert calculate_vertical_host_size(1) == "cpx21"
    assert calculate_vertical_host_size(3) == "cpx21"
    assert calculate_vertical_host_size(4) == "cpx31"
    assert calculate_vertical_host_size(8) == "cpx31"
    assert calculate_vertical_host_size(9) == "cpx51"
    assert calculate_vertical_host_size(16) == "cpx51"
    assert calculate_vertical_host_size(32) == "cpx51"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_swarm.py -k test_calculate_vertical_host_size -v`  
Expected: FAIL with `ImportError` or `AttributeError`

- [ ] **Step 3: Implement sizing logic and lease lifecycle orchestration**

In `synlynk/swarm.py`:
- Add `calculate_vertical_host_size(task_count: int) -> str`.
- Implement `SwarmLease` dataclass tracking `lease_id`, `epic_id`, `driver`, `node_ids`, `status`, and `started_at`.
- Add `cmd_swarm_lease_dispatch()` packaging the milestone tasks into worktree specs, resolving host sizing, and provisioning via `RunnerManager`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_swarm.py -k test_calculate_vertical_host_size -v`  
Expected: PASS

---

### Task 5: CLI Wiring & FinOps Telemetry Event Emission

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `synlynk/swarm.py`
- Modify: `tests/test_swarm.py`

- [ ] **Step 1: Write failing test for CLI `swarm lease` commands**

```python
# Add to tests/test_swarm.py
import subprocess
import sys


def test_cli_swarm_lease_help():
    result = subprocess.run(
        [sys.executable, "-m", "synlynk.cli", "swarm", "lease", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--epic" in result.stdout
    assert "--size" in result.stdout
    assert "--driver" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_swarm.py -k test_cli_swarm_lease_help -v`  
Expected: FAIL with `error: invalid choice: 'lease'`

- [ ] **Step 3: Wire `swarm lease` subparsers in `synlynk/cli.py` and event emission**

In `synlynk/cli.py`:
- Register `lease` subparser under `swarm`:
  - `lease` with subcommands: `dispatch`, `list`, `destroy`.
- In `synlynk/swarm.py`:
  - On lease completion, emit `milestone_lease_completed` event onto the event bus via `RelayBroker` with active seconds and hardware metadata for consumption by [gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_swarm.py -k test_cli_swarm_lease_help -v`  
Expected: PASS

---

### Task 6: Full Regression Verification Suite

**Files:**
- Run: `pytest tests/test_runners_hetzner.py tests/test_swarm.py tests/test_relay_hub.py`
- Run: `synlynk pr check`

- [ ] **Step 1: Run comprehensive local test suite**
- [ ] **Step 2: Verify zero mandatory dependency violations**
- [ ] **Step 3: Run `synlynk pr check` to attest gates**
