---
decision_id: dec-7b5c8864
topic: "Should tpm's durable tasking/tracking/reporting loop be built as a consumer of GOVERNS' existing lifecycle-enforcement event contract (PR #817), or does tpm need its own separate, independent tracking mechanism? Option A: tpm consumes GOVERNS events as its data source -- GOVERNS stays the enforcement layer, tpm becomes a reporting/tasking layer on top of the same event contract. Option B: keep them decoupled -- GOVERNS enforces lifecycle rules unaware of tpm, tpm builds its own independent polling/state of GitHub/synlynk project state. Recommend one option and justify briefly."
date: 2026-08-09
panel: [claude, agy, codex]
status: approved
---

## Topic
Should tpm's durable tasking/tracking/reporting loop be built as a consumer of GOVERNS' existing lifecycle-enforcement event contract (PR #817), or does tpm need its own separate, independent tracking mechanism? Option A: tpm consumes GOVERNS events as its data source -- GOVERNS stays the enforcement layer, tpm becomes a reporting/tasking layer on top of the same event contract. Option B: keep them decoupled -- GOVERNS enforces lifecycle rules unaware of tpm, tpm builds its own independent polling/state of GitHub/synlynk project state. Recommend one option and justify briefly.

## Panel Inputs

### claude
As PM/reviewer on this project, I'll answer directly since this is a decision-panel judgment call, not implementation work.

**Analysis**

GOVERNS' PR #817 already establishes an event contract for lifecycle enforcement — state transitions, gate checks, violations. The question is whether tpm treats that contract as its source of truth or builds a parallel view.

Option B (independent tracking) creates the exact failure mode this project has been fighting all year: two systems independently polling GitHub/synlynk state will drift. We already have a standing memory item — "never trust `synlynk jobs` status alone" (#202) — precisely because state-tracking systems built without a single source of truth desync under real usage. tpm re-polling GitHub/synlynk state independently of GOVERNS means two enforcement-adjacent systems can disagree about whether a task is actually done, blocked, or violated — and now someone has to reconcile them. That reconciliation burden compounds with every dispatched job, the same way stale-worktree accumulation did before the Worktree Hygiene Protocol existed.

Option A keeps a single enforcement source of truth. GOVERNS emits events, tpm consumes them for reporting/tasking. This is also consistent with synlynk's own architecture pattern elsewhere in the repo: telemetry.json is written once by `exec_command`, and other consumers (costs.md, sentinel checks, `synlynk status --json` per the Vizor memory) read from that single log rather than re-deriving state. tpm-as-consumer fits that established shape.

The only real cost of Option A is coupling: if GOVERNS' event schema changes, tpm changes with it. But that's a manageable, visible dependency — versioned contract, not silent drift. Option B's cost (two systems disagreeing about ground truth) is worse and harder to detect, because it fails quietly until someone notices tpm and GOVERNS disagree on a task's state.

**Recommendation: Option A.** tpm should consume GOVERNS' lifecycle-enforcement events as its data source rather than building independent tracking. GOVERNS remains the single enforcement authority; tpm is a reporting/tasking layer on top. This avoids duplicating state-tracking logic, prevents the drift/reconciliation problem this project has already been burned by, and matches the existing single-source-of-truth pattern used elsewhere in synlynk (telemetry.json, `synlynk status --json`). Decouple only if GOVERNS' contract proves too narrow for tpm's needs — but that should be evidenced, not assumed upfront.

### agy
**Last completed task:** Perform structured technical code review of PR #51 (Codex Headless Dispatch)  
**Next task:** Refine decision flow templates for agents  

---

### Decision Panel Analysis: `tpm` Tasking Loop vs. `GOVERNS` Lifecycle Contract

Building `tpm`'s durable tasking, tracking, and reporting loop on top of `GOVERNS`' existing lifecycle-enforcement event contract (PR #817) offers clear architectural advantages over constructing a separate polling infrastructure.

**1. Single Source of Truth & Reduced Drift**  
If `tpm` operates its own independent polling mechanism against GitHub and synlynk project states (Option B), the system risks state desynchronization between lifecycle enforcement and task execution. Dual polling loops inevitably incur timing latency differences, race conditions, and unnecessary API rate-limit overhead. By consuming `GOVERNS` events (Option A), `tpm` relies on a unified, authoritative state log that guarantees consistent state awareness across all downstream reporting tools.

**2. Clean Separation of Concerns via Event-Driven Architecture**  
Consuming the `GOVERNS` event contract does not introduce tight operational coupling. `GOVERNS` remains entirely focused on validating and enforcing lifecycle rules without requiring any domain knowledge of `tpm`. Meanwhile, `tpm` acts strictly as an asynchronous consumer—translating verified lifecycle state changes into actionable tasks, metrics, and reporting workflows. This cleanly decouples enforcement policy from task orchestration while maintaining schema alignment.

**3. Operational Efficiency & Auditability**  
Reusing the PR #817 event contract eliminates redundant telemetry pipelines. Audit logs, rule evaluations, and task progression share matching event identifiers and timestamps, simplifying end-to-end debugging and platform compliance across autonomous agent workflows.

### Recommendation
**I strongly recommend Option A: `tpm` consumes `GOVERNS` events as its data source.** Option A preserves a single source of truth, prevents state drift, avoids API quota exhaustion, and maintains strict architectural separation by using `GOVERNS` strictly as the enforcement emitter and `tpm` as the tasking and reporting subscriber.

### codex
GOVERNS should be the canonical lifecycle authority, while tpm should consume its event contract and maintain only derived tasking/reporting state. The existing contract already provides the right primitives for durable coordination: append-only events, typed payloads, parent-event links, and per-consumer checkpoints. That gives tpm replayability, resumability, and idempotent processing across interrupted runs—important properties for durable task tracking.

Option A also preserves a clean separation of responsibilities. GOVERNS determines whether lifecycle transitions and boundaries are valid; tpm interprets those transitions to assemble waves, assign work, monitor progress, and produce reports. tpm can still own projections suited to its needs—dependency graphs, assignment state, queue priorities, task metrics, and performance history—without becoming a second authority over whether a story is legitimately ready, executing, released, or sustained.

Option B would make tpm independently poll GitHub, files, and synlynk state, forcing it to reconstruct lifecycle semantics that GOVERNS already enforces. That creates duplicated logic, race conditions, inconsistent interpretations of state, and reconciliation problems when events are missed or external state changes between polls. It also weakens the value of GOVERNS: enforcement and reporting could disagree about what actually happened.

The event contract should be made sufficiently expressive before tpm depends on it. In particular, lifecycle-stage transitions, task/job identifiers, story and goal links, completion outcomes, and failure or quarantine states should be represented explicitly. tpm may supplement events with periodic reconciliation for recovery, but polling should be a correctness backstop—not its primary source of truth.

My recommendation is **Option A**: build tpm as a consumer of GOVERNS’ lifecycle-enforcement events, with its own durable read model for scheduling and reporting. This avoids duplicated authority while preserving tpm’s ability to provide richer operational behavior.

## Synthesis
Decision: Option A — tpm consumes GOVERNS' lifecycle-enforcement event contract (PR #817) as its data source rather than building independent tracking. All three panelists converge on this, and it matches synlynk's own established pattern of single-writer/multi-reader state (telemetry.json feeding costs.md, sentinel checks, and `synlynk status --json`) rather than parallel polling systems that can drift — the exact failure mode already documented in the standing "never trust `synlynk jobs` status alone" (#202) memory. GOVERNS remains the sole enforcement authority over lifecycle validity; tpm builds a derived read model on top for scheduling, assignment, and reporting, with Codex's caveat noted as an implementation condition: the event contract must be verified sufficiently expressive (typed payloads, task/story/goal linkage, completion/failure/quarantine states, per-consumer checkpoints) before tpm depends on it, and tpm may keep lightweight periodic reconciliation strictly as a correctness backstop, never as its primary source of truth. Decoupling (Option B) is not pursued unless the GOVERNS contract is later proven too narrow for tpm's needs — that would need to be demonstrated, not assumed.

## Decision
Decision: Option A — tpm consumes GOVERNS' lifecycle-enforcement event contract (PR #817) as its data source rather than building independent tracking. All three panelists converge on this, and it matches synlynk's own established pattern of single-writer/multi-reader state (telemetry.json feeding costs.md, sentinel checks, and `synlynk status --json`) rather than parallel polling systems that can drift — the exact failure mode already documented in the standing "never trust `synlynk jobs` status alone" (#202) memory. GOVERNS remains the sole enforcement authority over lifecycle validity; tpm builds a derived read model on top for scheduling, assignment, and reporting, with Codex's caveat noted as an implementation condition: the event contract must be verified sufficiently expressive (typed payloads, task/story/goal linkage, completion/failure/quarantine states, per-consumer checkpoints) before tpm depends on it, and tpm may keep lightweight periodic reconciliation strictly as a correctness backstop, never as its primary source of truth. Decoupling (Option B) is not pursued unless the GOVERNS contract is later proven too narrow for tpm's needs — that would need to be demonstrated, not assumed.

> Signatures: see 2026-08-09-should-tpm-s-durable-tasking-tracking-re.json
