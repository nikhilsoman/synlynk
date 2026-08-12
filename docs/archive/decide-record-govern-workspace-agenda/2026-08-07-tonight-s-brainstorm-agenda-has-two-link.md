---
decision_id: dec-e92949e1
topic: "Tonight's brainstorm agenda has two linked topics.

TOPIC 1 — Close the GOVERNS lifecycle enforcement gap (goal-90e73dfd). PR #464 shipped the advisory instruction TEXT (render_lifecycle_checkpoint_section() in synlynk/instructions.py, verbatim-tested) that tells agents to suggest 'synlynk goal create' at spec-approval and plan-approval moments — but nothing enforces it. Proof: goal_contributions table was found completely empty before this session; goal-90e73dfd itself was unlinked to any story. The original spec (docs/superpowers/specs/2026-07-23-governs-lifecycle-engagement-design.md) explicitly deferred two preconditions before going further: (1) real maturity-tier detection to replace the hardcoded _current_trigger_registry_tier() returning Tier 2, and (2) one release cycle of telemetry on suggestion-shown vs suggestion-accepted rates. Neither is built. Also missing: any 'synlynk story <id> done' command (stories can be created/linked but never marked complete), and no automated check that a merged spec/plan-derived PR has a linked GOVERNS goal. The user also wants this goal's scope to include a NEW capability: a synlynk workspace agent proactively nudging the user at task boundaries with next-steps/new-initiatives/next-goal-stage suggestions (not just passive instruction text).

TOPIC 2 — Revive and activate 'Synlynk workspace agents': SFIA-taxonomy-associated knowledge-worker roles meant to be durable per-project assistants (not just per-task dispatch workers). Prior art: 4 named-role specs from 2026-06 (Support Engineer — SHIPPED as synlynk/support_engineer.py + synlynk agent run/add/list + GH Actions cron; Release Agent — spec only, never built, no release-agent.json or release suggest/run/status surface exists despite a basic 'synlynk release' version-bump command existing; TPM Agent — spec only, 'tpm' exists only as a bare role-label string in synlynk/db.py, no lifecycle engine; Grok Agent Support — implemented, but as an ephemeral per-task dispatch worker, not a durable role). The archive files (docs/archive/synlynk-agent-workers-assessment.md, synlynk-agent-workers-git-managed.md, multi-agent-implementation-plan.md) never actually define what 'permanent' means — they cover per-task GitHub-contributor routing/attribution infra, not standing/durable agent processes. SFIA capability-scoring infra (synlynk/taxonomy_standards.py, synlynk/capability_sweep.py) exists but is used for ephemeral-dispatch calibration, not role identity. A 2026-07-25 decision already approved per-role GitHub App identity (scoped .pem/JWT tokens per dispatched role) — closest existing 'durability' primitive. The user wants a new goal: activate the full workspace-agent fleet with a custom set of roles per active project (rxcc, cc-videoreframing, playblazer-ng, synlynk itself).

Give each panel agent's perspective on: what should tonight's brainstorm actually decide vs defer, what's the minimum viable first slice for each topic, and any risk/sequencing dependency between Topic 1 and Topic 2 (e.g., should workspace-agent activation itself be the mechanism that finally auto-creates/links GOVERNS goals and stories, closing both gaps with one design instead of two separate builds?)."
date: 2026-08-07
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Tonight's brainstorm agenda has two linked topics.

TOPIC 1 — Close the GOVERNS lifecycle enforcement gap (goal-90e73dfd). PR #464 shipped the advisory instruction TEXT (render_lifecycle_checkpoint_section() in synlynk/instructions.py, verbatim-tested) that tells agents to suggest 'synlynk goal create' at spec-approval and plan-approval moments — but nothing enforces it. Proof: goal_contributions table was found completely empty before this session; goal-90e73dfd itself was unlinked to any story. The original spec (docs/superpowers/specs/2026-07-23-governs-lifecycle-engagement-design.md) explicitly deferred two preconditions before going further: (1) real maturity-tier detection to replace the hardcoded _current_trigger_registry_tier() returning Tier 2, and (2) one release cycle of telemetry on suggestion-shown vs suggestion-accepted rates. Neither is built. Also missing: any 'synlynk story <id> done' command (stories can be created/linked but never marked complete), and no automated check that a merged spec/plan-derived PR has a linked GOVERNS goal. The user also wants this goal's scope to include a NEW capability: a synlynk workspace agent proactively nudging the user at task boundaries with next-steps/new-initiatives/next-goal-stage suggestions (not just passive instruction text).

TOPIC 2 — Revive and activate 'Synlynk workspace agents': SFIA-taxonomy-associated knowledge-worker roles meant to be durable per-project assistants (not just per-task dispatch workers). Prior art: 4 named-role specs from 2026-06 (Support Engineer — SHIPPED as synlynk/support_engineer.py + synlynk agent run/add/list + GH Actions cron; Release Agent — spec only, never built, no release-agent.json or release suggest/run/status surface exists despite a basic 'synlynk release' version-bump command existing; TPM Agent — spec only, 'tpm' exists only as a bare role-label string in synlynk/db.py, no lifecycle engine; Grok Agent Support — implemented, but as an ephemeral per-task dispatch worker, not a durable role). The archive files (docs/archive/synlynk-agent-workers-assessment.md, synlynk-agent-workers-git-managed.md, multi-agent-implementation-plan.md) never actually define what 'permanent' means — they cover per-task GitHub-contributor routing/attribution infra, not standing/durable agent processes. SFIA capability-scoring infra (synlynk/taxonomy_standards.py, synlynk/capability_sweep.py) exists but is used for ephemeral-dispatch calibration, not role identity. A 2026-07-25 decision already approved per-role GitHub App identity (scoped .pem/JWT tokens per dispatched role) — closest existing 'durability' primitive. The user wants a new goal: activate the full workspace-agent fleet with a custom set of roles per active project (rxcc, cc-videoreframing, playblazer-ng, synlynk itself).

Give each panel agent's perspective on: what should tonight's brainstorm actually decide vs defer, what's the minimum viable first slice for each topic, and any risk/sequencing dependency between Topic 1 and Topic 2 (e.g., should workspace-agent activation itself be the mechanism that finally auto-creates/links GOVERNS goals and stories, closing both gaps with one design instead of two separate builds?).

## Panel Inputs

### claude
**Sequencing dependency is the crux.** Topic 2's durability primitive (per-role GitHub App identity, approved 2026-07-25) is the only thing in either topic that behaves like a standing process rather than an ephemeral dispatch. If a workspace agent literally *runs* at spec-approval/plan-approval/PR-merge boundaries — rather than an instruction string hoping the dispatched agent complies — it can call `synlynk goal create`/`link` itself, closing Topic 1's enforcement gap as a side effect of Topic 2's activation. Building them separately risks a second advisory-text layer that also gets ignored, which is exactly what happened to PR #464.

**What to decide tonight:** commit to the merged design — workspace-agent activation *is* the GOVERNS enforcement mechanism, not a parallel effort. Pick one role (Support Engineer is already shipped and durable via GH Actions cron — reuse its skeleton) and give it exactly one new responsibility: detect spec/plan-approval and PR-merge events, and auto-create/link the GOVERNS goal/story. That's the minimum viable first slice — no new taxonomy work, no Release/TPM agent builds tonight.

**What to defer:** real maturity-tier detection and the telemetry cycle (Topic 1's original preconditions) — these tune the nudge, they don't block a first automated link. Also defer Release Agent and TPM Agent builds, the proactive "next-steps/new-initiatives" nudging capability (that's a UX layer on top of a mechanism that doesn't exist yet — sequence it after one role proves the pattern), and per-project custom role sets for rxcc/cc-videoreframing/playblazer-ng (multiplies scope before the single-role mechanism is validated in synlynk itself). Also skip `story done` command design tonight — needed eventually but not blocking.

**My position:** treat this as one goal, not two. Ship a single durable Support-Engineer-pattern role in synlynk that auto-links GOVERNS goals/stories on spec/plan/PR events as its first and only new capability. Everything else — other roles, other projects, proactive nudging, telemetry-driven tier detection — is explicitly out of scope for tonight and becomes goal-90e73dfd's next stage once this slice has real usage data.

### agy
Last completed task: Structured technical code review of PR #51 (Codex Headless Dispatch).
Next task: Refine decision flow templates for agents (`todo.md`).

### Decision Panel Analysis

**Architect Perspective:**
Topics 1 and 2 should not be built as isolated systems. Attempting to enforce GOVERNS lifecycle checkpoints through passive prompt text or rigid CLI hooks is fragile. Activating durable **Synlynk Workspace Agents** (specifically the TPM Agent) provides the runtime engine required for both proactive task-boundary nudging and automated goal/story lifecycle enforcement.

**Product & Process Lead Perspective:**
* **Decide Tonight:**
  1. **Architectural Coupling:** Formally approve using TPM Workspace Agents as the proactive driver for GOVERNS lifecycle enforcement.
  2. **Core Primitives:** Spec the missing `synlynk story <id> done` command and a pre-merge CI check for linked GOVERNS goals.
  3. **Role Scope:** Select the initial target projects (`synlynk` and `rxcc`) for workspace agent fleet activation using per-role GitHub App identities.
* **Defer Tonight:** Complex maturity-tier detection algorithms (retain Tier 2 default) and full telemetry capture for suggestion acceptance rates.

**Minimum Viable First Slice:**
* **Topic 1 (Lifecycle):** Implement `synlynk story <id> done` and a lightweight PR validation check enforcing GOVERNS goal linkages on merged spec/plan PRs.
* **Topic 2 (Agents):** Deploy the TPM Agent in `synlynk` leveraging per-role GitHub App JWT auth to execute proactive nudges at task boundaries and auto-create missing story links.

**Risk & Sequencing Dependency:**
Building separate passive enforcement scripts prior to workspace agent activation risks duplication and throwaway code. Sequencing workspace agent activation first—or as the core mechanism—eliminates redundant designs. However, the primary risk is agent over-solicitation; proactive nudging must be strictly bounded to git commit/PR/task completion events.

### Recommendation & Final Position

**Position:** I strongly recommend unifying Topic 1 and Topic 2 under a single design initiative. Tonight's brainstorm should decide to deploy the TPM Workspace Agent as the active enforcement and nudging engine. By leveraging the TPM agent to observe task boundaries, prompt users with next steps, and enforce goal linkage prior to PR merges, we resolve the GOVERNS enforcement gap and activate durable workspace agents in a single, cohesive build.

### codex
**Governance/enforcement perspective:** Tonight should decide the minimum enforceable GOVERNS lifecycle contract: when spec/plan approval creates or links a goal, how stories transition to done, and what CI blocks a merged derived PR lacking a linked goal. The first slice should include `synlynk story <id> done`, persistent goal/story linkage, and a merged-PR validation check. Defer real maturity-tier detection and suggestion-acceptance telemetry until the contract is instrumented; they are prerequisites for optimizing prompts, not prerequisites for basic enforcement.

**Workspace-agent/product perspective:** Decide what “permanent” means operationally: project-scoped configuration, durable identity, scheduled/event-driven execution, state persistence, and explicit user-visible boundaries. The first slice should activate one role—preferably Support Engineer, since it already ships—as a durable workspace agent in one project, with configurable role metadata, `run/status`, persisted state, and task-boundary nudges for next steps, new initiatives, and the next goal stage. Defer the entire multi-role fleet and bespoke role design across all four projects until this lifecycle is proven.

**Architecture/operations perspective:** Avoid treating per-task dispatch workers as workspace agents. Reuse the approved per-role GitHub App identity, but add a project/role registry and event model rather than cloning dispatch machinery. Activation should emit auditable events and telemetry. The main sequencing risk is building autonomous nudges before permissions, suppression rules, and user opt-in are defined; that could create noise or unexpected mutations.

The two topics should be coupled, but not collapsed into one opaque build. I recommend making workspace-agent activation the eventual orchestration layer for goal/story suggestions and links, while first shipping a narrow shared lifecycle service and CLI/CI enforcement. In other words: decide the common event and data contracts tonight; implement GOVERNS enforcement plus one durable Support Engineer pilot first; defer maturity detection, telemetry-based tuning, and fleet-wide activation. This closes the correctness gap quickly while creating a credible path for agents to become the mechanism that maintains GOVERNS state.

### grok
I'll ground this in the existing specs and implementation surface so the panel recommendation is specific, not abstract.## Grok panel input — GOVERNS gap × workspace agents

### Decide tonight (not defer)

1. **One product object, two surfaces.** Define “workspace agent” as a durable *role identity* (config + schedule + permissions + optional GH App), not a long-running process. “Permanent” = survives sessions in `.synlynk/` / `state.db`, not a daemon that stays up forever.
2. **Where enforcement lives.** Advisory text already failed (`goal_contributions` empty). Decide: **structural hooks first** (CLI + post-approve / post-merge checks), agents **surface** next steps — they must not be the sole enforcer.
3. **Which roles for which repos.** Pick a 1–2 role pilot set per active project; do not greenlight the full fleet.
4. **Sequencing:** Topic 1 primitives before Topic 2 personality. Without `story done`, goal/story link invariants, and a checkpoint hook, a TPM/PM agent has nothing reliable to nudge.

### Defer

- Real maturity-tier detection and suggestion-acceptance telemetry (still correct gates for *broad hard defaults*, not for a narrow mechanical MVP).
- Release Agent / full TPM lifecycle engine / multi-project fleet activation.
- Hard-blocking CI on “every merged PR has a GOVERNS goal” until false-positive cost is measured on maintenance/chore PRs.

### MVP slices

**Topic 1 (lifecycle):**  
(1) `synlynk story <id> done` (close the half-open lifecycle),  
(2) `goal link` at plan-approve as a **synlynk CLI/skill hook** that writes `goal_contributions` / primary `goal_id` (soft-fail with explicit skip reason, not silent skip),  
(3) optional `synlynk pr check` warning when a plan/spec-derived PR has no linked goal. Ship telemetry counters *with* the hook so the deferred gate gets data without a separate “telemetry project.”

**Topic 2 (agents):**  
One durable role on **synlynk itself** first — prefer **Support Engineer pattern** (config + `agent run` + cron) extended to a thin **PM/nudge** role: at task boundaries, emit next-step / next-goal-stage suggestions from `goal`/`story`/`todo` state. No new process model; reuse Support Engineer’s durability shell + per-role identity.

### Dependency

**Do not merge designs into one build.** Workspace-agent activation should *consume* GOVERNS state; it should not invent goal creation semantics. Shared design decision tonight: checkpoint events (`spec approved`, `plan approved`, `story done`, `PR merged`) are a single event bus both topics listen to. Build the bus + story/goal completeness in Topic 1; Topic 2 is the proactive consumer.

**Position:** Tonight’s brainstorm should **ratify the event-bus + durability definition, freeze a two-step MVP (lifecycle primitives → one PM-nudge agent on synlynk), and explicitly reject “agents will enforce GOVERNS by reading instruction text.”** Defer fleet activation, Release/TPM full builds, and hard merge gates until the MVP proves contribution rows fill and nudge accept-rate is non-zero.

## Synthesis
Decision: Tonight's brainstorm ratifies a single unified design rather than two parallel builds — workspace-agent activation becomes the mechanism that closes the GOVERNS enforcement gap, but only after mechanical lifecycle primitives exist for it to drive.

**Tonight, decide:**
1. **Unify goal-90e73dfd's scope** — reject the "advisory text + separate agent fleet" split. One event bus (`spec approved`, `plan approved`, `story done`, `PR merged`) is the shared contract both topics consume.
2. **Ship Topic 1's mechanical primitives first, tonight's actual build target:** `synlynk story <id> done`, a `goal link` hook at plan-approval that writes `goal_contributions` with an explicit skip reason on failure (no silent skips — this is what let the table go empty undetected), and a soft-warn (not hard-block) `synlynk pr check` for unlinked GOVERNS goals on spec/plan-derived PRs.
3. **Pilot exactly one durable workspace agent, on synlynk itself, reusing the Support Engineer skeleton** (already shipped, already durable via GH Actions cron + per-role GitHub App identity from 2026-07-25). Extend it with one new responsibility: read goal/story/todo state at task boundaries and surface next-step/next-goal-stage nudges — consuming the event bus from #2, not inventing its own goal-creation semantics.
4. **Define "durable/permanent" operationally now** (config + persisted state in `.synlynk/`/state.db + scheduled/event-driven execution + explicit user-visible boundaries), so it's a reusable definition for future roles, not re-litigated per role.

**Defer explicitly:** real maturity-tier detection and suggestion-acceptance telemetry (tune the nudge later, don't block the mechanism); Release Agent and TPM Agent builds; the full multi-role fleet and per-project custom role sets (rxcc, cc-videoreframing, playblazer-ng); hard CI-blocking on unlinked goals (soft-warn until false-positive rate on chore/maintenance PRs is measured).

**Rationale:** the panel converges that instruction-text enforcement already failed once (PR #464, empty `goal_contributions`), so a second passive layer isn't worth building. But jumping straight to a full agent fleet gives that fleet nothing reliable to enforce or nudge on — Codex and Grok are right that the CLI/data primitives (`story done`, goal linkage, checkpoint events) have to exist first. The one-role pilot proves the pattern cheaply using infrastructure that already exists (Support Engineer shell, per-role GitHub App identity) before multiplying scope across roles or projects.

## Decision
Decision: Tonight's brainstorm ratifies a single unified design rather than two parallel builds — workspace-agent activation becomes the mechanism that closes the GOVERNS enforcement gap, but only after mechanical lifecycle primitives exist for it to drive.

> Signatures: see 2026-08-07-tonight-s-brainstorm-agenda-has-two-link.json
