# Roadmap Reconciliation and Release Sequencing Design

Date: 2026-10-20  
Status: Approved by Nikhil Soman, 2026-10-20  
Decision: `dec-f8835ba3` (`project-docs/decisions/2026-10-20-roadmap-reconciliation-decision-assess-a.md`)

---

## 1. Purpose

Replace the overlapping Developer Preview, Wave, and future-release arcs with one dependency-ordered delivery sequence. The sequence prioritizes trustworthy execution before autonomy, autonomy before public distribution, and evidence before any Developer Preview decision.

This design is a planning and state-reconciliation specification. It authorizes neither implementation work nor a Dev Preview date.

## 2. Canonical-State Rules

- The canonical product state is `~/.synlynk/workspaces/synlynk/state.db`.
- GitHub Issues and pull requests are the durable external delivery record.
- `project-docs/{roadmap,todo,costs}.md` are generated projections, never a second authority.
- Every active delivery story has one owning goal, one GitHub issue, and one release phase. A phase may aggregate stories, but must name its parent epic and exit evidence.
- Old dispatch and review artifacts are archived or linked as evidence, not counted as delivery stories.

## 3. Supersession Policy

The following records preserve history but cannot remain parallel release plans:

| Existing arc | Disposition |
|---|---|
| `1.0.0` Developer Preview Public Launch | Supersede into the v0.25.2--v0.27.2 evidence-gated path. |
| `v1.0.0-rc1` 15-Minute First Win | Supersede into v0.27.1 onboarding and its journey evidence. |
| `v1.0.0-preview` | Supersede into this sequence; retain only as planning history. |
| `v0.25.0` and `v0.25.1` | Preserve as published historical releases; do not reuse. |
| Commercial/Tokq `v1.0.0` | Keep long-horizon and outside this delivery sequence. |

No record is deleted merely to simplify the display. Each supersession must reference this specification and its successor release phase.

## 4. Canonical Release Sequence

### v0.25.2 -- Model Catalog Recovery

**Primary goals:** `goal-3ef62232`, `goal-005ea87d`.

**Scope:** LIVE-27 parent #2441 and children #2447--#2450, plus #2454.

**Exit evidence:** each supported harness resolves an allowlisted active model at every requested tier; dirty historical rows cannot re-enter the catalog; fleet-wide invariants and real dispatch compatibility tests pass.

### v0.25.3 -- Trust Contracts: Authority, Completion, Attribution, and Cost

**Primary goals:** `goal-adb60ccc`, `goal-079e2f37`, `goal-eacab0dc`.

**Scope:** task-bound human approval, role and credential enforcement, one-terminal-outcome contract, receipt-to-commit/PR linkage, failed-retry accounting, provider-compatible rerouting, and bounded spend reservation/cancellation.

**Exit evidence:** no unresolved Sev1/Sev2 truth defect; a multi-harness test matrix proves authorization, completion, model/provider attribution, and cost reconciliation; an unverified outcome never reports success.

### v0.25.4 -- Canonical State and Release Integrity

**Primary goals:** `goal-079e2f37`, `goal-9ef9a965`, `goal-eacab0dc`.

**Scope:** #1926/#1831 state consolidation, #2321 release-command repair, #1914 single version source, durable outbox/projections, sidecar generated documents, release provenance, read-only status/recovery, and launcher reliability (#2442).

**Exit evidence:** canonical DB resolution fails closed; generated projections cannot create a second truth; release and roadmap commands mutate the intended state and are covered by tests; a fresh checkout reports the same release status as GitHub.

### v0.26.0 -- Supervised Execution and Daemon Reliability

**Primary goals:** `goal-bd5eaa14`, `goal-06758149`, `goal-eacab0dc`.

**Scope:** daemon startup/restart/lock health, charter/skill/authority and credential checks, cancellation, replay, recovery, and policy-visible GitHub-write provenance.

**Exit evidence:** a daemon cannot dispatch work without enforceable role, charter, credential, and approval checks; restart/replay/cancellation journeys are repeatable and leave one truthful terminal record.

### v0.26.1 -- Workspace-Agent and Team Operations Hardening

**Primary goals:** `goal-eacab0dc`, `goal-a222b393`, `goal-06758149`.

**Exit evidence:** charter-required skills, authority boundaries, and fallback provenance have positive and negative tests; role-scoped GitHub operations are auditable.

### v0.26.2 -- Evidence-Gated Supervised Autonomy

**Primary goals:** `goal-bd5eaa14`, `goal-eacab0dc`.

**Containment gate:** document and enforce credential and egress boundaries for untrusted or credentialed execution. Worktree isolation alone is insufficient.

**Exit evidence:** clean supervised-autonomy telemetry, bounded budgets, revocation, cancellation, crash recovery, and budget-overshoot journeys. No unrestricted-autonomy expansion is permitted by this release.

### v0.27.0 -- Developer Surfaces

**Primary goals:** `goal-e3840370`, `goal-85656c82`.

**Exit evidence:** VS Code uses a stable observation/command API, retains CLI as the reference substrate, and supports inspectable jobs, goals, logs, and worktree diffs.

### v0.27.1 -- Onboarding and First-Win

**Primary goals:** `goal-e47ee312`, `goal-85656c82`, `goal-9ef9a965`.

**Exit evidence:** five external clean-workspace journeys complete a useful task in under 15 minutes without maintainer intervention. Evidence includes fresh-machine, offline/dependency failure, dirty repository, interruption, and rollback paths.

### v0.27.2 -- Marketplace Distribution

**Primary goals:** `goal-9ef9a965`, `goal-85656c82`.

**Exit evidence:** signed/packageable VSIX, validated Visual Studio Marketplace and Open VSX publishing, user-facing installation/recovery documentation, and no marketplace claim beyond observed behavior.

### v0.28.0 -- Bounded Swarms and Universal Gateway

**Primary goals:** `goal-256d17d6`, `goal-8d34c416`, `goal-005ea87d`.

**Gate:** v0.26.2 clean telemetry plus a serial baseline. Fan-out, conflict, and speculative-cost budgets are mandatory.

### v0.28.1 -- Capability Crawler, Index, and GTM Evidence

**Primary goals:** `goal-aa48c456`, `goal-20bb3987`.

**Exit evidence:** reproducible crawler/calibration receipts, no synthetic ratings presented as production evidence, and a design-partner validation of the Index, Prompt Oracle, and preflight value proposition.

### v0.29.0 -- Backlog Consolidation

**Rule:** Every remaining active story is assigned to a later goal/release, superseded with a successor, archived as an artifact, or justified as ongoing maintenance. No speculative expansion enters this release without a new approved specification.

## 5. Review Recommendation Coverage

| Review theme | Delivery home | Required proof |
|---|---|---|
| Supervised safety and authority | v0.25.3--v0.26.0 | Denied paths, approval provenance, role/credential checks |
| Completion and job truth | v0.25.3 | Receipts bind to commits/PRs; no false success |
| Capability attribution and cost/budgets | v0.25.2--v0.25.3 | Valid catalog, attributable attempts, bounded cost |
| State and document truth | v0.25.4 | One DB, deterministic projections, release provenance |
| Containment | v0.26.2 gate | Explicit egress/credential boundary evidence |
| Surface tiering | v0.27.0 | Thin client; CLI remains reference substrate |
| Onboarding and journey validation | v0.27.1 | Five independent first-win receipts |
| Distribution | v0.27.2 | Marketplace publishing only after onboarding gate |
| Swarms, gateway, crawler, Index, GTM | v0.28.x | Post-preview, evidence-gated |
| Scope discipline | v0.29.0 | Explicit defer/supersede/archive dispositions |

## 6. Migration Acceptance Criteria

1. There is one active roadmap arc for each release in Section 4 and no competing Developer Preview arc.
2. Each active phase has an owning goal, parent GitHub epic, linked stories, linked tickets, priority, and exit evidence.
3. Each active delivery story has exactly one goal and one GitHub issue.
4. Ad-hoc dispatch and review artifacts are archived or linked as evidence, not counted as delivery work.
5. The migration produces an auditable disposition report for every currently ungoaled or unticketed active story.
6. A Dev Preview remains a human decision after the v0.25.x truth, v0.26.x reliability/authority, and v0.27.1 journey gates pass; it is not implied by a calendar target.
