# Road to Autonomous Operations

**Date:** 2026-08-10  
**Target:** Public Autonomous Development Loop Preview by 2026-10-01  
**Status:** Strategy roadmap; implementation requires an approved spec

## Objective

Make Synlynk a full-stack autonomous development system that can turn periodic product-strategy conversations into bounded, tracked, verified, and shipped work across Synlynk and related projects.

The target is autonomous execution and continuity, not autonomous strategic commitment. Human approval remains required for major product decisions, scope changes, security or GitHub policy changes, irreversible merges where required, and named releases.

## Target operating loop

```text
Strategy conversation
  -> PM extracts goal and decisions
  -> Architect creates or approves spec and plan
  -> TPM creates stories, assigns work, and tracks evidence
  -> Dev/design harnesses execute under quota gates
  -> QA verifies
  -> PR/review/merge pipeline completes
  -> Devlog, costs, GitHub Issues, roadmap, and todo reconcile
  -> Human approves major decisions and releases
```

## Current position

| Capability | Position |
|---|---|
| Multi-harness dispatch and routing | Strong |
| Worktrees, jobs, retries, and handoff | Strong foundation; operational edge cases remain |
| Cost and quota controls | Strong foundation; pricing/provenance still maturing |
| Ground-truth verification | Recently substantially improved |
| GitHub identity and write safety | Strong foundation |
| Goal/story model | Exists; attribution remains incomplete |
| Specs, plans, and story workflow | Exists; still partly manual |
| Durable TPM tasking loop | Designed; not fully realized |
| Devlog/session continuity | Exists; mostly summary-based |
| GitHub Issue reconciliation | Partial |
| Strategy conversation to executable plan | Mostly manual |
| Fully autonomous closed loop | Not yet built |

The execution substrate is approximately 60-70% complete. The autonomous operating loop is approximately 25-35% complete. These are directional assessments, not product metrics.

The primary gap is orchestration continuity: session capture, goal attribution, TPM reconciliation, and bounded progression between lifecycle stages. More harness infrastructure is not the immediate priority.

## Operating ownership

- **PM:** represents the human, owns strategic intent, prioritization, and major decisions.
- **Architect:** owns technical design, spec/plan approval, review, and merge authority.
- **TPM:** owns the durable tasking, tracking, reconciliation, reporting, and escalation loop.
- **Dev/designer:** execute bounded implementation work through routed harnesses.
- **QA:** owns verification, CI/CD, and deployment quality.
- **GOVERNS:** remains the lifecycle enforcement and attention authority.
- **SQLite:** remains the shared canonical state store.
- **Devlog:** remains the narrative continuity record.
- **GitHub:** remains the external collaboration surface, synchronized but not treated as the local roadmap authority.

TPM operates shared canonical state; it must not create a private activity database or a second source of truth.

## Autopilot available immediately

Synlynk can operate in an “autopilot-lite” mode today:

1. Start each session with one active goal and one primary repository scope.
2. Convert a strategy conversation into one goal, a short outcome statement, 3-7 executable stories, and explicit non-goals.
3. Link every story to the goal before marking it ready.
4. Use `synlynk schedule --execute` for bounded execution instead of unconstrained parallel dispatch.
5. Keep parallelism low: one or two active jobs with explicit token estimates and quota reservations.
6. Run `synlynk jobs`, `synlynk ops`, `synlynk pr check`, and `synlynk checkpoint` at task boundaries.
7. Keep human gates for strategic changes, scope changes, security/GitHub policy, merges where required, and releases.
8. Record the session narrative in the devlog; treat SQLite, job, and GitHub data as evidence.

Use one orchestrator harness for PM/TPM work and route implementation to the best specialist harness. Do not make all harnesses deliberate on every cycle; that is expensive and currently unreliable.

## Minimum build for October 1, 2026

The public target is an **Autonomous Development Loop Preview**, not the complete Tokq or portable-agent vision.

### 1. Finish the governance contract

Resolve the roadmap-governance strategy with these boundaries:

- TPM owns reconciliation and task tracking.
- SQLite owns shared canonical state.
- GOVERNS owns lifecycle enforcement.
- PM owns escalation and human decisions.
- Devlog owns narrative continuity.
- GitHub Issues are synchronized external work, not automatic roadmap commitments.

Then write one approved implementation spec. Do not begin with a broad agent framework.

### 2. Build the smallest TPM loop

The first durable TPM loop must:

- identify the active session and goal;
- discover jobs, commits, PRs, Issues, decisions, plans, and costs;
- attach evidence to the session/work envelope;
- classify work as goal progress, maintenance, exploration, parked, or needs attribution;
- nudge on unresolved attribution;
- produce the next recommended story.

### 3. Add session and devlog capture

Implement only:

```text
session open
session status
session checkpoint
session close
```

Each session should create a session ID, project scope, intended goal, opening devlog entry, evidence links, and closing disposition. Full transcripts may remain local append-only artifacts indexed from SQLite; they should not be injected into normal context.

### 4. Connect GitHub Issues and PRs

The preview should support:

- explicit `--issue N` and `#N` references mapping to stories;
- `external_untriaged` for Issues without local disposition;
- PR and Issue closure updating evidence;
- visible sync failures rather than treating unavailable GitHub data as zero work;
- confirmation before promoting an Issue into a goal.

This is attribution and visibility, not a complete GitHub synchronization product.

### 5. Close the execution loop

The preview must demonstrate:

```text
goal
-> plan
-> stories
-> quota-aware schedule
-> dispatch
-> verification
-> PR
-> review/merge gate
-> costs
-> devlog
-> roadmap/todo reconciliation
```

Reuse existing routing, reservations, worktrees, GOVERNS nudges, and ground-truth job checks. The new work should connect them rather than replace them.

## Weekly sequence

### 2026-08-10 to 2026-08-16: Contract and dogfood

- Resolve the roadmap-governance strategy.
- Approve the Autonomous Development Loop implementation spec.
- Choose one real Synlynk goal.
- Run the loop manually across Synlynk and one related project.
- Measure attribution failures and prompt friction.

### 2026-08-17 to 2026-08-30: TPM/session MVP

- Add the session/work-envelope schema.
- Link devlog entries to sessions and goals.
- Inherit session and goal IDs through dispatch and story creation.
- Add checkpoint reconciliation.
- Add the first durable TPM loop and nudges.

### 2026-08-31 to 2026-09-13: Evidence and GitHub integration

- Add Issue/PR mirror fields and provenance.
- Add `external_untriaged` state.
- Link commits, jobs, decisions, plans, PRs, Issues, and costs.
- Extend GOVERNS events.
- Add release-scope attribution reporting.

### 2026-09-14 to 2026-09-24: Multi-project dogfood

Exercise the loop across Synlynk, rxcc, and vdowrx with bounded quotas, low parallelism, real Issue/PR workflows, deliberate scope changes, and failure/handoff cases.

### 2026-09-25 to 2026-10-01: Public preview hardening

- Document the operating model and limitations.
- Add a narrow `synlynk autopilot` entry point only if the underlying loop is stable.
- Publish measured results.
- Release only if the gates below pass.

## Release gates

The October 1 preview requires:

- 100% of terminal jobs have cost data or explicit `cost_missing` status.
- 100% of meaningful work has a disposition within one checkpoint.
- No unreviewed autonomous merge or release.
- No quota bypasses.
- No increase in verified rework from automation.
- Ordinary session closeout takes under one minute.
- GitHub Issues in configured scope are linked, parked, or marked out of scope.
- GitHub sync failures are visible and attributable.
- At least one complete multi-project dogfood cycle succeeds.
- Failed or abandoned jobs do not lose their devlog or attribution evidence.

## Scope exclusions for this release

Do not make the October preview depend on:

- full Agent manifest/configuration infrastructure;
- portable implants or Tokq deployment;
- hosted/team state synchronization;
- universal automatic intent classification;
- all-harness consensus on every decision;
- autonomous strategic goal promotion;
- fully autonomous release publishing.

These remain future phases after the local autonomous loop proves useful and sustainable.

## Decision

Make TPM the accountable owner of the autonomous operating loop now, while keeping the underlying state shared across devlog, GOVERNS, SQLite, GitHub, and all other roles. Build the smallest closed loop that converts a strategy conversation into bounded, quota-aware, verified work and reconciles its evidence. Dogfood it immediately, then ship the measured Autonomous Development Loop Preview by 2026-10-01.
