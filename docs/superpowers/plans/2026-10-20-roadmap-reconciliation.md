# Implementation Plan: Roadmap Reconciliation and Release Sequencing

Date: 2026-10-20  
Spec: `docs/superpowers/specs/2026-10-20-roadmap-reconciliation-design.md`  
Decision: `dec-f8835ba3`  
Branch: `feat/codex/roadmap-reconciliation`

## Objective

Make `state.db` and GitHub express one dependency-ordered release path from
v0.25.2 through v0.29.0, with every active delivery story linked to a goal,
release phase, parent epic, and GitHub issue. Preserve historical evidence;
never silently delete it.

## Phase A: Establish a Reconciliation Baseline

1. Snapshot the canonical DB before every state mutation using the supported
   backup command. Record the snapshot path and checksum in the parent issue.
2. Generate a read-only inventory of roadmap arcs, phases, goals, stories, and
   GitHub issue links from the canonical DB.
3. Classify all active stories into exactly one disposition:
   - delivery work in v0.25.2--v0.29.0;
   - later-goal work outside the current sequence;
   - duplicate/superseded work with successor;
   - archived dispatch/review artifact;
   - ongoing maintenance loop.
4. Produce an auditable CSV/Markdown report containing old ID, disposition,
   successor ID, owning goal, GitHub issue, and rationale.

**Verification:** no DB mutations in the inventory step; counts reconcile to
the canonical DB before and after report generation.

## Phase B: Repair the Roadmap Mutation Path

1. Fix #2321 so `synlynk roadmap add --version` and `synlynk release --version`
   cannot be intercepted by the global version flag.
2. Add regression tests proving both commands update the canonical DB and
   generated sidecar projection, not a checkout-local DB.
3. Fix release metadata single-source behavior under #1914 before any named
   release state is edited.

**Verification:** command-level tests demonstrate a successful mutation, a
non-zero failure on invalid input, and correct canonical DB resolution.

## Phase C: Create the Canonical Release Hierarchy

Create one active arc and one GitHub parent epic for each release below. Use
new delivery goals only where an existing goal cannot truthfully own the work;
otherwise retain existing goal ownership and cross-link the release epic.

| Release | Parent goal(s) | Required parent-epic theme |
|---|---|---|
| v0.25.2 | `goal-3ef62232`, `goal-005ea87d` | Model catalog recovery / LIVE-27 |
| v0.25.3 | `goal-adb60ccc`, `goal-079e2f37`, `goal-eacab0dc` | Trust contracts |
| v0.25.4 | `goal-079e2f37`, `goal-9ef9a965`, `goal-eacab0dc` | Canonical state and release integrity |
| v0.26.0 | `goal-bd5eaa14`, `goal-06758149`, `goal-eacab0dc` | Supervised execution and daemon reliability |
| v0.26.1 | `goal-eacab0dc`, `goal-a222b393`, `goal-06758149` | Workspace-agent operations |
| v0.26.2 | `goal-bd5eaa14`, `goal-eacab0dc` | Evidence-gated supervised autonomy |
| v0.27.0 | `goal-e3840370`, `goal-85656c82` | Developer surfaces |
| v0.27.1 | `goal-e47ee312`, `goal-85656c82`, `goal-9ef9a965` | Onboarding and first-win |
| v0.27.2 | `goal-9ef9a965`, `goal-85656c82` | Marketplace distribution |
| v0.28.0 | `goal-256d17d6`, `goal-8d34c416`, `goal-005ea87d` | Bounded swarms and gateway |
| v0.28.1 | `goal-aa48c456`, `goal-20bb3987` | Capability evidence and GTM |
| v0.29.0 | platform-health owner plus explicit later goals | Backlog consolidation |

For every phase, create or associate a story with a GitHub issue before it is
made ready. Include exit criteria and dependency links in both the issue and
roadmap phase notes.

**Verification:** no active phase has a null story link; no delivery story
lacks a goal or GitHub issue; every parent issue body lists intent, context,
child issues, and acceptance evidence.

## Phase D: Supersede Competing Preview Arcs

1. Mark `1.0.0` Developer Preview Public Launch, `v1.0.0-rc1`, and
   `v1.0.0-preview` as superseded in the canonical DB.
2. Link each former phase to its successor release and story; retain completed
   implementation evidence as historical receipts.
3. Keep published v0.25.0/v0.25.1 immutable and retain commercial/Tokq v1.0.0
   as a separate long-horizon arc.

**Verification:** exactly one active planned path covers each scope area; no
status page presents an implied Developer Preview date.

## Phase E: Release-by-Release Execution Gates

1. Start v0.25.2 only with the LIVE-27 model-catalog parent and children.
   Require all-harness tier resolution and real-dispatch tests.
2. Start v0.25.3 after the v0.25.2 regression suite passes. Require truthful
   completion, approval, attribution, and cost receipts.
3. Start v0.25.4 after v0.25.3. Require one ledger, one projection path, and
   truthful release mechanics.
4. Start v0.26.0 only after enforceable role/credential/approval controls are
   live. Require daemon restart, recovery, cancellation, and replay journeys.
5. Do not start v0.26.2 until the explicit containment gate passes.
6. Require five independent under-15-minute first-win journeys in v0.27.1
   before Open VSX or Marketplace publication in v0.27.2.
7. Keep v0.28.x post-preview and require v0.26.2 clean telemetry before
   swarm/gateway work.

## Phase F: Final Reconciliation Audit

1. Extend `synlynk doctor` or an equivalent read-only audit to report:
   - competing active release arcs;
   - phases without a story;
   - active delivery stories without a goal or issue;
   - stories whose issue is closed while the DB is non-terminal;
   - release status mismatches among the canonical DB, GitHub, and sidecar
     projection.
2. Run the audit against the canonical DB and compare it with GitHub.
3. Post a narrative completion rollup to every affected parent epic.

## Completion Criteria

- The six migration acceptance criteria in the approved design all pass.
- The parent release epics and target stories are visible on GitHub.
- State DB and generated projections report the same release sequence.
- The backlog report accounts for all formerly ungoaled/unticketed active
  stories, without deleting historical receipts.
- No Dev Preview release is created, tagged, or announced by this work.
