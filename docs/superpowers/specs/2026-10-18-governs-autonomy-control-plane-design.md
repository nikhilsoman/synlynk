# GOVERNS Autonomy Control Plane and Evidence-Gated Scale Design

**Status:** Draft for Nikhil review; not approved for implementation  
**Date:** 2026-10-18  
**Roadmap placement:** Fast follow after the synthesized strategic roadmap epic #2384 and the v1.0.0-preview release gate are complete; explicitly not a v1.0.0 launch blocker.  
**GOVERNS goal:** `goal-eacab0dc` — Universal GOVERNS enforcement  
**Primary tracking issue:** [#2412](https://github.com/nikhilsoman/synlynk/issues/2412)  
**Related substrate issue:** [#2413](https://github.com/nikhilsoman/synlynk/issues/2413)  
**Related reproduction:** [#2409](https://github.com/nikhilsoman/synlynk/issues/2409)  

### Goal associations

The existing tracking story `story-ee4529d9` remains primarily under `goal-eacab0dc`. Its cross-cutting contributions are:

- `goal-bd5eaa14` — reliable daemon-driven autonomy and backlog scheduling;
- `goal-a222b393` — executable workspace-agent charters and authority;
- `goal-adb60ccc` — job success/cost attribution and review telemetry;
- `goal-06758149` — activation of the workspace-agent fleet;
- `goal-abecd18c` — execution isolation and swarm-capable sandboxing;
- `goal-079e2f37` — launch credibility and completion of the synthesized review roadmap before this fast follow.

`goal-256d17d6` (whether to operate managed execution nodes or swarms for users) is a related decision boundary, not an implementation commitment of this design. This proposal does not decide to host execution.

## 1. Intent

Define a trustworthy control plane for autonomous engineering work that can begin with a small, strongly consistent local workflow and grow—only on demonstrated capability and cost adherence—to coordinated swarms of tens or hundreds of agents.

The design must make every task's objective, parentage, owner, delegated authority, execution identity, evidence, cost, and lifecycle state traceable. It must preserve strategic focus: Synlynk is a neutral control plane that routes work, verifies outcomes, preserves project state, and accounts for execution—not a promise that maximum autonomy or agent count is itself valuable.

This is a design proposal, not an implementation plan. No production autonomy, concurrency, permission, or merge policy is changed by this document.

## 2. Problem and review synthesis

The review record supports a consistent product and architecture direction, with some differences in priority and what was considered complete at each review date:

| Review source | Recommendation relevant to this design | Design consequence |
|---|---|---|
| 2026-09-27 deep architecture review (`project-docs/decisions/2026-09-27-round-1-deep-architectural-review.md`) | Verify effects rather than exit codes; enforce budgets; probe capability before routing; keep one authoritative ledger; keep the full seven-stage GOVERNS model internally while simplifying routine UX. | Strong consistency for authority and writes; verified receipts; preflight capability checks; simple operator view over the full lifecycle. |
| 2026-09-27 strategic/business review (`project-docs/decisions/2026-09-27-round-2-strategic-business-review.md`) | The durable value is neutral cross-vendor accountability, shared project memory, reliable outcomes and costs. Avoid competing with coding agents on their core interface or overclaiming enterprise controls. | Optimize for trust, portability, and a credible user journey; do not turn swarm size into the product promise. |
| 2026-10-02 architecture re-review (`project-docs/decisions/2026-10-02-round-1-deep-architectural-re-review.md`) | Reported the original five invariants as structurally implemented at that time. | Treat these as historical evidence and verify current behavior; do not reopen or declare them complete based on review prose alone. |
| 2026-10-05 three-lens strategic review (`docs/reviews/2026-10-05-three-lens-strategic-review.md`) | Extract and harden the verification kernel; focus on adoption, reliability, governance closure and measured routing rather than breadth. | Make large-swarm execution a future scale tier, not a prerequisite for the first useful release. |
| 2026-10-13 workspace-agent charter decision (`project-docs/decisions/2026-10-13-finalize-workspace-agent-roles-charters.md`) | Durable roles need explicit mandate, authority, escalation and wake-cycle SOPs. Harness/model choice should remain empirical and should not be hard-coded into role charters. | Roles own responsibility; measured capability chooses the execution harness; bind each job to the charter revision actually used. |
| 2026-10-16 deep-goal and repository reviews (`docs/reviews/2026-10-16-deep-review-against-goals.md`, `docs/reviews/2026-10-16-deep-repo-review-and-revised-roadmap.md`) | Keep the release dependency-ordered and scope-controlled; make GOVERNS enforcement, capability/cost evidence, workspace roles, and swarm capability explicit roadmap concerns. | Reconcile prior claims and open work; build in phases with evidence gates. |
| 2026-10-16 frontier-lab architecture review (`docs/reviews/2026-10-16-frontier-lab-architecture-review.md`) | Supervised execution was inconsistent; authorization should be bound to task/repository/base/capabilities/policy/budget; recommendations must not become approvals; completion/cost evidence must be keyed to actual job attempts; unknown actions should fail closed. | Treat authorization, recommendation, execution, verification, and approval as distinct recorded facts; enforce at enqueue and spawn; use a durable outbox and reconciliation for external effects. |

These reviews are not treated as a vote to maximize feature scope. The earlier reviews' safety and scale observations are to be reconciled against current code and issues, with each recommendation marked implemented, open, superseded, or disputed and supported by evidence. The detailed source/disposition register belongs with #2412 and must include new periodic reviews as they arrive.

### Related-work boundary

- **#2412 owns** GOVERNS policy semantics, autonomous progression, role/charter accountability, authorization provenance, and cost attribution/reporting requirements.
- **#2413 owns** canonical state resolution, state/projection drift, roadmap/story write-through, and persistence synchronization. #2412 consumes these guarantees and should not duplicate that implementation scope.
- **#2409 remains** a Local Harness-originating review/merge reproduction. It is evidence for the cross-cutting authorization and provenance requirements, not the umbrella for them.

## 3. Goals and non-goals

### Goals

1. Preserve strong consistency for task ownership, authority, budget reservation, stage transitions, leases, and terminal evidence.
2. Make every child task and agent attempt traceable to a goal and parent work item, with explicit scope, owner, dependencies, evidence, and cost.
3. Prevent delegated work from widening the authority, repository scope, capabilities, or remaining budget granted to its parent.
4. Enforce GOVERNS stage policy and workspace-agent charter responsibilities at the system boundary, not only in prompts.
5. Permit gradual increases in concurrency only after defined evidence demonstrates outcome quality, policy adherence, recovery, and cost control.
6. Keep the execution plane replaceable and scalable without prematurely introducing distributed consistency mechanisms.
7. Preserve a legible product promise: approved work, attributable outcomes, explicit costs, and recoverable failures.

### Non-goals

- Implementing or enabling a 100-agent swarm in the first delivery phase.
- Replacing the SQLite ledger with a distributed database or adopting microservices before measured need.
- Treating model consensus, agent count, a successful process exit, or an issue/PR status alone as proof of task completion.
- Removing human-reserved or independent review/merge gates.
- Claiming enterprise isolation, zero cost overshoot, or autonomous safety by prompt alone.
- Binding model/harness selection permanently into role charters.

## 4. Architectural alternatives

### A. Centralized scheduler and strongly consistent ledger

One logical controller owns authorization, task DAGs, leases, budgets, stage transitions, and dispatch. Workers execute in isolated worktrees and return receipts.

**Advantages:** simplest authority model; straightforward audit and deterministic transition ordering; best starting point for a single workspace and low concurrency.

**Risks:** central scheduler and SQLite write path can become throughput or availability bottlenecks. A single global queue may create head-of-line blocking.

### B. Hierarchical agent coordinators

A goal/workstream coordinator decomposes work and supervises subordinate agents, which can create further bounded tasks.

**Advantages:** maps naturally to large projects and parallel work; coordination can be partitioned by workstream.

**Risks:** delegation chains can obscure ownership, lose requirements, duplicate work, or widen authority. Multiple coordinators may race on shared resources or make inconsistent policy decisions.

### C. Hybrid control plane with hierarchical decomposition — recommended target

Keep one logical authority for policy, identity, budget reservation, GOVERNS transitions, and durable audit. Coordinators may propose bounded task DAGs; a trusted control-plane service validates and admits them. Independent worker pools execute isolated tasks and report receipts. Start with one local controller and SQLite; introduce partitioned queues or replicated services only when measured limits require them.

**Advantages:** preserves a strong governance boundary while supporting horizontal execution; hierarchical planning does not confer authority; can evolve without making distributed infrastructure a day-one requirement.

**Risks:** requires explicit APIs and durable event semantics; the control plane remains a critical dependency and must have clear recovery behavior.

**Decision proposed:** adopt C as the long-term architecture and implement its minimum strongly consistent subset first. Do not build distributed consensus or a hosted control plane in this tranche.

## 5. Proposed system model

### 5.1 Work hierarchy and task contract

Represent work as a directed acyclic graph with explicit lineage:

`goal → epic/workstream → story → task → attempt`

Each executable task contract includes:

- stable ID, parent ID, primary goal ID, optional secondary goal contributions;
- objective, acceptance criteria, constraints, risk class, and verification plan;
- dependency edges and declared read/write/resource scope;
- requested workspace role and resolved role/agent identity;
- authorized capabilities and budget ceiling;
- repository, worktree, base commit, and relevant policy/charter revisions.

Decomposition is a proposal until admitted by the control plane. Child tasks inherit the parent scope and remaining budget as an upper bound. A child may narrow either. It cannot add capabilities, repositories, budget, or approval powers without a new authorization. Dependencies must be explicit; a child cannot be marked complete solely because its parent coordinator reports completion.

### 5.2 Strong-consistency boundary

Strong consistency is required for:

- task creation/admission, parent-child links, task ownership, and dependency/lease acquisition;
- authorization grants, revocations, budget reservation/settlement, and policy revision selection;
- GOVERNS state transitions and terminal job decisions;
- immutable identity, charter revision, and evidence/provenance linkage.

Use the canonical state database as the current write authority, with transactions and a single-writer contract. Preserve an append-only lifecycle/provenance journal and transactional outbox for external side effects. This does **not** require a wholesale event-sourced rewrite: normalized current state may remain authoritative, while journal events provide audit and replayable external-effect intent. Markdown, dashboards, and analytics are projections with freshness markers, not competing authorities. #2413 owns the canonical-ledger and projection implementation.

GitHub or other remote side effects cannot be committed atomically with the local database. Persist an authorized outbox intent before attempting the side effect; use an idempotency key where supported; then record the remote receipt or an explicit pending/failed state. Reconcile after lost acknowledgements or restart. Never report an external effect as complete based only on a local dispatch result.

### 5.3 GOVERNS stage policy and ownership

Keep the seven-stage lifecycle as the internal source of truth. Provide a compact default UI/status view for routine work, with full stage evidence available on demand.

| Stage | Proposed accountable role | Minimum evidence before transition | Autonomy boundary |
|---|---|---|---|
| Goal | PM / human goal owner | Outcome, success measure, scope, owner, risk and budget envelope | Strategic goal creation/major scope changes require human authority. |
| Open | TPM, with PM for priority | Deduplicated tracked item, goal link, acceptance criteria, dependencies, risk class | Intake and classification may be automated; ambiguous or conflicting priority escalates. |
| Visualize | Architect / design owner | Approved design/spec and explicit unresolved decisions | Agents may draft and critique; required human spec sign-off remains reserved. |
| Execute | Capability-selected implementing role | Admitted task contract, valid grant, lease, budget reservation, preflight capability result | Bounded task execution may be autonomous only within its grant. No self-expanding scope. |
| Release | Independent QA / reviewer; merge authority from policy | Verified effects, required checks, independent review, policy check, attributable credentials | Author cannot approve own work. Merge requires the configured independent authority and any reserved human gate. |
| Notify | TPM / automation identity | Durable outcome receipt, relevant links, cost and failure state | Notifications can be automated from confirmed events; no success claim without evidence. |
| Sustain | TPM / maintainer | State/projection reconciliation, follow-up items, audit/cost closure, recovery of orphans | Routine reconciliation can run autonomously; policy changes and irreversible cleanup remain gated. |

Every transition records actor, accountable role, evidence references, policy revision, cause/event ID, timestamp, and whether it was automatic, human-authorized, or corrected. Invalid transitions fail closed and remain visible; exceptions must not be swallowed into apparent success.

### 5.4 Autonomy modes and reserved gates

Retain the existing three-mode model rather than adding mode proliferation. Define its semantics uniformly across CLI, daemon, scheduler, dispatch, retry, handoff, and relay entry points:

- **Manual:** no autonomous execution or advancement beyond explicitly requested actions; observation and bookkeeping may continue.
- **Supervised:** eligible work may be prepared and scheduled, but execution requires an explicit task-bound authorization receipt. A “ready” label alone is not an execution grant. Reserved design/release/merge actions remain independently gated.
- **Autonomous:** only admitted, risk-bounded tasks with a valid delegated grant may execute and advance automatically. Grant scope, budget, capability, expiry, and maximum concurrency are enforced outside the worker. High-impact or irreversible actions remain reserved by policy.

The same decision function must run at admission/enqueue and immediately before spawn/side effect. Retries, child delegation, daemon recovery, and handoff cannot widen authority. Mode semantics must be tested against the actual production call graph, not only a standalone helper.

### 5.5 Identity, authorization, and provenance

Record distinct identities for:

- **authorizing principal** — human or policy principal that granted a specific action;
- **delegating coordinator** — agent/role that requested or decomposed work;
- **workspace-agent identity and role** — accountable owner under a versioned charter;
- **execution harness/model/provider** — runtime that performed the work;
- **credential principal** — GitHub App, service account, host account, or local credential actually used for each external effect.

An authorization receipt should bind at minimum: grant ID, authorizing principal, target goal/task/attempt, repository, base SHA or equivalent resource version, allowed operations/capabilities, policy revision, budget ceiling, expiry, revocation state, and delegation parent. Record both allowed and denied operations. Dispatch authorization must not imply permission to review, approve, merge, publish, or alter policy. Host credential fallback must be denied by default or explicitly authorized and logged before the effect; a displayed GitHub username alone does not prove which credential mechanism was used.

Each attempt receipt should bind task lineage, GOVERNS stage, requested/resolved role, workspace-agent ID and charter revision, harness/model/provider, worktree/base SHA, grant ID, start/finish/exit state, changed paths/effect hashes, checks and independent review, external-effect receipts, retries/failures, token/cost measurements, and reconciliation status. Use immutable event IDs and idempotency keys to prevent duplicate transitions. Protect provenance and policy records from worker mutation.

### 5.6 Charter and assignment contract

Charters combine human-readable mandate/SOP with a validated machine-readable contract:

- scope, stage responsibilities, allowed task/risk classes, required skills/capabilities;
- allowed tools/actions and forbidden actions;
- approval authority (usually none for self-review/merge), budget/concurrency envelope;
- escalation triggers, idle/wake behavior, handoff and recovery expectations;
- charter owner, version, and content hash.

Assignment first selects a responsible workspace role based on stage and task type. Harness/model selection is a separate capability decision based on live eligibility and measured evidence. A missing role, unavailable harness, incompatible grant, or stale charter causes explicit escalation/rejection, not silent substitution. Every attempt retains the charter revision and assignment rationale used.

### 5.7 Cost and capacity contract

Capture per attempt, with explicit provenance and coverage state:

- provider-billed/paid amount when available;
- token/usage-derived estimate with pricing version and uncertainty;
- subscription-amortized allocation, kept separate from marginal spend;
- manual correction/true-up and source reference;
- shared control-plane overhead as its own bucket.

Roll up without double-counting across task, story, workstream, goal, workspace role/agent, harness, provider, and retry/review activity. Unavailable, disputed, unattributed, and stale measurements remain explicit. Reserve the remaining project/goal budget transactionally before task admission; child and retry ceilings cannot exceed the unspent parent budget. Define a permitted measurement error/overshoot envelope from provider limits, sampling interval, and cancellation latency. Do not claim zero overshoot where the provider cannot support it.

### 5.8 Swarm execution and isolation

The work plane may scale independently, but all workers operate under the control-plane grant and task contract:

- one isolated worktree/repository namespace per active task or attempt;
- explicit leases for shared files, branches, environments, and scarce resources;
- declared read/write sets where practical; dependency-aware scheduling and conflict detection;
- per-project, goal, role, harness, and provider concurrency/rate limits with fair scheduling;
- bounded retries, cancellation propagation, heartbeats, and idempotent recovery;
- integration tasks merge artifacts in dependency order; independent review and verification remain separate roles;
- kill switch at project/goal and workspace level that prevents new admission and revokes outstanding grants according to policy.

Agent-to-agent messages are advisory unless converted into validated control-plane state. Worker output cannot mutate authority, budget, or acceptance criteria. Parent coordinators remain accountable for decomposition quality, but task-level receipts preserve direct executor responsibility.

## 6. Evidence-gated concurrency and cost promotion

Strong consistency is not relaxed to gain throughput. Scale the execution plane gradually; authority and ledger semantics remain stable at every tier.

| Tier | Target concurrency | Gate to enter | Required measurements |
|---|---:|---|---|
| Baseline | 1 | Contract and policy tests pass; one end-to-end lifecycle works with a real isolated worktree and test credentials. | Correct task/goal association, verified effect, independent review, complete provenance, cost reconciliation, restart recovery. |
| Pilot | Up to 5 | Baseline evidence is repeatable; applicable GOVERNS observe/enforce promotion requirements are met; no unresolved critical authorization, ownership, or completion defect. | Success/no-op rate, stage drift, attribution completeness, budget variance, conflicts, queue latency, recovery and cancellation behavior. |
| Bounded swarm | Up to 10, then 25 | Predeclared sample sizes and thresholds are met at the preceding tier; 100-clean-pass requirement is satisfied where required for leaving observe mode; security/policy violations remain zero. | Same metrics plus fairness, dependency stalls, duplicate work, merge/rebase conflicts, per-role/harness quality and resource saturation. |
| Scale validation | 50, then 100+ | 25-agent tier demonstrates stable control-plane latency, no ledger/lease corruption, bounded recovery, complete accounting, and approved costs under load. | Soak, restart, partial outage, queue partition/replay, budget reservation race, revocation propagation, and cross-workstream integration tests. |

Before each tier, owners must publish the sample size, error bars, acceptable cost-variance/overshoot envelope, latency and recovery limits, and stop conditions. Thresholds are not tuned after observing a failing run. Any unauthorized side effect, incorrect task ownership, false-success completion, budget-limit bypass, or unrecoverable provenance gap stops promotion and triggers rollback to the last proven tier. If evidence is insufficient, hold the current tier rather than interpreting “no observed failure” as proof.

The first scale gates should be calibrated from the baseline rather than inventing arbitrary precision. The existing GOVERNS 100-clean-pass criterion remains a hard prerequisite where policy requires it; it does not replace task-quality, cost-adherence, recovery, or concurrency evidence.

## 7. Delivery phasing

### Phase 0 — Review reconciliation and boundary agreement

- Build the recommendation/source register and disposition each relevant strategic, business, architecture, charter, GOVERNS, and cost review finding.
- Confirm #2412/#2413 ownership and shared interfaces; keep #2409 as evidence.
- Baseline current stage drift, assignment/provenance completeness, cost attribution, and autonomy-mode behavior.
- No new autonomy or concurrency is enabled in this phase.

**Scheduling dependency:** Start this follow-on only after the synthesized strategic roadmap tracked by [#2384](https://github.com/nikhilsoman/synlynk/issues/2384) is complete and the v1.0.0-preview Phase 3 release gate has been resolved. This is a planned fast follow, not a release-blocking item. If the strategic roadmap is re-baselined, retain the dependency and update the roadmap reference rather than pulling this scope into launch by default.

### Phase 1 — Semantics and contract design

- Approve the stage/role/evidence table and exact three-mode semantics.
- Define task/attempt lineage, authorization/delegation receipt, agent/credential identity, charter revision, cost record, and outbox contracts.
- Define reserved human gates, denial and escalation behavior, threat model, retention, and auditable correction/supersession rules.
- Decide measurable promotion thresholds and stop/rollback conditions before running scale experiments.

### Phase 2 — Strongly consistent single-worker vertical slice

- Implement only after the design spec is approved and an implementation plan is committed.
- Prove one task end-to-end through goal/open/visualize/execute/release/notify/sustain with evidence-backed transitions.
- Prove no unauthorized execution in supervised mode; no self-review/merge; no silent host-auth fallback; correct failure/retry/restart handling; complete identity and cost receipts.
- Coordinate canonical ledger/projection changes with #2413; preserve fail-closed behavior.

### Phase 3 — Bounded concurrency (1 → 5 → 10 → 25)

- Add independent worktree workers, leases, budgets, fairness, queueing, cancellation, and dependency handling.
- Promote one tier at a time only after the evidence gates above pass with predeclared samples and thresholds.
- Keep the authoritative write path strongly consistent; scale readers/projections independently and expose their freshness.

### Phase 4 — Swarm scale validation (50 → 100+)

- Only if Phase 3 measurements identify real scheduler/worker throughput limits.
- Add partitioned queues and worker pools while retaining one logical authority per workspace/project partition, durable event/outbox contracts, and explicit cross-partition integration rules.
- Test database/lease contention, coordinator loss, worker churn, partial network/GitHub outages, policy revocation, and budget races under load.
- Select any future storage/broker changes based on measured limits; do not pre-commit to Postgres, a specific message bus, or hosted services.

### Phase 5 — Product and operationalization

- Expose concise task status and clear explanations for why work is blocked, permitted, or denied; provide deep receipts and full GOVERNS history on demand.
- Publish truthful capability, cost, concurrency, and reliability claims based on sustained evidence.
- Keep a kill switch, rollback path, operator runbook, data export/backup, and audit reports part of the product contract.

## 8. Verification and acceptance criteria

1. Every task/attempt has one unambiguous parent lineage and primary GOVERNS goal; cross-goal links are explicit contributions.
2. Stage transitions enforce required evidence and role authority across CLI, daemon, dispatch, retry, handoff, and remote-ingress paths.
3. Supervised mode cannot spawn execution without an explicit task-bound authorization receipt. Autonomous mode cannot exceed inherited scope, capability, budget, or concurrency.
4. Author, reviewer, approver, merger, credential principal, and human authorizer remain distinguishable in receipts; same-agent approval is rejected.
5. Charter and policy revision changes are auditable; worker edits cannot grant authority to themselves.
6. A false-green/no-op task, duplicate event, timeout, partial GitHub effect, missing usage report, token/cost limit, restart, revoked grant, and coordinator failure each have explicit tested outcomes.
7. Cost reports reconcile direct costs to attempts and aggregate accurately to story/goal/role; unattributed/shared costs and estimates are plainly labeled.
8. Concurrency promotion is blocked until its predeclared capability, cost, consistency, recovery, and policy gates pass; scale can be reduced immediately without losing audit data.
9. Projections can lag or be rebuilt without becoming alternate authorities; #2413 owns persistence and drift-repair criteria.
10. Strategic/customer-facing claims stay within the independently verified capability and do not imply enterprise isolation or unrestricted swarm autonomy.

## 9. Open decisions for review

1. Does the proposed hybrid architecture—central logical governance with hierarchical decomposition and independently scalable workers—fit the long-term intent?
2. Which transitions require explicit human sign-off in all workspaces, and which may be configured by policy? The spec assumes design approval and high-impact release/merge gates remain reserved unless policy explicitly delegates them.
3. What task risk classes and action taxonomy should control autonomous admission?
4. What baseline sample sizes and quantitative cost/quality/recovery thresholds should govern the 1→5→10→25→50→100+ promotion ladder?
5. Should parent coordinators be allowed to create proposed child tasks directly, or must every child be admitted by a separate TPM/control-plane role? This draft favors proposals by coordinators and authoritative admission by the control plane.
6. Which cost dimensions are decision-grade and available from each harness/provider, and what constitutes acceptable estimate error?
7. Which local identity/credential mechanisms are in scope for the first vertical slice, including explicit handling of host-auth fallback?
8. What retention, redaction, and privacy policy applies to prompts, diffs, logs, provenance receipts, and external identities?

## 10. Approval boundary

This document is a draft for discussion. Per the repository's brainstorm-first and design→plan→build rules, it is not an approved spec until Nikhil signs off and the spec is committed. Do not write an implementation plan or dispatch implementation work before that approval.
