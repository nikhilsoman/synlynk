# Blog Proposal: Project Management in Agentic Engineering — Why State is Canonical and Platforms are Views

**Audience:** CTOs, Engineering Leaders, and developers designing or adopting multi-agent development systems who are struggling to coordinate human and agent work without causing context drift, API throttling, or security/attribution gaps.

---

## The Pitch
In a world where AI agents build software alongside humans, who manages whom? Traditional Project Management (PM) systems—Jira, Linear, GitHub Projects V2—are built for humans. They assume human constraints: 8-hour workdays, sprint cycles, story points, and manual status updates. 

When you plug autonomous coding agents into this flow, the system breaks. Agents operate at sub-second decision speeds, exhaust API rate limits in minutes, and need to track variables that humans never care about (like token estimation, domain competency scores, and cryptographic signatures of execution events).

This proposal outlines how **synlynk** solves this coordination challenge: by treating a local SQLite WAL database (`state.db`) as the canonical PM scheduler, and external human-centric PM boards as mere projection views.

---

## Target Narrative Outline

### 1. The Day the Agents Broke the Kanban Board
* A brief case study of the canonical failure (referencing the real-world **rxcc S-037** incident): Two agents (e.g., Claude and Gemini) working in different git worktrees of a polyglot workspace, completely blind to each other's active work, overriding each other’s commits because the PM board was updated via manual copy-paste scripts.
* Why traditional PM systems can’t handle agent coordination:
  * **API Latency & Limits:** A scheduling loop checking tasks or moving cards via GraphQL/REST on every step introduces 500ms+ network calls and hits rate limits almost instantly.
  * **Offline-First Failure:** If the internet drops or GitHub goes down, the agent’s scheduler halts. A developer's local compiler doesn't stop during an outage; the agent's scheduler shouldn't either.
  * **Schema Square-Peg/Round-Hole:** Standard issue templates don't support agent-native concepts like Token Quotas, Domain Routing, or Automated Verification Assertions.

### 2. The Solution: "State Never Branches"
* Introducing synlynk's core database principle: **Branching is for code; project state never branches.**
* How the local database (`~/.synlynk/projects/<project_id>/state.db`) operates as the local scheduler "kernel" shared by all worktrees.
* How the context bridge (`context.md`) is generated on the fly, ensuring that every agent execution has an absolute, up-to-the-millisecond view of WIP across the entire workspace.

### 3. Agentic PM vs. Human PM: A Paradigm Shift
We compare the metrics and structures of agentic project management against the human equivalents:
* **Time/Sprints vs. Capability Gates:** Work isn't grouped by dates; it's gated by executable assertions (e.g., "v0.5.0 is complete when the SQLite WAL migration passes all verification tests").
* **Story Points vs. Token Budgets:** Estimating difficulty in points is replaced by token usage ceilings, routing agents based on capability-to-cost efficiency.
* **Velocity vs. Throughput:** Measuring points per sprint is replaced by tokens processed per quota period.

### 4. Cryptographic Identity & Attribution
* Why storing status changes directly in GitHub Projects or Jira breaks security.
* How synlynk uses local machine-level Ed25519 keypairs (`~/.synlynk/identity.key`) to sign every single event (starts, blocks, completions, costs).
* Creating a non-repudiable audit trail of agent activity, even when simulating a full multi-member team locally.

### 5. The Sync Gateway: How Humans Stay in the Loop
* If the agent database is local and canonical, how do human managers track progress?
* Introducing the **Async Outbox Gateway**:
  * **Local is Canonical:** The local agent schedule writes directly to the local database immediately.
  * **Asynchronous Projection:** A background daemon publishes these state updates to GitHub Projects or Jira outbox style (non-blocking).
  * **External Signals:** Human comments or status updates on GitHub are pulled back as signed `external_signal` events, syncing human decisions back into the local state machine.

---

## Draft Key Snippets

### The Agentic Project Management Hierarchy
In synlynk, we replace the traditional Epic -> Story hierarchy with a dependency and strategy-anchored structure:
```
Project
  └── Arc       — Strategic direction (Pivot/Convergence/Archive)
        └── Phase     — Structural backbone (Capability gates, replacing Sprints)
              └── Epic      — One execution plan (e.g., the output of a writing-plan task)
                    └── Story     — One assigned, verifiable, dependency-aware task unit
                          └── Event     — Cryptographically signed state transitions (replaces manual devlogs)
```

### The Async Projection Bridge (The `external_refs` Mapper)
Instead of forcing the agent system to conform to GitHub's schema, synlynk maintains an `external_refs` table to project its internal state out to the world:

```sql
CREATE TABLE external_refs (
  id           INTEGER PRIMARY KEY,
  entity_type  TEXT NOT NULL,   -- 'arc'|'phase'|'epic'|'story'
  entity_id    INTEGER NOT NULL,
  platform     TEXT NOT NULL,   -- 'github'|'jira'|'linear'
  external_id  TEXT NOT NULL,   -- Platform specific UUID/ID
  external_url TEXT,
  last_synced  TIMESTAMP
);
```

---

## Expected Takeaways for Readers
1. **Local State is Non-Negotiable:** For multi-agent systems to be reliable, fast, and secure, they must use a local canonical state database.
2. **PM Integration Must Be Async:** Treating external issue trackers as write-through caches or async views prevents network failure from stopping local execution.
3. **Agent Coordination Requires New Primitives:** We must transition our engineering tracking from human-centric time constraints to agent-centric resource and capability gates.
