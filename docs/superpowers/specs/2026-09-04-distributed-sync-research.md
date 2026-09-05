# Research: Distributed state.db Synchronization Protocols & Enterprise Cost Aggregation

**Date:** 2026-09-04  
**Author:** Agy (Gemini)  
**Status:** Research & Architectural Evaluation  
**Issue Reference:** Closes #1402  
**Story Reference:** story-d58e5033  

---

## 1. Executive Summary & Context

`synlynk` is designed as a single-file, zero-dependency, local-first developer CLI and multi-agent coordination harness. Currently, all coordination state, product management metadata, and telemetry live in a single SQLite database:
- **Canonical Path:** `~/.synlynk/projects/<repo-hash>/state.db` (or `.synlynk/state.db` within sandboxes).
- **Storage Model:** Single SQLite instance configured with WAL mode (`PRAGMA journal_mode=WAL`), foreign keys (`PRAGMA foreign_keys=ON`), and application-level schema migrations (`synlynk/db.py`).
- **Data Domains in `state.db`:**
  1. *Product State:* `stories`, `backlog_items`, `roadmap_arcs`, `roadmap_phases`, `decisions`.
  2. *Agent Governance & Telemetry:* `sessions`, `events`, `daemon_jobs`, `harness_quotas`, `harness_reservations`, `credit_grants`.
  3. *Messaging & Inter-Agent Bus:* `relay_events`, `relay_mailbox`, `swarm_runners`.
  4. *Cost & Token Ledger:* `cost_entries` (`input_tokens`, `output_tokens`, `cache_read_tokens`, `total_cost_usd`, `actual_usd`, `payment_mode`).

### The Distributed Challenge (#1402)
As `synlynk` scales from a single-developer workstation to **distributed enterprise fleets**:
- **Multi-Node Autonomous Swarms:** Agents run in ephemeral cloud containers (e.g., Fly.io machines, AWS ECS/Fargate, Kubernetes pods) and headless CI/CD pipelines.
- **Collaborative Multi-Human Workgroups:** Multiple engineers work concurrently on separate branches and machines, dispatching local harnesses (`claude`, `agy`, `codex`, `grok`).
- **Cross-Worktree & Cross-Host State Divergence:** Worktrees and sandboxed containers operate with disjoint filesystems, creating split-brain ledgers where stories, reservation locks, and cost metrics diverge.
- **Enterprise Cost Blind Spots:** Enterprise FinOps teams require continuous, authoritative rollups of model usage across thousands of agent dispatches, multi-cloud accounts (Vertex AI, Anthropic Direct, Azure OpenAI), and diverse projects without risking single-machine database lock contention or silent loss of spend metrics.

This document researches three primary distributed database synchronization protocols (**LiteFS**, **CRDTs / cr-sqlite**, and **gRPC Relay**), analyzes **enterprise cost aggregation patterns**, presents a comprehensive tradeoff matrix, and formulates a recommended phased architecture for `synlynk`.

---

## 2. Distributed Synchronization Protocols Deep Dive

### 2.1 LiteFS: FUSE-Based Physical WAL Replication

#### Architectural Overview
LiteFS (developed by Fly.io) is a distributed file system implemented as a user-space FUSE (Filesystem in Userspace) layer. It sits transparently between SQLite and the operating system's disk I/O interface.

```
+-------------------------------------------------------------+
|                      synlynk Process                        |
|   (Python sqlite3 connection: PRAGMA journal_mode = WAL)    |
+-------------------------------------------------------------+
                              |
                              v (standard POSIX filesystem syscalls)
+-------------------------------------------------------------+
|                    LiteFS FUSE Mount                        |
|   - Intercepts SQLite WAL write transactions                |
|   - Packages changes into LTX (LiteFS Transaction) files    |
|   - Tracks transaction IDs (txid)                           |
+-------------------------------------------------------------+
        |                                       ^
        | Replication Stream (LTX chunks)       | Pull updates
        v                                       |
+-------------------+                   +-------------------+
| LiteFS Primary    |=== gRPC stream ==>| LiteFS Replica(s) |
| (Holds lease via  |                   | (Read-only query  |
| Consul/etcd/Cloud)|                   |  endpoints)       |
+-------------------+                   +-------------------+
```

- **Transaction Packaging:** LiteFS intercepts SQLite transactions when SQLite commits to the Write-Ahead Log (WAL). It packages WAL frame additions into immutable, compressed **LTX files** (checksummed boundary files representing sequential monotonic transactions).
- **Leadership & Leases:** Uses a single-primary, multi-replica architecture. A primary node acquires a distributed lease using a consensus store (such as Consul, etcd, or LiteFS Cloud lease API). Only the primary may execute write transactions.
- **Write Forwarding & Read-Your-Writes:** Replicas receive streaming LTX frames from the primary. Read queries execute against local SQLite snapshots with near-zero latency. When a replica attempts a write, LiteFS either rejects it or requires application-level write-forwarding (via an HTTP reverse proxy using `fly-replay` or internal gRPC redirection to the leaseholder). LiteFS tracks the latest applied transaction ID (`txid`), ensuring clients can verify read-your-writes consistency before reading after a delegated write.

#### Strengths for synlynk
1. **Zero SQL Schema Modifications:** Operates entirely at the filesystem layer. `synlynk`'s existing 3,500-line schema in `synlynk/db.py` requires zero DDL changes or ORM refactoring.
2. **Absolute ACID & Snapshot Isolation:** Preserves standard SQLite serializability and transactional semantics.
3. **High-Performance Local Reads:** Read queries execute directly against memory-mapped local disk blocks without network overhead.

#### Failure Modes & Limitations in synlynk
1. **Single-Writer Bottleneck:** In a multi-agent system, multiple agents on different machines or worktrees frequently update task statuses and log token metrics simultaneously. Under LiteFS, all writes must bottleneck through the single leaseholder.
2. **Platform Portability & Sandbox Obstacles:**
   - LiteFS relies on Linux FUSE (`/dev/fuse`). It cannot run natively on macOS workstations without commercial third-party extensions (macFUSE), which conflicts with `synlynk`'s primary developer base on macOS arm64.
   - Restrictive sandboxes (such as Docker containers without `SYS_ADMIN` capability or gVisor/firecracker runtimes) block FUSE mounts, breaking `synlynk`'s sandboxing goals (`goal-abecd18c`).
3. **Split-Brain & Partition Vulnerabilities:** If network connectivity between a remote worker and the consensus store drops, the worker cannot write, halting local agent dispatch unless complex offline fallback modes are engaged.

---

### 2.2 Conflict-Free Replicated Data Types (CRDTs) & `cr-sqlite`

#### Architectural Overview
CRDTs (Conflict-free Replicated Data Types) provide mathematically provable, eventual consistency across distributed nodes without requiring central coordination or active leader election. In the SQLite ecosystem, **`cr-sqlite`** (an open-source project by vlcn.io) transforms standard SQLite tables into Conflict-Free Replicated Relations (CRRs) via an official SQLite loadable C extension.

```
  Node A (Local Workstation)                     Node B (Cloud Swarm Pod)
+-------------------------------+              +-------------------------------+
| synlynk state.db (cr-sqlite)  |              | synlynk state.db (cr-sqlite)  |
| - Table: stories (as CRR)     |              | - Table: stories (as CRR)     |
| - Clock: Vector / HLC [A: 42] |              | - Clock: Vector / HLC [B: 18] |
+-------------------------------+              +-------------------------------+
         \                                             /
          \                                           /
           \---> [Changeset Delta: crsql_changes] <--/
                 - table: 'stories'
                 - pk: 'story-d58e5033'
                 - cid: 'readiness'
                 - val: 'in_progress'
                 - col_version: 12
                 - db_version: 43
                 - site_id: 0xDEADBEEF
```

- **Replication Mechanics:** `cr-sqlite` tracks changes using a hidden metadata table (`crsql_changes`). Each column update increments a local Hybrid Logical Clock (HLC) or version counter.
- **Delta-State Replication:** Nodes query `SELECT * FROM crsql_changes WHERE db_version > ? AND site_id != ?`. Only mutated columns and their version vectors are transmitted over the wire.
- **Conflict Resolution Rules:**
  - **LWW-Element-Set (Last-Write-Wins):** Applied at the column level. If Node A updates `status = 'in_progress'` at timestamp T1 and Node B updates `assigned_agent = 'codex'` at T2, both updates merge seamlessly without overwriting each other. If both update `status` concurrently, the highest HLC value deterministically wins.
  - **PN-Counters (Positive-Negative Counters):** Used for numeric values like token consumption and credit balances, allowing concurrent additions and subtractions to merge without loss.
  - **Grow-Only Sets (G-Sets) / Observed-Removed Sets (OR-Sets):** Ideal for append-only logs (`events`, `devlog_entries`, `relay_events`).

#### Mapping synlynk Tables to CRDT Primitives

| `state.db` Table | Proposed CRDT Primitive | Conflict Resolution Strategy |
| :--- | :--- | :--- |
| `stories`, `backlog_items` | Column-level LWW-CRR | Monotonic state lattice (e.g., status transitions `open -> assigned -> ready -> done` cannot regress unless an explicit admin override flag is present). |
| `cost_entries` | Append-only G-Set + UUID PK | Zero conflict; every dispatch produces a unique `(job_id, recorded_at)` tuple. Merging is a pure set union. |
| `harness_quotas`, `credit_grants` | Distributed PN-Counter | Separate positive increments and negative decrements, synchronized across nodes to track remaining budget. |
| `relay_events`, `relay_mailbox` | Causal Sequence / G-Set | Lamport timestamp ordering; duplicate event IDs dropped via idempotent primary keys. |
| `capability_ratings` | Multi-Value Register (MVR) / Bayesian Merge | Calibrated harness score updates merged using running weighted averages. |

#### Strengths for synlynk
1. **True Multi-Master & 100% Offline Capability:** Agents running on air-gapped dev laptops or transient cloud pods can commit writes locally to `state.db`. When network connectivity resumes, nodes exchange deltas and converge cleanly.
2. **Platform Neutrality:** As a SQLite loadable extension (`.dylib` / `.so`), `cr-sqlite` runs inside the standard Python `sqlite3` driver (`conn.enable_load_extension(True); conn.load_extension(...)`) without kernel FUSE or root daemon requirements.
3. **Granular Merge Semantics:** Prevents whole-row clobbering. Simultaneous edits to different fields of a story by different agents merge without human intervention.

#### Failure Modes & Limitations in synlynk
1. **Binary Compilation Matrix:** Compiling and distributing pre-built C extensions across macOS (ARM64 & x86_64), Linux (musl/glibc), and containerized sandboxes increases packaging and distribution complexity.
2. **Schema Invariant Anomalies:** Eventual consistency does not prevent temporary constraint violations (e.g., two nodes independently allocating the exact same remaining quota tokens before a sync occurs).
3. **Tombstone & Storage Bloat:** Deletions require tracking tombstone records in `crsql_changes`. Without periodic distributed compaction and garbage collection, local databases grow steadily over time.

---

### 2.3 gRPC Relay Mesh: Strongly-Typed Event & Mutation Streaming

#### Architectural Overview
The gRPC Relay model builds upon and modernizes `synlynk`'s existing background daemon and relay infrastructure (`synlynk/relay.py`, `synlynk/daemon.py`). It replaces stateless HTTP polling and SSE broadcasts with a bidirectional, multiplexed, strongly-typed gRPC streaming protocol backed by Protocol Buffers (`proto3`).

```
+-----------------------------------------------------------------------------------+
|                             Enterprise Relay Mesh                                 |
|                                                                                   |
|  +--------------------+                     +--------------------+                |
|  | Synlynk Node A     |                     | Synlynk Node B     |                |
|  | (macOS Workstation)|                     | (Fly.io Worker Pod)|                |
|  +--------------------+                     +--------------------+                |
|            \                                            /                         |
|             \      Bi-directional gRPC Streaming       /                          |
|              \     (HTTP/2, mTLS, Protobuf Envelopes) /                           |
|               v                                      v                            |
|             +------------------------------------------+                          |
|             |          Synlynk gRPC Hub / Router       |                          |
|             |  - Client Authentication & RBAC (mTLS)   |                          |
|             |  - Channel & Mailbox Routing Table       |                          |
|             |  - Durable Outbox Store (Kafka/NATS/PG)  |                          |
|             |  - Stream Deduplication & Checkpointing  |                          |
|             +------------------------------------------+                          |
|                                   |                                               |
|                                   v                                               |
|             +------------------------------------------+                          |
|             |     Central FinOps Aggregation Engine    |                          |
|             |  (Real-time Token & Spend Rollup Pipeline|                          |
|             +------------------------------------------+                          |
+-----------------------------------------------------------------------------------+
```

#### Core Protocol Buffer Specification (Proposed)

```protobuf
syntax = "proto3";

package synlynk.relay.v1;

import "google/protobuf/timestamp.proto";

service SynlynkMeshService {
  // Bi-directional event bus for cross-agent signaling
  rpc StreamEvents(stream EventEnvelope) returns (stream EventEnvelope);

  // Streaming push of token consumption and execution telemetry
  rpc PushCostEntries(stream CostBatch) returns (CostAck);

  // Delta-sync for state database mutations
  rpc SyncDatabaseDeltas(stream MutationBatch) returns (stream MutationBatch);

  // Quota reservation negotiation
  rpc ReserveQuota(QuotaRequest) returns (QuotaResponse);
}

message EventEnvelope {
  string event_id = 1;
  string event_type = 2;
  google.protobuf.Timestamp timestamp = 3;
  ActorIdentifier sender = 4;
  ActorIdentifier recipient = 5;
  string payload_json = 6;
  string correlation_id = 7;
}

message ActorIdentifier {
  string workspace_id = 1;
  string member_id = 2;
  string agent_role = 3;
  string harness = 4;
  string job_id = 5;
}

message CostBatch {
  string batch_id = 1;
  string workspace_id = 2;
  string project_id = 3;
  repeated CostEntry entries = 4;
}

message CostEntry {
  string entry_id = 1;
  google.protobuf.Timestamp recorded_at = 2;
  string harness = 3;
  string agent_role = 4;
  string model = 5;
  int64 input_tokens = 6;
  int64 output_tokens = 7;
  int64 cache_read_tokens = 8;
  double estimated_cost_usd = 9;
  double actual_cost_usd = 10;
  string payment_mode = 11;
  string story_id = 12;
  string job_id = 13;
  string cost_center = 14;
}

message CostAck {
  string batch_id = 1;
  bool success = 2;
  int64 committed_entries = 3;
  string error_message = 4;
}

message MutationBatch {
  string source_node_id = 1;
  int64 cursor = 2;
  repeated RowMutation mutations = 3;
}

message RowMutation {
  string table_name = 1;
  string primary_key = 2;
  string operation = 3; // INSERT, UPDATE, DELETE
  string data_json = 4;
  int64 version = 5;
}

message QuotaRequest {
  string workspace_id = 1;
  string harness = 2;
  int64 requested_tokens = 3;
  double requested_usd = 4;
  int32 ttl_seconds = 5;
}

message QuotaResponse {
  bool granted = 1;
  string reservation_id = 2;
  int64 allocated_tokens = 3;
  double allocated_usd = 4;
  google.protobuf.Timestamp expires_at = 5;
}
```

#### Strengths for synlynk
1. **High Throughput & Low Latency:** HTTP/2 multiplexing allows hundreds of telemetry records and inter-agent messages to stream across a single persistent TCP connection with negligible overhead.
2. **Strict Contract & Fleet Interoperability:** Protobuf contracts ensure strict type-safety across diverse harness integrations (Python CLI, Go/Rust microservices, TypeScript web frontends).
3. **Resilience & Backpressure:** Built-in gRPC flow control prevents agent workers from overwhelming the central hub during high-volume swarm sweeps.

#### Failure Modes & Limitations in synlynk
1. **Central Server Dependency:** Requires a reachable relay hub. If workers lose network connectivity, inter-agent messaging halts unless a local store-and-forward outbox buffer is maintained.
2. **Not a Storage Engine:** gRPC is a transport layer, not a database. It must be paired with SQLite on the edge and a relational or event store on the hub to maintain persistent history.

---

## 3. Enterprise Cost Aggregation in synlynk

### 3.1 Limitations of the Current Local Cost Ledger
In `synlynk`, cost tracking is handled by `synlynk/costs.py` and stored in the `cost_entries` table in `state.db`. While effective for a single operator on one laptop, enterprise deployments reveal significant shortcomings:
1. **Isolated Data Silos:** When 20 developers and 50 CI runner pods execute agent jobs, each writes only to its local `~/.synlynk/.../state.db`. Organization-wide spend is invisible until manual out-of-band aggregation occurs.
2. **Quota Race Conditions:** Today's `harness_quotas` table uses local reservations (`harness_reservations`). If five nodes concurrently check the remaining  budget, all five may dispatch concurrently, resulting in a 5x budget overrun.
3. **Static Rate Cards:** LLM providers frequently adjust pricing (e.g., prompt caching tiers, batch API discounts, regional variations). Local hardcoded pricing dictionaries in `costs.py` drift from actual enterprise billing.

### 3.2 Enterprise Architecture: Hierarchical Multi-Tenant Rollup

To satisfy enterprise governance, cost aggregation must follow a multi-tier hierarchy:

```
[ Enterprise Organization: Acme Corp ]
  |-- Cost Center: Engineering (CC-104)
  |     |-- Project / Repository: synlynk-core
  |     |     |-- Epic: epic-job-truth-2026-08
  |     |     |     |-- Phase: Phase 2 (Distributed Mesh)
  |     |     |           |-- Story: story-d58e5033
  |     |     |                 |-- Job: job-7c8c84f5 (Agy dispatch)
  |     |     |                 |-- Job: job-836e13a4 (Codex dispatch)
  |-- Cost Center: Marketing (CC-208)
```

#### Architectural Components
1. **Local Outbox & Store-and-Forward:**
   - Dispatched jobs continue writing immediately to local `cost_entries`.
   - A local background worker tails new rows where `synced_to_enterprise = 0`, batches them, and pushes them via gRPC `PushCostEntries` to the enterprise collector.
   - If offline, records queue safely in local SQLite; upon reconnection, batches drain with exponential backoff.
2. **Dynamic Rate-Card Service:**
   - The central relay distributes normalized pricing tables during heartbeat checks, ensuring all agents calculate estimates using identical, up-to-date rate cards.
3. **Two-Phase Distributed Quota Reservation (2PC Reservation):**
   - Before a high-cost dispatch runs, the local node requests a temporary lease via `ReserveQuota(tokens, usd, ttl)`.
   - The central coordinator decrements the available enterprise quota pool.
   - Upon job completion, the node commits actual token usage via `PushCostEntries`, releasing unused reserved allocations.
4. **OpenTelemetry & FinOps Export Integration:**
   - The central aggregation engine converts incoming cost events into standard OpenTelemetry GenAI semantic metrics:
     - `gen_ai.client.token.usage` (attributes: `type: input|output|cache_read`, `model`, `agent_role`, `cost_center`).
     - `gen_ai.client.estimated_cost` (attributes: `currency: USD`, `payment_mode`).
   - Exports directly to Prometheus, TimescaleDB, and ClickHouse for consumption by Grafana, Datadog, or OpenCost.

---

## 4. Architectural Comparison & Tradeoff Matrix

| Criterion | LiteFS (Physical FUSE WAL) | CRDTs / cr-sqlite (Logical Delta) | gRPC Relay Mesh (Streaming Event Bus) | Centralized Postgres / Turso |
| :--- | :--- | :--- | :--- | :--- |
| **Consistency Model** | Strict Serializability (Primary), Read-Your-Writes (Replicas) | Eventual Consistency (Causal convergence via HLC) | Transport only (Eventual at storage sink) | Strong Consistency (ACID) |
| **Multi-Writer Support** | ❌ No (Single primary, writes must be forwarded) | ✅ Yes (Seamless concurrent multi-master writes) | ⚠️ N/A (Relies on central storage engine) | ✅ Yes (Row-level locks / MVCC) |
| **Offline Operation** | ❌ Read-only when disconnected from leaseholder | ✅ Full read-and-write offline capability | ⚠️ Requires local outbox queuing | ❌ Completely unavailable offline |
| **macOS & Windows Support** | ❌ Requires Linux kernel FUSE; fragile on macOS/Win | ✅ High (C extension runs inside standard SQLite) | ✅ High (Pure network protocol, stdlib or grpcio) | ✅ High (Network driver over TCP/TLS) |
| **Container & Sandbox Safety** | ❌ Requires `SYS_ADMIN` capability and `/dev/fuse` | ✅ High (Requires only local filesystem access) | ✅ High (Standard outbound HTTPS/TCP) | ✅ High (Standard outbound network) |
| **Conflict Resolution** | Physical serialization; no logical conflicts | Column-level LWW, PN-Counters, monotonic lattices | Handled by application or central coordinator | Optimistic concurrency / Serializable transactions |
| **Network Efficiency** | Medium (Transmits compressed physical disk pages) | High (Transmits minimal column-level delta changesets) | Very High (Protobuf binary streaming over HTTP/2) | Medium-High (SQL wire protocol over TLS) |
| **Implementation Complexity** | Low app code, High infra (Consul/etcd clustering) | Medium-High (C extension packaging & CRR schemas) | Medium (Protobuf schema definition & streaming loops) | Low (Standard psycopg2/SQLAlchemy driver) |
| **Suitability for Token/Cost Telemetry** | Low (High write contention causes lock storms) | High (Append-only CRDT G-Sets merge effortlessly) | Ideal (Designed for streaming event ingestion) | High (Standard relational `INSERT` batching) |

---

## 5. Recommended Architecture for synlynk

Based on `synlynk`'s identity as a **lightweight, developer-first, multi-agent harness**, no single protocol solves all requirements in isolation. A monolithic central database breaks offline developer autonomy, while pure LiteFS fails on developer macOS environments and unprivileged sandboxes.

We recommend a **3-Tier Hybrid Synchronization & FinOps Architecture**:

```
+--------------------------------------------------------------------------------+
| TIER 1: Local Node (Edge Autonomy - Zero External Dependencies)               |
| - Primary storage: local ~/.synlynk/.../state.db (Standard SQLite WAL)         |
| - 100% offline execution; zero latency on agent read/write operations          |
| - Local Outbox Table: cost_entries_outbox and state_mutations_outbox           |
+--------------------------------------------------------------------------------+
                                      |
                                      v (gRPC Bidirectional Stream over mTLS)
+--------------------------------------------------------------------------------+
| TIER 2: gRPC Mesh & Event Relay (Real-Time Coordination & Signaling)          |
| - Streaming inter-agent mailbox and event delivery (replacing polling)        |
| - Distributed token quota reservations (2-phase reservation protocol)         |
| - Batch telemetry ingestion pipeline for cost and health metrics               |
+--------------------------------------------------------------------------------+
                                      |
                                      v (Async Storage Pipeline)
+--------------------------------------------------------------------------------+
| TIER 3: Enterprise Aggregation Plane (Consolidation & Analytics)              |
| - FinOps Data Sink: ClickHouse or TimescaleDB for enterprise cost rollups      |
| - Collaborative State Sync: CRDT Delta Engine or LiteFS cluster for cloud pods |
| - OpenTelemetry / Prometheus Exporter for corporate observability platforms    |
+--------------------------------------------------------------------------------+
```

### Key Architectural Decisions
1. **Preserve Local SQLite Independence:** The developer machine's local `state.db` remains the authoritative truth for active local sessions. It must never block waiting for an upstream network sync.
2. **Outbox Pattern for Cost Telemetry:** Writes to `cost_entries` commit locally first. A lightweight background worker pushes batches to Tier 2 via gRPC when connected.
3. **CRDT Delta Engine for Shared Project Artifacts:** For multi-agent shared entities (`stories`, `backlog_items`, `decisions`), evaluate `cr-sqlite` to allow concurrent branch work to merge without git-style text conflict markers.
4. **gRPC Relay for Live Swarm Communication:** Upgrade `synlynk/relay.py` from HTTP polling to gRPC streaming, unlocking real-time event distribution and quota leasing across cloud runners and desktop agents.

---

## 6. Phased Implementation Roadmap

### Phase 1: gRPC Relay & Outbox Telemetry Push (Target: v0.20.0)
- **Objective:** Establish real-time telemetry streaming and cross-node messaging without altering local SQLite schemas.
- **Deliverables:**
  1. Define `.proto` definitions for `EventEnvelope`, `CostBatch`, and `QuotaReservation` in `synlynk/proto/`.
  2. Implement client outbox queue in `synlynk/costs.py` (`synced_at` column in `cost_entries`).
  3. Upgrade `SynlynkRelay` (`synlynk/relay.py`, `synlynk/daemon.py`) to support gRPC transport alongside legacy HTTP/SSE.
  4. Implement `synlynk cost push` and background streaming daemon sync.

### Phase 2: Distributed Quota Leasing & Dynamic Pricing (Target: v0.21.0)
- **Objective:** Prevent budget overruns across concurrent agent swarms and synchronize pricing rate cards.
- **Deliverables:**
  1. Implement `ReserveQuota` two-phase lease negotiation in `synlynk/dispatch.py`.
  2. Centralized rate-card distribution: `synlynk` fetches dynamic provider price tiers during daemon heartbeat, superseding static dictionaries.
  3. Wire quota reservations into `harness_reservations` table in `synlynk/db.py`.

### Phase 3: Collaborative CRDT State Replication (Target: v0.22.0)
- **Objective:** Enable multi-master synchronization of `stories`, `backlog_items`, and project decisions across distributed worktrees.
- **Deliverables:**
  1. Package optional `cr-sqlite` extension prebuilds or implement a pure-Python delta-vector CRDT sync layer for core tables.
  2. Implement `synlynk sync` command to pull and apply remote change sets.
  3. Automated tombstone compaction and conflict telemetry logging.

### Phase 4: Enterprise FinOps & OpenTelemetry Collector (Target: v0.23.0)
- **Objective:** Turnkey integration with enterprise observability platforms.
- **Deliverables:**
  1. OpenTelemetry collector export (`gen_ai.client.token.usage`).
  2. Prometheus `/metrics` endpoint on the `synlynk relay` server.
  3. Pre-configured Grafana dashboard templates for cost-center and agent-role spend visualization.

---

## 7. Traceability & References

- **Issue:** Closes #1402 (*Research distributed state.db synchronization protocols and enterprise cost aggregation*)
- **Story ID:** `story-d58e5033`
- **Related Issues & Historical Specs:**
  - #681 / `docs/superpowers/specs/2026-08-03-state-db-path-override-design.md`: State database path overrides for sandboxed execution.
  - #348 / `docs/superpowers/specs/2026-08-01-fleet-parity-security-cluster-design.md`: Environment isolation and subprocess credential protection.
  - #1255 / `docs/superpowers/specs/2026-08-16-rename-agent-cli-to-harness-design.md`: Harness vs Workspace Agent taxonomy separation.
  - `synlynk/costs.py`: Token extraction, rate tables, and cost estimation logic.
  - `synlynk/relay.py`: In-memory broker and SQLite-backed relay mailbox.
  - `synlynk/db.py`: Canonical schema definitions, migration versioning, and WAL configuration.
