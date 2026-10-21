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
- shared control-plane overhead as its own bucket;
- customer-brought-credential (BYO-provider) usage, metered but not vendor-billed, kept separate from every bucket above — no subscription-amortization or vendor-markup logic applies to it, since the vendor is not the payer of record.

Roll up without double-counting across task, story, workstream, goal, workspace role/agent, harness, provider, and retry/review activity. Unavailable, disputed, unattributed, and stale measurements remain explicit. Reserve the remaining project/goal budget transactionally before task admission; child and retry ceilings cannot exceed the unspent parent budget. Define a permitted measurement error/overshoot envelope from provider limits, sampling interval, and cancellation latency. Do not claim zero overshoot where the provider cannot support it.

### 5.8 Swarm execution and isolation

The work plane may scale independently, but all workers operate under the control-plane grant and task contract:

- one isolated worktree/repository namespace per active task or attempt;
- explicit leases for shared files, branches, environments, and scarce resources;
- declared read/write sets where practical; dependency-aware scheduling and conflict detection;
- per-tenant, per-project, goal, role, harness, and provider concurrency/rate limits with fair scheduling — tenant is the outermost scoping boundary, so no fairness or scheduling decision made at the project/goal/role/harness/provider level may cross it;
- bounded retries, cancellation propagation, heartbeats, and idempotent recovery;
- integration tasks merge artifacts in dependency order; independent review and verification remain separate roles;
- kill switch at tenant, project/goal, and workspace level that prevents new admission and revokes outstanding grants according to policy.

Agent-to-agent messages are advisory unless converted into validated control-plane state. Worker output cannot mutate authority, budget, or acceptance criteria. Parent coordinators remain accountable for decomposition quality, but task-level receipts preserve direct executor responsibility.

### 5.9 External system integration points

This design defers building enterprise-grade integrations but names the seams now so the core model does not have to be retrofitted later. Three points of the system are external-system-pluggable rather than fixed to the tools used during the single-workspace tranche (GitHub, local git identity):

**Tracked-item adapter.** The Open stage (5.3) is defined in terms of a "deduplicated tracked item" with a goal link, acceptance criteria, and dependencies — not in terms of GitHub Issues specifically. Treat the binding between a tracked item and its system of record as an adapter: GitHub Issues/PRs is the first (and, for the single-workspace tranche, only) adapter implementation. An adapter's job is to normalize an external record (a GitHub issue, a Jira ticket, a ServiceNow request) into the Open-stage contract and to write GOVERNS-stage status back to that record via the outbox pattern (5.2) — never to become an alternate authority for stage state. #2413's canonical-state ownership is unaffected: adapters produce Open-stage admission candidates and receive status projections; they do not read or write ledger state directly.

**Principal-resolution adapter.** Section 5.5 already separates authorizing principal, delegating coordinator, workspace-agent identity, execution harness, and credential principal. Treat *authorizing principal* resolution itself as adapter-bound rather than assuming a git/GitHub login: the first implementation resolves principals from local git identity and GitHub accounts; a later enterprise adapter resolves the same principal type from an identity provider (SAML/OIDC/SCIM-fed directory service) without changing the receipt schema, the grant model, or any downstream consumer of "authorizing principal." Open decision #7 (local identity/credential scope) is unchanged by this — it still governs what ships in the first vertical slice — but the interface boundary it operates inside is now explicit.

**Retention and tenancy-scoped policy hook.** Open decision #8 (retention, redaction, and privacy policy for prompts, diffs, logs, receipts, and external identities) remains unresolved and is not being answered here. What changes is that any future answer must be expressible per tenant, not only globally: a receipt or provenance record carries enough structure (subject type, data-classification tag, originating adapter) that a tenant-specific retention/redaction policy can be applied without changing the receipt schema itself. No specific retention duration, redaction mechanism, or classification taxonomy is adopted by this document.

None of the three adapters above are implemented in Phase 1 or Phase 2 of this design (section 7). Naming them now is a cost of a few paragraphs; discovering the need for them after Phase 2's vertical slice ships would require reopening the task contract, the identity model, and the receipt schema simultaneously.

The same split — synlynk-exclusive authority/decision versus adapter-eligible content/evidence — recurs at every GOVERNS stage, not only Open:

| Stage | Synlynk-exclusive core (cannot be delegated) | Adapter-eligible surface | Example external tools |
|---|---|---|---|
| Goal | Budget/authority ledger record; human-approval event | Outcome/success-measure content import | OKR tools (Aha!, Productboard, Jira Align) |
| Open | Admission decision: dedup, goal link, risk classification | Tracked-item source | GitHub Issues, Jira, ServiceNow |
| Visualize | Sign-off/approval evidence record (who, when, which revision) | Design-doc storage/collaboration | Confluence, Notion, Figma, RFC tools |
| Execute | Task admission, leasing, grant issuance, budget reservation — the strong-consistency core of the whole system | None of substance. The artifacts touched (git, cloud infra) are the subject of execution, not an info adapter for the stage itself. | — |
| Release | Merge-authority gate decision (policy check, independent-review requirement) | Evidence ingestion: check results, review approvals, scan results | GitHub Actions/CI, GitLab/Gerrit review, SAST/DAST scanners |
| Notify | Receipt correctness/durability (must exist before notifying) | Outbound channel — almost the whole stage | Slack, email, PagerDuty, Jira comment, status page |
| Sustain | Reconciliation/orphan-recovery logic against the canonical ledger (#2413's domain) | Follow-up item creation (loops back through Open's adapter); cost/audit export | ERP/billing export, SIEM/audit log export |

Execute is deliberately the exception: it is the stage where an integrator might instinctively look for a plug point, and there is none at the stage-info level — admission, leasing, and budget reservation are exactly the strong-consistency boundary section 5.2 protects, and no external system (an ITSM automation, a Jira workflow trigger) may invoke Execute directly. Notify is the opposite extreme and the lowest-risk first integration target: the receipt is already synlynk-owned and durable before anything goes out, so pushing it to an enterprise customer's existing Slack/Jira is close to zero new control-plane risk. Sustain's follow-up-item creation closes the loop through the same Open-stage adapter that would have admitted a human-filed ticket, rather than using a separate code path.

### 5.10 Third-party execution-fleet harnesses (Devin/OpenHands/Vue-class)

Execute's "no adapter surface" (5.9) is a statement about *authority* — admission, leasing, and budget reservation stay synlynk-exclusive — not about which runtime performs the work once a task is admitted. A commercial autonomous-engineering fleet (Devin, OpenHands, Vue, and similar) is not an Execute-stage integration at all; it is a candidate **harness**, the same abstraction slot Claude/Codex/Grok/Agy/local/muse already occupy (see Terminology: Role vs Harness). The hybrid control-plane model (section 4, Alternative C) already assumes the control plane admits a bounded task and an independent worker pool executes it and reports a receipt — a third-party fleet is simply a worker pool synlynk does not operate itself. The strategic appeal is specialization: a fleet vendor may buy compute and core-model access at rates synlynk cannot match directly, while synlynk's differentiated value stays in the GOVERNS lifecycle, policy/audit trail, cost accounting, and (per 5.8) tenant isolation sitting above it.

**Harness capability contract.** Any execution backend — in-house or third-party — must satisfy the same minimum receipt shape to be dispatch-eligible: task status, resulting diff/PR or equivalent artifact, itemized cost/token usage, and provenance (which principal authorized it, which credential executed it). This is already implicitly required of every current harness; naming it as an explicit contract matters once a harness is a closed third-party product rather than a CLI synlynk invokes directly. Two concrete risks follow from that closedness:

- **Cost itemization may not exist.** A fleet vendor who bundles compute pricing into a single flat or subscription charge cannot populate 5.7's per-attempt cost buckets (provider-billed, token-estimate, etc.) with the same granularity a directly-invoked harness provides. Where this is unresolvable, the fleet's cost must be treated as a new, explicitly-labeled bucket (vendor-opaque-bundled) rather than forced into an existing bucket it doesn't fit.
- **Receipt depth may not exist.** A fleet product oriented around its own end-user UI may not expose attempt-level provenance (which underlying model/credential acted) at all, only an aggregate task outcome. A harness that cannot supply this is not dispatch-eligible under section 5.5's identity model as written today — this is a gate, not a detail to work around quietly.

**Calibration pre-screening gate.** CLAUDE.md's Empirical Capability Assessment Policy requires ≥5 merged-job samples per harness×task-type before routing may rely on it. That bar is the right discipline for an *existing*, already-provisioned harness picking up a new task-type, but it is the wrong first move for a never-integrated fleet-type harness: funding 5 fresh jobs with zero prior signal, across however many task-types, is exactly the "expensive full-range calibration on a new epic" this design should avoid. Instead, before a candidate fleet harness is allowed to begin accruing toward that ≥5-sample bar at all, it passes a single **calibration anchor** check: take one specific, already-completed story with full existing provenance (cost, `pr_review_cycles`, quality, in `capability_ratings`/`cost_entries`) from a task-type with a dense existing sample, replay the identical task spec through the candidate fleet as a non-merging shadow dispatch, and compare the two receipts directly. This anchor run is a **pre-screening gate, not the first of the five samples** — a poor anchor result disqualifies the candidate before any further spend; a good one only earns the fleet the right to begin accruing real, merged-job samples toward the actual bar. The anchor comparison itself is exploratory evidence, not routing-grade data, precisely because it is a single observation rather than a measured distribution.

None of this is implemented or decided in Phase 1/2 (section 7); naming the harness-contract and calibration-gate shape now avoids discovering, after integrating a first fleet vendor, that the receipt schema and the capability-assessment policy both need to be reopened to accommodate it.

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
2. Which transitions require explicit human sign-off in all workspaces, and which may be configured by policy? The spec assumes design approval and high-impact release/merge gates remain reserved unless policy explicitly delegates them. In a multi-tenant deployment, each reserved gate also needs a principal-class: **vendor-reserved** (fixed by synlynk policy regardless of tenant — e.g. the independent-review requirement cannot be disabled by any tenant) versus **tenant-reserved** (the gate exists, but the human who must clear it is the enterprise customer's own approver, not the vendor's). The single-tenant tranche has no vendor/tenant distinction to make; this question is unresolved and must be answered before any multi-tenant admission.
3. What task risk classes and action taxonomy should control autonomous admission? A related, currently unresolved question for multi-tenant deployment: is there one synlynk-defined risk taxonomy that every tenant's policy maps onto, or is the taxonomy itself tenant-configurable above a vendor-enforced floor? The second option is more flexible for enterprise compliance variance but harder to keep consistently auditable across tenants. Not decided; Phase 1/2 (single-tenant) can proceed with one taxonomy regardless of which way this resolves later.
4. What baseline sample sizes and quantitative cost/quality/recovery thresholds should govern the 1→5→10→25→50→100+ promotion ladder?
5. Should parent coordinators be allowed to create proposed child tasks directly, or must every child be admitted by a separate TPM/control-plane role? This draft favors proposals by coordinators and authoritative admission by the control plane.
6. Which cost dimensions are decision-grade and available from each harness/provider, and what constitutes acceptable estimate error? Enterprise customers who bring their own provider credentials (5.7's BYO-provider bucket) introduce a case where synlynk never sees a vendor-billed amount at all — only usage to meter and report. How reporting-grade accuracy is demonstrated for a bucket synlynk doesn't pay for is unresolved.
7. Which local identity/credential mechanisms are in scope for the first vertical slice, including explicit handling of host-auth fallback?
8. What retention, redaction, and privacy policy applies to prompts, diffs, logs, provenance receipts, and external identities?
9. Third-party execution-fleet harnesses (5.10): how is the calibration-anchor story selected (which existing task-type/sample counts as a valid anchor, and who picks it), and what specific pass/fail threshold on the anchor comparison gates a candidate fleet into real ≥5-sample accrual versus disqualifying it outright? Also unresolved: when a fleet cannot itemize cost (vendor-opaque-bundled) or cannot supply attempt-level provenance, is that an automatic dispatch-eligibility failure, or can policy admit it under a reduced-trust tier? Not decided; no fleet integration is implied or scheduled by naming this gate.

## 10. Approval boundary

This document is a draft for discussion. Per the repository's brainstorm-first and design→plan→build rules, it is not an approved spec until Nikhil signs off and the spec is committed. Do not write an implementation plan or dispatch implementation work before that approval.
