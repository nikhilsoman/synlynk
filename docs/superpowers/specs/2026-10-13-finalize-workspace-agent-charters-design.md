# Finalize Workspace Agent Roles, Charters, Responsibilities & SOPs — Design Spec

**GOVERNS:** `story-0ad6c02b`, primary goal `goal-a222b393` (Agent Charter Framework), secondary goal `goal-06758149` (Activate full fleet)

**Status:** Draft — pending user review of this written spec.

**Decide-panel input:** `project-docs/decisions/2026-10-13-finalize-workspace-agent-roles-charters.md` (`.json`) — panel: claude, agy, codex.

## Problem

`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` defines an 8-role org chart (pm, architect, tpm, dev, designer, qa, marketing, synlynk-bot) and marks pm/tpm/qa as "durable." In reality:

- Only `.synlynk/charters/architect.json`, `dev.json`, `qa.json`, and `maintainer.json` exist on disk. There is no `pm.json` or `tpm.json`, despite both being specified as durable.
- `maintainer` is not even one of the original 8 roles — it was added pragmatically (worktree cleanup, policy sync, release cuts, housekeeping) and its durable status was never formally reconciled with the design spec.
- `synlynk-bot` is explicitly documented as "not a role" — a shared automation identity used by durable roles' scheduled/cron-triggered writes, not an activatable agent.
- QA's Support Engineer (`synlynk/support_engineer.py`) is the only durable role concretely shipped and running today.
- TPM's actual built scope (`docs/superpowers/specs/2026-06-23-tpm-agent-design.md`, `synlynk tpm suggest`, cron `0 9 * * 1-5`) operates strictly downstream of an architect-approved plan — it scans for new approved plans, not raw open GitHub issues. This conflicted with the user's original expectation (a 6-step pipeline starting with "TPM picks up open tickets").

The user wants this reconciled into a finalized, written charter set — with every durable role's SOP designed so allocated token/compute quota is never idle from underutilization — and wants all agents activated against that finalized set. Per this project's Brainstorm-First Policy, activation is gated on this spec being approved; it is not part of this spec's scope.

There are 150+ open GitHub issues in this repo, which is the concrete scale this design's intake/triage flow needs to handle.

## Decide-panel findings (consolidated)

Panel (claude, agy, codex) converged on:
- Lock the durable set at **pm, tpm, qa, maintainer**; **architect, dev, designer, marketing** stay on-call.
- Formalize `maintainer.json` as durable rather than inventing a 9th role — it's the closest existing fit for platform-maintenance ownership, and the Worktree Hygiene Protocol's own "30 stale worktrees accumulated because cleanup was only ever reactive" finding is direct evidence a standing owner is needed.
- `synlynk-bot` stays a shared automation identity, never a charter.
- Harness/model selection stays **entirely out of every charter**, per the Empirical Capability Assessment Policy (2026-10-04) — charters define mandate/authority/SOP only; routing is measured, not hand-locked.
- On the raw-issue-intake gap: **expand TPM's charter** to ingest raw GitHub issues directly, converting them into triaged proposals/plans, with architect approval still gating anything becoming an executable plan. (This was contested — see "Decision override" below.)

### Decision override: intake ownership

The panel's majority (codex, agy) recommended TPM own raw intake directly. The user was presented this against their own earlier stated preference (PM owns intake) and explicitly chose to follow the panel's recommendation. **Final: TPM owns raw intake.** PM's role shifts from "scans raw issues" to "approves/prioritizes TPM's drafted intake proposals" — this preserves the spirit of the user's original 6-step pipeline (a human-legible priority-tagging step) without duplicating the polling loop across two roles.

## Finalized role roster

| Role | Durability | Status |
|---|---|---|
| pm | **Durable** (cron-triggered) | New `pm.json` to be written |
| tpm | **Durable** (cron-triggered) | New `tpm.json` to be written, expanded scope |
| qa | **Durable** (always-on, Support Engineer) | Existing `qa.json` — unchanged, durability now formally justified |
| maintainer | **Durable** (cron-triggered) | Existing `maintainer.json` — promoted to formally-durable, SOP addition |
| architect | On-call (per-story dispatch) | Existing `architect.json` — unchanged |
| dev | On-call (per-story dispatch) | Existing `dev.json` — unchanged |
| designer | On-call (per-story dispatch) | No charter file exists yet; out of scope for this spec (no current demand signal — defer until a project actually dispatches a designer role) |
| marketing | On-call (per-story dispatch) | No charter file exists yet; out of scope for this spec (same reason) |
| synlynk-bot | Not a role | Shared automation identity for pm/tpm/qa/maintainer's scheduled writes — no charter |

**Durability model:** per the user's explicit choice, "durable" means **cron-triggered, not always-on** for pm/tpm/maintainer — matching TPM's existing pattern and this project's own GOVERNS-lifecycle-design definition ("durable = cron-triggered + persisted state, not an always-on daemon"). QA is the one exception, already shipped as an always-on Support Engineer process; this spec does not change QA's execution model, only formally documents why it's durable.

This choice directly serves the "don't waste token quota" constraint: a cron-triggered role that finds no work simply exits (near-zero cost), rather than an idle daemon burning baseline resources between events. The idle-avoidance problem this spec solves is therefore narrower: **what does a durable role do on a wake cycle when its primary queue is empty**, not "how do we keep a process busy."

## Per-role charter specifications

### PM (`pm.json`, new)

- **mandate:** "Approve and prioritize TPM's drafted intake proposals; author and reprioritize stories; own the spec-approval gate; block for human sign-off on major decisions (release cuts, budget, charter changes)."
- **autonomous_authorities:** `["approve_priority", "author_story", "approve_spec"]`
- **escalation_triggers:** `["budget_exceeded", "cross_story_conflict", "charter_change_requested"]` — all escalate to human (Nikhil); PM does not self-approve charter changes or budget overrides.
- **behavioral_weights:** `{"verbosity": "concise", "risk_tolerance": "conservative"}`
- **harness_bindings:** omitted (routing stays outside charters per the Empirical Capability Assessment Policy)
- **Wake-cycle SOP:**
  1. Pull TPM's pending-approval queue (proposals TPM drafted from raw issue intake, or new plans awaiting priority sign-off).
  2. For each item: approve, reject with reason, or request rework from TPM.
  3. Tag approved items with a priority (this is the "PM triages and tags priority" step from the user's original pipeline — now applied to TPM's drafted proposals rather than raw issues).
  4. **Idle-avoidance:** if the approval queue is empty, do not exit immediately — reconcile open stories/goals against `state.db` (stale status, orphaned links, goals with no linked story) before exiting. An empty queue means "nothing new to approve," not "nothing useful to do."

### TPM (`tpm.json`, new, expanded scope)

- **mandate:** "Convert the open-issue backlog into dispatchable, tracked work. Own raw-issue intake, deduplication, and draft-plan authoring; track dispatched work through its lifecycle stages."
- **autonomous_authorities:** `["triage_issue", "draft_plan", "dispatch_track"]`
- **escalation_triggers:** `["technical_ambiguity", "priority_ambiguity", "dispatch_blocked_twice"]`
  - `technical_ambiguity` → architect (on-call dispatch)
  - `priority_ambiguity` → pm
  - `dispatch_blocked_twice` → escalate to human (two consecutive blocked/failed dispatch attempts on the same item)
- **behavioral_weights:** `{"verbosity": "concise", "risk_tolerance": "moderate"}`
- **Wake-cycle SOP:**
  1. Poll open GitHub issues not yet seen by this cycle (track last-seen issue number/timestamp in persisted state, not `state.db` re-scan of everything every time).
  2. Dedupe/cluster against existing open stories (avoid re-triaging the same backlog item every wake cycle).
  3. For genuinely new items: draft a reproduction/verification spec outline (not a full architect-level spec — a scoping draft).
  4. Route ambiguity: technical uncertainty → architect; priority/scope uncertainty → pm. Items with neither ambiguity go straight into PM's approval queue as a drafted proposal.
  5. On PM approval: convert the proposal into a tracked plan/story (existing `synlynk story create` + `synlynk goal link` mechanics), per the existing GOVERNS-lifecycle event contract — this is not a second independent tracking mechanism.
  6. Continue tracking previously-dispatched work (existing `synlynk tpm suggest` scope) through completion.
  7. **Idle-avoidance:** if there is no new dispatch work to propose (step 6 queue empty), fall back to step 1 (raw backlog triage) rather than exiting. An empty dispatch queue never means idle for TPM — it means "go triage more backlog."

### QA (`qa.json`, unchanged)

No charter changes. This spec formally documents *why* QA is durable: it already runs as an always-on process (`synlynk/support_engineer.py`), and its own continuous-ticket-triage behavior already satisfies the idle-avoidance principle this spec applies to pm/tpm/maintainer. No action item against the file itself.

### Maintainer (`maintainer.json`, promoted to formally-durable)

- **mandate:** unchanged ("Maintain workspace hygiene: worktree cleanup, policy sync, release cuts, and long-running housekeeping tasks.")
- **autonomous_authorities:** unchanged (`worktree_cleanup`, `policy_sync`, `release_cut`)
- **escalation_triggers:** unchanged (`invariant_violation_detected`, `budget_exceeded`, `irreversible_action_required`)
- **New field:** `"durability": "durable"` (was implicit/undeclared before this spec)
- **New SOP addition — idle-avoidance:** when there is no pending cleanup/release work (no merged-and-unswept worktrees, no policy drift, no release queued), run a proactive dependency/policy-drift sweep (check for outdated `.synlynk/policy.json` fields against current config schema, stale GitHub label sets, orphaned branches with no PR) rather than exiting with nothing done. This directly answers "ensure one of the durable agents is responsible for maintenance of the platform" — maintainer is that agent, and this SOP addition is what keeps it from being idle between the reactive triggers (merge events) that currently drive most of its work.

### Architect / Dev / Designer / Marketing (unchanged)

Stay on-call, dispatched per-story. No idle-quota concern applies to on-call roles — they are not continuously allocated between dispatches, so there's no idle window to design against. No charter changes from this spec. (Designer and marketing have no charter files yet at all; writing those is out of scope here — nothing in this investigation surfaced demand for them, and inventing charters with no dispatch history to ground them in would violate YAGNI.)

## Out of scope for this spec

- Writing designer/marketing charter files (no current demand signal).
- Any change to `.synlynk/policy.json`'s `task_allocation` or harness routing — charters and routing are deliberately kept separate per the Empirical Capability Assessment Policy.
- Actually creating `pm.json`/`tpm.json`, editing `maintainer.json`, or wiring any cron entries — deferred to the implementation plan written after this spec is approved.
- **Activating any agent.** Per the Brainstorm-First Policy, activation happens only after this spec is approved and an implementation plan executes it — this spec defines what gets activated, not the activation itself.
- Redesigning `synlynk tpm suggest`'s existing downstream-of-approved-plan tracking logic — only its intake front-door is expanded; existing tracking behavior (step 6 above) is preserved as-is.

## Next steps after approval

Write an implementation plan (`superpowers:writing-plans`) covering: writing `pm.json` and `tpm.json`, adding the `durability` field + idle-avoidance SOP note to `maintainer.json`, any cron-install wiring needed for pm/tpm (mirroring TPM's existing `--install-cron` pattern), and tests verifying each new charter loads correctly and matches this spec's SOP fields. Scoped under `story-0ad6c02b`.
