# Intent-Based Engineering: Roadmap Drift Governance & Foundational Intent Capture

**Date:** 2026-11-13
**Status:** Approved
**Roadmap entry:** New GOVERNS goal — "Intent-Based Engineering: close the intent-capture and roadmap-drift gaps" — supersedes ad hoc roadmap maintenance with a structurally enforced mechanism.

---

## Context

A review of the planned roadmap (triggered by validating a pasted "takeover brief" claiming authority over GitHub issue #5228) surfaced that `project-docs/roadmap.md` has no entries at all for v0.31–v0.38, despite two ratified decision records (`dec-9b41a7c3`, the authoritative release cadence; `dec-4e81b29a`, the theme prioritization order) describing exactly that range. Investigation found the root cause: the newly-shipped (v0.32.3) GOVERNS/spec-lint enforcement machinery covers goal↔story↔PR linkage, but has no hook into the `roadmap_arcs`/`roadmap_phases` tables, which are only updated by a manual, non-enforced `synlynk roadmap add/update` command. Nothing breaks when a ratified decision never gets materialized into the roadmap tables — the drift is silent.

A second-order finding compounded this: both ratified decision records cite `primary_goal: goal-2458-master-roadmap`, which does not exist in `state.db`'s `goals` table. Even the "authoritative" records have a dangling reference. Separately, `story-ca8afaf8` ("Review + merge PR #2596: synlynk.com platform vision spec") still shows `status: open, readiness: draft` despite the spec file already existing on disk — another place the provenance chain has silently broken.

This spec treats these not as one-off bugs to patch, but as evidence of a missing structural invariant: **every intent must trace an unbroken path — intent → goal → roadmap_phase → decision → spec → plan → story → PR.** That invariant is named **Intent-Based Engineering**, and this spec is both its first formal statement and the mechanism that enforces it, per the project's own standing principle that gates must be structural, not a matter of discipline (`feedback_invariants_always_hold.md`).

---

## Design

### 1. Intent Capture Layer (new)

**Problem:** today, intent enters the system only through a few narrow, inconsistently-used paths (a human manually filing a GitHub issue, or a session manually running `synlynk story create`). Most intent — a eureka moment mid-session, a bug noticed in passing, a half-formed idea in a GitHub comment thread — has nowhere structured to go, so it either gets lost or bypasses the goal/story chain entirely.

**Mechanism:** one shared capture primitive, triggered from three surfaces:

- **Interactive terminal:** `synlynk intent capture "<text>"` — on-demand, callable by any harness/session mid-work. Backstop: at session-end housekeeping (the same moment as the existing devlog-checkpoint step), if a session had non-trivial activity but zero `intent capture` calls, flag it in `sentinel.md` as "possible uncaptured intent from session X" for triage at the next session start. This is a cheap heuristic trip-wire, not a re-scan of the full transcript.
- **Vizor:** a "Flag as Intent" action on any card (story, roadmap phase, cost anomaly) that calls the same capture function Vizor already has `state.db` access for (`synlynk status --json` is its existing data contract). No separate sweep needed — a click is inherently on-demand.
- **GitHub issues/comments:** a periodic poll (daemon tick, same cadence family as the existing TPM GitHub polling in `tpm_sweep.py`) over new issues not yet GOVERNS-linked, and new comments that don't match the `/approve|/revise|/drop|/prioritize|/hold` grammar — i.e., free-text discussion that might be carrying an intent nobody formally filed.

If gaps remain after these three surfaces are live, continuous in-session monitoring is the next escalation — not built now.

**Semantic association (shared resolution logic, run on every captured intent before it's allowed to become a *new* goal):**

1. Title/keyword match against `goals` / `stories` / `roadmap_phases`.
2. Doc-graph (`docgraph.json`) proximity to existing specs/decisions.
3. Code-graph (`impact.py`'s AST graph) resolution if the intent names a file/module — maps to the owning subsystem, then to that subsystem's GOVERNS-linked stories.
4. Policy check against the Semantic Laws seed doc (Section 5 below) and existing ratified decision theme definitions, to catch contradiction or duplication.

Output is one of: attach to an existing goal/story, open a new goal candidate under a theme, or flag orphan/unclear for human triage. Every outcome — including "attach to existing" — posts through the same `/approve /revise /drop /prioritize /hold` proposal protocol the TPM sweep already uses (`process_proposal_comments()`), so nothing becomes a real goal without ratification.

### 2. Roadmap Drift Gate — `synlynk roadmap check`

Diffs two sides:

- **Source of truth:** the `decisions` table's structured fields (`ratified_cadence`, `prioritized_theme_order`, `target_milestone`, `primary_goal`) from every `status: approved` decision record.
- **Materialized side:** `roadmap_arcs` / `roadmap_phases`.

Every mismatch is reported as a `ROADMAP_DRIFT` sentinel (same family as the existing `HARNESS_VERSION_DRIFT` pattern in `check_sentinel_patterns()`): a decision ratifying a cadence/theme-order with no corresponding arc/phase row, an arc/phase row with no backing decision, or a `primary_goal`/`goal_id` reference that doesn't resolve in `goals`. The `goal-2458-master-roadmap` dangling reference and `story-ca8afaf8`'s stale `draft` status become this gate's first real remediation targets (see "Remediation" below).

**Wiring:**
- **Blocking:** added to `synlynk pr check` — any PR touching `project-docs/decisions/*.json` or claiming a `target_release` must pass `roadmap check` clean, fail-closed, same posture as the existing spec-lint gate (`check_pr_spec_gate()`).
- **Standalone:** runnable directly by the PM/Wingman at decision-ratification time or release-cut time, so drift is caught before a PR even exists.

A fully-derived alternative (Approach C — deprecate manual `roadmap add/update` entirely, compute the rendered roadmap directly from `decisions`+`goals`+`stories` every time, eliminating the drift class structurally rather than detecting it) was considered and rejected **for this spec** as too large a table-architecture change to bundle with the governance fix. It is tracked as a follow-up ticket (see "Deferred").

### 3. Orphan Sweep (recurring, advisory)

Walks `docgraph.json` + the AST code graph looking for nodes — specs, decisions, modules — with no resolvable path back to a `goal_id`. Reuses the same graph-walking logic as the drift gate (one shared `find_orphans()` / `diff_roadmap()` module), so the sweep is effectively "the gate's reconciliation logic, run proactively instead of just at PR time."

Folded into two existing cadences rather than inventing a third:
- **On-demand:** a new check in `synlynk doctor`.
- **Unattended:** the daemon's periodic tick (same mechanism driving the TPM wake cycle), writing findings to `sentinel.md` for triage. Advisory, not blocking — an orphan isn't necessarily wrong, just unlinked and worth a human look.

### 4. Enforcement Model

Dual, matching the project's own standing principle — structural enforcement over discipline, with the role as the accountable owner on top:

- **Structural layer:** `roadmap check` in `pr check` + Intent Capture's association step. Code, not discipline.
- **Process layer:** an explicit PM-role duty — "every decision ratification and every release cut runs `roadmap check`" — added to this project's `CLAUDE.md` PR Review Discipline section alongside the existing GOVERNS/cross-harness-review rules.
- **Personal-edition variant — the Wingman charter:** for the single-user Personal tier (no Agent Studio), one agent charter consolidates PM + architect + dev + qa responsibilities. It runs the *same* policy gates (`roadmap check`, GOVERNS linkage, cross-harness review where applicable) at single-agent scale — "lighter" means fewer agents and less infra overhead, never a relaxed ruleset. This is the Personal-tier **default**, not a fallback for when Agent Studio isn't available; Agent Studio is the opt-in scale-up from Wingman to a full multi-role fleet, entirely within Personal — it does not require moving to Team.

### 5. Semantic Laws Seed Doc — `docs/strategy/synlynk-constitution.md`

Explicitly **v1/seed**, not the full Constitution — a deeper, standalone brainstorm is deferred (see "Deferred"). Contents:

1. **Asimov Laws 0-3** — documented in prose for the first time. They currently exist only as code in `evaluate_asimov_invariants()` (shipped v0.32.2), with no canonical written statement anywhere in the repo.
2. **The Intent-Based Engineering invariant** (new, this spec's namesake): every spec, plan, ticket, and roadmap phase must trace an unbroken path — intent → goal → roadmap_phase → decision → spec → plan → story → PR. `roadmap check` and the orphan sweep are its enforcement mechanisms; this doc is where the rule itself is written down as policy, independent of the code that enforces it.

Referenced by both the drift gate (as the thing it enforces) and by Intent Capture's policy-check association step.

### 6. Uber-Roadmap Reorg: Core / Opt-in / Add-on

**The classification rule (one test, not three categories to memorize):** every synlynk capability is classified by **who bears its marginal cost of existing**.

| Bears the cost | Category | Examples |
|---|---|---|
| Nobody extra — it's the local runtime itself | **Core** | `state.db`/worktree isolation, AST code graph (`impact.py`), doc-graph (`docgraph.py`), harness/model dispatch routing (including sovereign/local model destinations — it's a routing choice, not a hosted service), GOVERNS linkage *enforcement* (the fail-closed gate itself), Intent Capture, `roadmap check`, Orphan Sweep, non-author verification gate, telemetry/sentinel |
| The user, via their own config/ceremony/credentials | **Opt-in** (free, scales *complexity*) | `decide --record` panel ceremony and GOVERNS ceremony depth generally; Agent Studio (multi-role charter fleet, scale-up from the default Wingman); user's own 3rd-party integration credentials (their own Slack webhook, Jira instance, GitHub App token) |
| synlynk, by operating or brokering it | **Add-on** (priced, because synlynk bears the cost) | Hosted relay, hosted workstation, swarm gateway; a priced 3rd-party integration where synlynk itself negotiates/resells a bulk tier |

**GOVERNS is split by this same test, not treated as one monolithic opt-in.** GOVERNS-the-invariant (every PR must trace to a linked intent/goal record, enforced by a fail-closed gate) is **Core** — if the linkage requirement itself were optional, Intent-Based Engineering would be a suggestion, not a law. GOVERNS-the-ceremony (decision panels, elaborate goal hierarchies) is what scales with the **Opt-in** dial: at Wingman scale, satisfying the Core invariant can be as light as `intent capture` auto-minting a one-line goal record.

**Add-on has three billing shapes, not three separate categories:**
1. **Infra-rental** — pay for synlynk-operated relay/workstation/swarm access, priced by what it costs synlynk to run.
2. **Consumption/task-based routing** — synlynk operates its own model router on bulk-purchased partnership token quota (instead of passthrough to OpenRouter/Bedrock/etc.), billed per-token/per-task rather than per-hour-of-infra.
3. **Outcome-based delivery** ("outsource to synlynk") — the customer hands over intent and synlynk's own fleet delivers the finished result end-to-end on synlynk-owned infra. Flagged as a deferred strategic thread (see "Deferred") — it maps directly onto the 2b model below, except synlynk's fleet is executing it *as a service* rather than the customer's own fleet.

**Editions bundle defaults across this test, they don't redefine it:**
- **Personal** = Core + local Vizor + Wingman (default). Opt-in: Agent Studio. Conceptually fully defined by this spec (not an exhaustive module inventory — see worked examples below).
- **Team** (tentative 2026-12-01) = Personal per-seat + local relay + hosted relay. **Light/stub only** — full boundary work is a separate, later spec.
- **Enterprise** (tentative 2027-01-01) = Team + governance/policy/security/compliance bolt-ons. **Light/stub only.**
- Remote relay, hosted workstation, and swarm gateway are **not edition-gated** — any tier can buy them individually; they're Add-ons by the cost-bearer test, not features reserved for a tier.

**Worked examples / edge cases surfaced while applying the rule, kept because they're genuinely non-obvious:**
- **Vizor is not one bucket.** Local, single-user rendering is Core. A Team-synced Vizor view (via local/hosted relay) crosses into Add-on the moment cross-user sync is involved.
- **The TPM daemon-tick mechanism is Core** (Orphan Sweep and GitHub-comment polling depend on it existing), but **how aggressively it acts is an Opt-in dial**: flag-only/observe-mode is the Core default, auto-apply-within-policy-bounds is the Opt-in escalation — mirroring the existing `require_linked_goal_mode: observe|enforce` pattern already in `.synlynk/policy.json`.

**2a/2b as the roadmap's classification test going forward:** 2a (full-stack builder — one person or Wingman, intent to shipped product, solo) is what Personal *is*. 2b (autonomous product org — PM/Ops delegated to a fleet) is what GOVERNS + Agent Studio become once load-bearing across Team/Enterprise. Every future roadmap phase gets tagged 2a or 2b, turning "is this a Personal feature or a Team/Enterprise feature" into a structural test rather than a judgment call. This reconciles with the Platform Vision spec's five unversioned phases: Phase 0-1 map to Core/Personal maturation, Phase 2-4 to Team's relay/hosted/swarm, Phase 5 (community) to Enterprise.

---

## Remediation (first real test cases for the new gate)

Once `synlynk roadmap check` exists, these two known-bad states are its first targets, not separate one-off fixes:

1. `goal-2458-master-roadmap`, cited as `primary_goal` in both `dec-9b41a7c3` and `dec-4e81b29a`, does not exist in `state.db`. Reconcile by either creating the goal or repointing both decision records to the correct existing goal.
2. `story-ca8afaf8` ("Review + merge PR #2596") shows `status: open, readiness: draft` despite the spec file already existing on disk. Reconcile its status to reflect reality.

---

## Deferred (explicitly out of scope for this spec)

- **Approach C** — fully-derived `roadmap_arcs`/`roadmap_phases` (no separate materialized table to drift). Follow-up ticket, not this spec.
- **Intent-Based Product Development** — the broader, cross-industry brainstorm on what Intent-Based Product Development means today and could mean in the future (2a/2b framing, PM/Ops-as-a-service implications). A separate, large strategic brainstorm; this spec's invariant seed doc and 2a/2b classification are its starting point.
- **The full Synlynk Constitution/Charter** — beyond the v1 seed doc in Section 5. A deeper, standalone brainstorm.
- **Team/Enterprise full boundary and opt-in gating mechanics** — beyond the light/stub definitions here. A separate spec (previously referred to as "Spec #2").
- **Per-edition onboarding journeys** — depends on the Team/Enterprise spec above landing first (previously "Spec #3").
- **Exhaustive module-by-module Core/Opt-in/Add-on inventory** across all ~138 `synlynk/*.py` modules and CLI commands. This spec establishes the conceptual rule and worked examples; the full inventory is a task for the implementation plan.
- **"Outsource to synlynk" outcome-based delivery** — flagged in Section 6 as a real strategic direction (synlynk's fleet executing 2b as a service), but out of scope here given its billing/SLA/liability surface.

---

## Testing / Rollout

- `synlynk roadmap check` ships with unit tests covering each mismatch type (missing arc/phase row, orphaned arc/phase row, dangling `goal_id`) plus a regression test fixed on the two known-bad records in "Remediation" above.
- The Orphan Sweep ships as advisory-only (writes to `sentinel.md`, never blocks) for its first cadence cycle before any consideration of promoting findings to blocking.
- Intent Capture's GitHub-polling surface reuses the existing TPM daemon-tick infrastructure rather than standing up a new poller, to avoid duplicating the exact class of drift this spec exists to prevent.
