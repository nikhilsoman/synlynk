# Design Spec: Automated Acceptance & Multi-Node Soak Testing Framework via OrbStack VMs & Docker

**Date:** 2026-09-20  
**Status:** In Review (Spec Approved by Panel, Awaiting Nikhil Sign-off)  
**Decision Record:** [`project-docs/decisions/2026-09-20-automated-acceptance-and-multi-node-soak.md`](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-09-20-automated-acceptance-and-multi-node-soak.md) (`dec-c830f41c`)  
**Authors:** [@nikhilsoman], [@claude], [@codex], [@agy], [@grok]  
**Relates to:** Wave 1 (`#1697`), Wave 2 (`#1698`), Wave 3 (`#1703`), Wave 4 (`#1708`)  

---

## 1. Executive Summary & Problem Statement

Synlynk has evolved from a single-process tool into a distributed, multi-agent, peer-to-peer orchestrator featuring:
- **P2P Relay Event Bus over WebSockets / NATS** (`synlynk/relay.py`)
- **Distributed Task Leases & Automatic Heartbeat Un-stranding in `state.db`** (`synlynk/jobs.py`)
- **AST Mesh Sibling Worktree Conflict Preemption** (`synlynk/mesh.py`)
- **3-Tier Identity Attribution Protocol (`<@user, role, harness>`)** (`synlynk/attribution.py`)

Unit tests and mock runners operate in a single OS process with one system clock, shared memory, and one filesystem. They cannot reproduce distributed failure modes:
1. Double lease claims and split-brain states across different machines.
2. Zombie lease un-stranding when a node dies unexpectedly (`kill -9`).
3. Relay event packet loss, latency, or loop storms across distinct IP addresses.
4. CWD-relative configuration leakage (e.g. issue #1228).
5. Subscription-based OAuth session collision when multiple test workers execute concurrently.

This specification establishes **`synlynk testbed`**: an automated, zero-host-pollution acceptance and soak testing framework that spins up isolated Linux environments on-demand, injects pinned Synlynk versions and credentials, executes real-world multi-node acceptance scenarios, verifies `state.db` invariants directly, and produces attested cryptographic receipts.

---

## 2. Architecture & System Topology

```
                                  ┌──────────────────────────────────────────────┐
                                  │           synlynk testbed CLI Runner         │
                                  │      (macOS Host / Linux CI Orchestrator)    │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                                ┌────────────────────────┴────────────────────────┐
                                ▼                                                 ▼
                    ┌────────────────────────┐                        ┌────────────────────────┐
                    │     OrbStack Driver    │                        │      Docker Driver     │
                    │   (Local macOS / VMs)  │                        │   (GitHub Actions CI)  │
                    └───────────┬────────────┘                        └───────────┬────────────┘
                                │                                                 │
        ┌───────────────────────┴───────────────────────┐                         │
        ▼                                               ▼                         ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│ Node 1: "@alice" (Dev)        │  P2P Mesh WS  │ Node 2: "@bob" (Architect)    │
│ IP: 192.168.139.213           │◄─────────────►│ IP: 192.168.139.214           │
│ Harness: Codex CLI (BYOK API) │               │ Harness: AGY (BYOK API)       │
│ Synlynk Target: v1.1.0-dev    │               │ Synlynk Target: v1.1.0-dev    │
│ state.db (Node-Local)         │               │ state.db (Node-Local)         │
└───────────────────────────────┘               └───────────────────────────────┘
```

---

## 3. Core Subsystems

### A. Dual-Backend Provider Abstraction (`synlynk/testbed/driver.py`)

To ensure both ultra-fast local execution on macOS (Apple Silicon) and headless portability in GitHub Actions CI, the testbed provides a lightweight driver interface:

```python
class TestbedDriver(Protocol):
    def create_node(self, node_id: str, base_image: str) -> NodeHandle: ...
    def exec_command(self, node_id: str, command: str, env: dict) -> ExecResult: ...
    def copy_file(self, node_id: str, src_path: str, dst_path: str) -> None: ...
    def get_ip_address(self, node_id: str) -> str: ...
    def inject_fault(self, node_id: str, fault_type: str) -> None: ... # kill, partition, delay
    def destroy_node(self, node_id: str) -> None: ...
```

1. **`OrbDriver` (Local macOS / Developer Machine):**
   - Drives `orbctl` to spin up lightweight Linux VMs (`ubuntu:noble` / `debian:bookworm`).
   - Uses native bridge IPs (`192.168.139.x`) for true multi-host networking.
   - Supports kernel-level network fault injection via `tc netem` and `iptables`.
   - Utilizes golden base image caching (`synlynk-testbed-base:v1`) for sub-2-second spinup.

2. **`DockerDriver` (Linux CI / GitHub Actions):**
   - Drives standard Docker containers sharing a dedicated bridge network.
   - Runs in headless CI pipelines without requiring virtualization extensions.

---

### B. Version & Release Ref Resolution (`synlynk/testbed/installer.py`)

The testbed allows exact targeting of Synlynk versions across individual nodes:

| Target Flag | Resolution Mechanism | Use Case |
| :--- | :--- | :--- |
| `--target staging` | Clones/installs commit `19fcd5ba` (Wave 1 v1.0.0 Dev Preview) | Verifying Wave 1 soak stability on clean OS |
| `--target unstable` | Clones/installs commit `284f810c` (Wave 2 v1.1.0-dev P2P Mesh) | Verifying Wave 2 mesh & distributed leases |
| `--target commit:<sha>` | Checks out specific commit SHA | Reproducing past regressions |
| `--target local` | Builds a local Python `.whl` from the current workspace and injects via `orbctl push` | Testing uncommitted feature branches before merge |

---

### C. Multi-Identity & Credential Strategy (`synlynk/testbed/identities.py`)

#### The Problem:
Interactive OAuth subscription flows (ChatGPT Plus / Claude Pro / Gemini Advanced) require interactive browser clicks, maintain single-session state, and cannot be dynamically provisioned for automated test workers.

#### The Solution:
1. **Headless Environment API Keys (BYOK):**
   - Automated test nodes run with explicit API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`).
   - In testbed mode, harnesses invoke non-interactive headless contracts.
2. **Synthetic 3-Tier Identity Matrix:**
   - Each VM node is provisioned with a clean Git identity and synlynk attribution:
     - **Node 1:** `<@alice, dev, codex>` (`user.name="Alice Dev"`, `user.email="alice@test.synlynk"`)
     - **Node 2:** `<@bob, architect, agy>` (`user.name="Bob Architect"`, `user.email="bob@test.synlynk"`)
     - **Node 3:** `<@charlie, qa, grok>` (`user.name="Charlie QA"`, `user.email="charlie@test.synlynk"`)

---

### D. Direct `state.db` Invariant Assertions

Unlike brittle assertions that read stdout labels or regex match terminal text, the testbed asserts directly against SQLite `state.db` relational invariants across all nodes:

1. **Mutual Exclusion Invariant:** For any given `story_id`, at most one active lease row (`status = 'active'` and `expires_at > CURRENT_TIMESTAMP`) may exist across the mesh.
2. **Crash Recovery Invariant:** When Node 1 (`@alice`) is killed via `SIGKILL`, its active lease must transition to un-stranded upon Node 2's `synlynk story reclaim` pass without orphan locks.
3. **P2P Relay Invariant:** All events published on Node 1 must be received by Node 2 with identical `event_id`, valid checksum, and deduplicated loop counters.
4. **AST Mesh Preemption Invariant:** Concurrent sibling worktrees modifying the same AST symbol must evaluate to `status = 'CONFLICT'` with `severity = 'CRITICAL'`.

---

## 4. Test Tiers & Execution Scenarios

### Tier 1: Acceptance & Smoke Suite (Duration: ~3–5 min)
Executed before release tags and as a local pre-push gate:
1. **Scenario 1.1 (Brownfield Coldstart):** Fresh VM -> installs prerequisites -> clones target unmanaged repo (`pbmr`) -> runs `synlynk init --brownfield` -> asserts living documentation and `state.db` created.
2. **Scenario 1.2 (Magic PR Engine):** Runs `synlynk heal --magic` -> asserts reproduction test generated, fix applied, and green PR branch created.
3. **Scenario 1.3 (P2P Mesh Handshake):** Spins up Node 1 and Node 2 -> registers peer -> publishes event -> asserts receipt on remote node.
4. **Scenario 1.4 (Lease Heartbeat Handover):** Node 1 acquires lease -> Node 1 killed -> Node 2 reclaims lease -> asserts clean transfer.

### Tier 2: Multi-Node Chaos & Soak Suite (Duration: 30–60 min)
Executed on scheduled nightly runs and pre-release soak ceremonies:
1. **Network Partition (Split-Brain Test):** `iptables` drops packets between Node 1 and Node 2 for 60 seconds; verifies nodes gracefully enter offline mode and reconcile state on reconnection.
2. **Clock Skew Simulation:** Adjusts system time by +45 minutes on Node 2; verifies lease expiration logic respects UTC timestamps.
3. **High-Churn Event Storm:** 1,000 relay messages/second across 5 mesh nodes; verifies zero memory leaks and sub-5ms routing latency.

---

## 5. CLI User Experience

```bash
# Run acceptance testbed locally with OrbStack VMs
synlynk testbed run --target unstable --scenario p2p-mesh

# Run full acceptance matrix across all 4 Waves
synlynk testbed matrix --target staging,unstable --json

# Run long soak chaos test with 5 nodes
synlynk testbed soak --nodes 5 --duration 30m --chaos kill,partition

# Inspect running testbed nodes
synlynk testbed status

# Teardown and clean all test VMs/containers
synlynk testbed clean --force
```

---

## 6. Attestation & Receipt Output

Upon completion, `synlynk testbed` outputs an attested JSON receipt:

```json
{
  "receipt_id": "rcpt-7f89b1c2",
  "timestamp": "2026-09-20T08:15:00Z",
  "target_version": "v1.1.0-dev (commit 284f810c)",
  "driver": "orbstack",
  "nodes_created": [
    {"node_id": "testbed-node-1", "ip": "192.168.139.213", "identity": "<@alice, dev, codex>"},
    {"node_id": "testbed-node-2", "ip": "192.168.139.214", "identity": "<@bob, architect, agy>"}
  ],
  "scenarios_executed": [
    {"name": "brownfield_init", "duration_seconds": 18.4, "status": "PASSED"},
    {"name": "p2p_relay_mesh", "duration_seconds": 24.1, "status": "PASSED"},
    {"name": "task_lease_recovery", "duration_seconds": 31.0, "status": "PASSED"}
  ],
  "invariants_verified": {
    "lease_mutual_exclusion": true,
    "zero_orphan_running_rows": true,
    "relay_deduplication": true
  },
  "overall_verdict": "PASSED",
  "signature": "ed25519:3f9a..."
}
```

---

## 7. Implementation Plan

| Phase | Deliverable | Assigned Harness / Role | Est. Time |
| :--- | :--- | :---: | :---: |
| **Phase 1** | **Testbed Driver & Orb/Docker Subprocess Layer** (`synlynk/testbed/driver.py`) | `codex` / `infra` | 40 min |
| **Phase 2** | **Version Installer & Wheel Packaging** (`synlynk/testbed/installer.py`) | `codex` / `core` | 30 min |
| **Phase 3** | **Synthetic Identity & Credential Vault** (`synlynk/testbed/identities.py`) | `agy` / `architecture` | 25 min |
| **Phase 4** | **Scenario Runner & Invariant Asserter** (`synlynk/testbed/scenarios.py`) | `codex` / `qa` | 45 min |
| **Phase 5** | **CLI Integration & Receipt Generator** (`synlynk/testbed/cli.py`) | `agy` / `dev` | 25 min |

---

## 8. Verification & Acceptance Criteria

1. `synlynk testbed run --scenario p2p-mesh` spins up 2 fresh OrbStack VMs, installs Synlynk at `--target unstable`, links them over WebSockets, executes task lease handover after a `SIGKILL` fault, and cleans up VMs in < 4 minutes total.
2. Verified 100% zero host environment pollution (no leftover files, processes, or ports on macOS host).
3. Produces green attested receipt `testbed-receipt-*.json`.
