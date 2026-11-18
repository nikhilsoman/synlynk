# Hetzner Cloud Swarm Runner Driver & Vertical Milestone Host Orchestration — Design Spec

**Status:** Draft, pending user review  
**Issue:** [gh:#5360](https://github.com/nikhilsoman/synlynk/issues/5360) (Follow-on to gh:#1326, gh:#1341; paired with Monetization Epic [gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359))  
**Date:** 2026-11-18  
**Author:** AGY (`agy-2.x`)  
**Domain:** `platform` · `backend`  
**Governing Goal:** `arc-goal-01C3FA0F` (Theme 6: Hetzner Cloud Swarm Runner & Vertical Milestone Host Orchestration; corrected 2026-11-18 from a stale `goal-d5323df6` reference that was never created in `goals` — see gh:#5373)  
**Story ID:** `story-76f56329`  

---

## 1. Executive Summary & Intent

Synlynk's multi-agent swarms require remote, on-demand compute infrastructure to execute complex milestone builds, multi-task epics, and empirical matrix verifications without bogging down developer laptops. While existing runner drivers support local processes and Fly.io microVMs, neither meets the requirements for cost-effective, high-velocity, multi-task milestone execution.

This specification designs the **Hetzner Cloud Swarm Runner Driver (`HetznerRunnerDriver`)** and the **Vertical Swarm Host Orchestration Pattern** for the Milestone Leaser.

### Core Objectives
1. **Unmatched Price-to-Performance Workhorse:** Integrate Hetzner Cloud (`hcloud`) as Synlynk's primary milestone runner, achieving 16-vCPU/32-GB execution for ~€0.045/hour (orders of magnitude cheaper than hyperscaler Fargate/EC2).
2. **Impermeable Workspace Isolation:** Enforce hardware-level virtualization (KVM) per lease with zero disk/memory leakage across successive runs. Reject multi-tenant container pools.
3. **High Velocity without Idle Waste:** Solve the "straggler/idle tail" problem using a **Two-Tier Topology**:
   - *Tier 1 (Default):* High-core single-tenant **Vertical Swarm Host** using native git worktree parallelism on local NVMe.
   - *Tier 2 (Massive Epics):* Striped multi-node swarm using an **Auto-Draining NATS JetStream Queue** where early-finishing nodes self-destruct immediately.
4. **Dual Transport Protocol:** Primary zero-leak workspace sync over encrypted NATS Relay streams; fallback to scoped ephemeral Git deploy tokens.
5. **Decoupled FinOps Seam:** Emit structured hardware and duration telemetry for consumption by the monetization and wallet billing engine ([gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359)).

---

## 2. Architectural Principles & Isolation Model

### 2.1 Rejection of Shared Warm Container Pools
We evaluated maintaining a pool of warm bare-metal/VPS instances hosting multiple Docker/Podman containers across different workspace leases. This approach was rejected due to:
- **Data & Prompt Leakage:** Shared `/proc`, kernel memory, residual temp files in `/tmp`, and unmapped disk blocks present unacceptable data privacy risks between separate client workspaces.
- **Noisy Neighbors:** Runaway compilations or unconstrained agent loops starve concurrent tasks.
- **Complex Bin-Packing Daemon:** Requires developing and maintaining stateful queue schedulers, heartbeat daemons, and fragile volume sanitization routines.

### 2.2 Dedicated Single-Tenant KVM Virtual Machines
Every milestone lease provisions a **fresh, dedicated Hetzner Cloud VM**:
- **Hardware Boundary:** Strict KVM hypervisor isolation. Each lease gets its own isolated Linux kernel, memory space, network stack, and virtualized NVMe disk.
- **Cryptographic & Hardware Zeroing:** When the milestone completes or times out, the host is terminated via Hetzner's `DELETE /servers/{id}` API. Hetzner zero-fills the underlying NVMe blocks before reallocating storage.
- **Zero Idle Burn:** Compute costs exist strictly for the active duration of the milestone (billed per second, 1-minute minimum). Idle infrastructure cost when no milestones are running is exactly **€0.00**.

---

## 3. Two-Tier Swarm Execution Topology

To achieve maximum concurrency without suffering from the idle-tail tax (where fast tasks finish early and their nodes sit idle waiting for slow tasks), Synlynk implements two distinct operational tiers:

```
                                    MILESTONE DISPATCH
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
       Tier 1: Vertical Swarm Host                     Tier 2: Dynamic Queue-Draining
         (Default for 85–90% of Epics)                   (For Massive 20+ Task Epics)
   ┌─────────────────────────────────────────┐     ┌─────────────────────────────────────────┐
   │ 1 Dedicated High-Core VM (e.g. 16 vCPU) │     │ NATS JetStream Distributed Work Queue   │
   │  ┌───────────┐ ┌───────────┐ ┌────────┐ │     │                                         │
   │  │Worktree 1 │ │Worktree 2 │ │Worktree│ │     │  [Node 1]     [Node 2]     [Node 3]     │
   │  │ (Codex)   │ │  (Agy)    │ │   3    │ │     │ (Busy 14m)   (Drains 3m)  (Drains 5m)   │
   │  └───────────┘ └───────────┘ └────────┘ │     │      │            │            │        │
   │ Local NVMe speed, shared local state.db │     │      │       [Auto-Destruct] [Auto-Destruct]
   │ Whole host destroyed when epic finishes.│     │      │     (Terminates early) (Terminates)  │
   └─────────────────────────────────────────┘     └─────────────────────────────────────────┘
```

### 3.1 Tier 1: The Vertical Swarm Host (Default)
Instead of distributing 8 tasks across 8 small VMs, Synlynk provisions **one vertically-sized high-performance VM** matching the epic's task count.

#### Hardware Sizing Matrix
| Milestone Size | Parallel Tasks | Hetzner Server Type | vCPUs | RAM | NVMe Disk | Hourly Rate | Est. 1-Hr Cost |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Small** | 1 – 3 | `cpx21` | 3 x86 | 4 GB | 80 GB | ~€0.010/hr | **€0.010** |
| **Medium** | 4 – 8 | `cpx31` | 4 x86 | 8 GB | 160 GB | ~€0.019/hr | **€0.019** |
| **Large** | 8 – 16 | `cpx51` | 16 x86 | 32 GB | 360 GB | ~€0.045/hr | **€0.045** |
| **Heavy / Arm**| 16 – 32 | `cax41` | 16 Arm | 32 GB | 320 GB | ~€0.038/hr | **€0.038** |

#### Concurrency & Execution Mechanics
1. **Native Worktree Parallelism:** The host launches tasks in dedicated git worktrees (`worktrees/task-1`, `worktrees/task-2`, etc.) governed by Synlynk's orthogonal file check (`check_orthogonal_files()`).
2. **Zero Network Rebase Friction:** Tasks commit and test against local worktrees on NVMe. Local git merges and verification checks run instantaneously without network roundtrips.
3. **Dynamic Core Reallocation:** When Task 1 finishes in 2 minutes, its CPU cores automatically shift to accelerate the test runner or build process of concurrent Task 2. All 16 cores remain saturated.
4. **Single Teardown:** Once all tasks pass verification and the final PR/commit bundle is emitted, the entire host is wiped and destroyed.

### 3.2 Tier 2: Striped Multi-Node Queue-Drain (Massive Epics)
For massive epics exceeding 16–20 concurrent tasks or heavy browser E2E test matrices:
1. **Ephemeral NATS Queue:** Tasks publish to `synlynk.<ws>.milestone.<epic_id>.tasks`.
2. **Pull-Based Worker Nodes:** $N$ nodes pull tasks dynamically.
3. **Auto-Destruct on Drain (Eliminating the Idle Tail):**
   ```python
   # Inside ephemeral worker loop
   task = nats_queue.pull(timeout_seconds=60)
   if task is None:
       # Queue is completely drained; early tasks are done
       logger.info("Milestone queue empty. Self-destructing node to stop billing.")
       trigger_node_self_destruct()
   ```
   If Node 2 and Node 3 finish their tasks after 4 minutes while Node 1 runs a 15-minute task, **Nodes 2 and 3 destroy themselves immediately**, completely eliminating idle-tail waste.

---

## 4. Dual Transport Protocol (Zero-Leak Workspace Sync)

To ensure workspace code, secrets, and history are never leaked or persisted remotely:

```
                      ┌──────────────────────────────────────┐
                      │    Workspace Sync Engine             │
                      │                                      │
                      │  Is NATS Hub Connected & Healthy?    │
                      └──────────────────┬───────────────────┘
                                         │
                        Yes ─────────────┴───────────── No (or large bundle)
                         │                                       │
                         ▼                                       ▼
             [ Primary: NATS Relay Hub ]            [ Fallback: Ephemeral Git Transport ]
             • Encrypted shallow git bundle         • Short-lived deploy key / token
             • Scoped state.db slice                • Ephemeral push to feat/milestone-lease/*
             • Direct stream via doc/artifact channel• Runner clones only --depth 1 of branch
             • Zero GitHub commit history leaked    • Key auto-revoked upon lease completion
```

### 4.1 Primary Path: NATS Relay Doc/Artifact Channel
1. **Sync In:**
   - Workspace creates a shallow git bundle of the target branch:
     `git bundle create /tmp/bundle.pack -1 HEAD`
   - Exports the governing epic slice of `state.db` (tasks, capability baselines, contracts).
   - Encrypts client-side using an ephemeral session key.
   - Streams over `synlynk.<ws>.doc.bundle` through the NATS Relay Hub into the runner's RAM disk (`/dev/shm/synlynk-workspace`).
2. **Execution:**
   - Runner unpacks bundle, initializes local git worktrees, and runs the swarm.
   - Telemetry, thoughts, and progress events stream back in real-time over NATS subject `synlynk.<ws>.agent.<harness>.<role>`.
3. **Sync Out:**
   - Verified commits and receipts are bundled and streamed back over `synlynk.<ws>.doc.bundle_receipt`.
   - Local workspace applies the verified commits. Remote runner executes `poweroff`.

### 4.2 Fallback Path: Ephemeral Scoped Git
1. If NATS is unreachable or bundle size exceeds 50 MB:
2. Synlynk mints a short-lived GitHub fine-grained PAT or deploy key with a 1-hour TTL, scoped strictly to the target repository.
3. Runner clones `git clone --depth 1 --single-branch -b feat/milestone-<id>`.
4. Upon task completion, runner pushes commits upstream, invalidates the token, and terminates.

---

## 5. Scale-to-Zero & Failure-Mode Watchdogs

To ensure no orphaned VMs generate runaway cloud costs, Synlynk enforces a three-layer fail-closed watchdog hierarchy:

```
┌────────────────────────────────────────────────────────┐
│ Layer 1: Host OS Hardware Watchdog                     │
│ Executed at VM boot in cloud-init:                     │
│   shutdown -h +<ttl_minutes>                           │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Layer 2: Process Shell Trap                            │
│ Executed in runner entrypoint:                         │
│   trap "synlynk relay emit runner_exited; poweroff" EXIT│
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Layer 3: Driver Supervisor (Client Side)               │
│ RunnerManager launches a daemon threading.Timer        │
│ If no completion event by TTL: driver.destroy(node_id) │
└────────────────────────────────────────────────────────┘
```

1. **Layer 1 (OS-Level):** Cloud-init issues `shutdown -h +{ttl}` upon boot. Even if the network disconnects or the agent process hangs, the Linux kernel shuts down the machine.
2. **Layer 2 (Process-Level):** Shell entrypoint registers `trap 'poweroff' EXIT`. The moment the swarm process exits (success or failure), poweroff is triggered.
3. **Layer 3 (Driver Supervisor):** `HetznerRunnerDriver` arms a background watchdog timer on the client machine. If the lease duration is exceeded without a receipt, it invokes `DELETE /servers/{id}` directly over the Hetzner REST API.

---

## 6. Hetzner Runner Driver Implementation Architecture

### 6.1 Class Contract (`synlynk/runners/hetzner.py`)
```python
class HetznerRunnerDriver(SwarmRunnerDriver):
    """Ephemeral Hetzner Cloud VM runner using Python stdlib HTTP."""

    def __init__(self, config: dict | None = None, opener: Any = None):
        self.config = config or {}
        self.base_url = "https://api.hetzner.cloud/v1"
        self.token = self.config.get("token") or os.environ.get("HCLOUD_TOKEN")
        self.location = self.config.get("location", "nbg1") # Nuremberg (or fsn1, hel1, ash)
        self.image = self.config.get("image", "ubuntu-24.04")
        self.ssh_key = self.config.get("ssh_key")
        self.timeout_seconds = int(self.config.get("timeout_seconds", 3600))
        self._watchdogs: dict[str, threading.Timer] = {}

    def provision(self, job_spec: dict) -> str:
        """Create a dedicated Hetzner Cloud VM scaled to the job requirements."""
        ...

    def stream_telemetry(self, runner_id: str, callback: Callable) -> None:
        """Stream logs over NATS Relay or polling console output."""
        ...

    def collect_results(self, runner_id: str) -> dict:
        """Query server status, metrics, and completion receipt."""
        ...

    def destroy(self, runner_id: str) -> bool:
        """Issue DELETE /servers/{id} to terminate VM and zero NVMe storage."""
        ...
```

### 6.2 FinOps Telemetry Seam (Interface for gh:#5359)
When a lease finishes, `HetznerRunnerDriver.collect_results()` generates a structured lease completion receipt:
```json
{
  "event": "milestone_lease_completed",
  "lease_id": "lease-8f2b1a",
  "workspace_id": "ws-main",
  "epic_id": "epic-c1829f",
  "provider": "hetzner",
  "server_id": 4829104,
  "server_type": "cpx51",
  "vcpus": 16,
  "ram_gb": 32,
  "location": "nbg1",
  "provisioned_at": "2026-11-18T12:00:00Z",
  "destroyed_at": "2026-11-18T12:45:12Z",
  "active_seconds": 2712,
  "raw_compute_cost_eur": 0.0339,
  "exit_code": 0,
  "tasks_completed": 8
}
```
This payload is emitted onto the local event bus (`milestone_lease_completed`) and written to `state.db`. The future billing engine ([gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359)) consumes this event to calculate wallet deductions and margin markup without coupling to the runner code.

---

## 7. Configuration Schema (`.synlynk/config.json`)

```json
{
  "swarm_runners": {
    "default": "hetzner",
    "enabled": ["local", "fly", "hetzner"],
    "timeout_seconds": 3600,
    "hetzner": {
      "token": "env:HCLOUD_TOKEN",
      "location": "nbg1",
      "default_server_type": "cpx31",
      "ssh_key": "synlynk-ephemeral-key"
    },
    "fly": {
      "app": "synlynk-swarm",
      "token": "env:FLY_API_TOKEN"
    }
  }
}
```

---

## 8. CLI Interface & Workflows

### 8.1 Command Syntax
```bash
# Lease a dedicated vertical host for an epic
synlynk swarm lease --epic <epic_id> [--driver hetzner] [--size auto|small|medium|large]

# Striped multi-node execution for massive epics
synlynk swarm lease --epic <epic_id> --nodes 4 --drain-on-empty

# Inspect active leases
synlynk swarm lease list

# Manually tear down an active lease
synlynk swarm lease destroy <lease_id> [--all]
```

---

## 9. Testing & Verification Strategy

1. **Unit Testing (`tests/test_runners_hetzner.py`):**
   - Mock Hetzner Cloud REST API responses using Python `urllib` test openers.
   - Verify server provisioning payload construction (cloud-init user-data, labels, server types).
   - Verify watchdog timer triggers `destroy()` if timeout is reached.
   - Verify clean error handling on Hetzner API rate limits (HTTP 429) and stock exhaustion (HTTP 422).
2. **Integration Verification (Mock / Staging):**
   - Test vertical host auto-sizing: 2 tasks $\rightarrow$ `cpx21`, 6 tasks $\rightarrow$ `cpx31`, 12 tasks $\rightarrow$ `cpx51`.
   - Test NATS encrypted bundle pack/unpack roundtrip.
   - Test queue-drain self-destruct simulation.
3. **Regression Safety:**
   - Ensure zero new mandatory dependencies: stdlib HTTP only.
   - Core CLI imports must execute cleanly without `hcloud` credentials present.

---

## 10. Forward Compatibility & Relationships

- **Theme 6 (Horizon 2 / `v0.39.0`):** Completes the compute driver requirements for Cloud Swarms.
- **Monetization & Wallets ([gh:#5359](https://github.com/nikhilsoman/synlynk/issues/5359)):** Consumes the `milestone_lease_completed` event emitted by this driver to calculate wallet balance debits and customer margins.
- **Personal Hosted Relay ([PR #5358](https://github.com/nikhilsoman/synlynk/pull/5358)):** Reuses the hardened NATS `HubAdapter` for secure bundle and telemetry streaming between the local workspace and the remote Hetzner node.
