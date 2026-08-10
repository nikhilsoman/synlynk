# Autonomous Ops Program — Design

**Date:** 2026-08-11
**Status:** Design; approved by Nikhil in chat 2026-08-11. Implementation requires a separate approved plan.
**Base document:** `docs/strategy/road-to-autonomous-ops.md` (2026-08-10) — adopted as the operating-loop, weekly-sequence, and release-gate foundation. This spec layers three modifications on top of that document and resolves the roadmap-governance strategy question it names as its first Week-1 task.
**Related:** `docs/strategy/2026-08-10-roadmap-todo-governance.md` (work-envelope/session model, devlog contract, GitHub-issue-as-external-surface model — adopted as the mechanism for Goal 2).

---

## Objective

Two goals, pursued together, for every repo synlynk operates in:

1. **Autonomous Ops** — job status is truthful, GitHub writes are reliable, execution is quota-aware and verified end-to-end, without requiring the user to babysit dispatched work.
2. **Roadmap & Todo alignment** — every meaningful unit of work ends up attributed to a goal, maintenance, or exploration; roadmap and todo stay generated, accurate projections of real state, managed by the workspace agents rather than by manual upkeep.

Target: an **Autonomous Development Loop Preview** live by **2026-10-01**, reached via an **Autonomous Ops Lite** milestone this week (by 2026-08-16) and a 7-week maturation arc after that.

This is execution and continuity autonomy, not strategic-decision autonomy. Human approval remains required for major product decisions, scope changes, security or GitHub policy changes, irreversible merges where required, and named releases.

## Three modifications to the base document

`road-to-autonomous-ops.md` already defines the target operating loop, the current-position assessment, the autopilot-lite recipe, the minimum build for October 1, the weekly sequence, and the release gates. This spec does not restate or re-derive those — it adopts them, with three changes:

### 1. Isolated per-repo workspace-agent identities, full 8-role set

Every repo synlynk operates in gets its own complete, isolated complement of the 8 defined Agent roles (pm, architect, tpm, dev, designer, qa, marketing, synlynk-bot — per `docs/glossary-agent-vs-harness.md` and `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §2), each with its own GitHub App identity. Identities are not shared across repos and not shared across roles.

Status as of this spec:
- **synlynk**: all 8 identities provisioned and tested working. Issue #864 (dead `synlynk.com` manifest `redirect_url` forcing a manual code copy-paste, hit on every role provisioned so far) is fixed via merged PR #900 — the manifest flow now runs a local-loopback HTTP server that auto-captures GitHub's callback code, falling back to manual paste only for headless/remote sessions.
- **cc-videoreframing** (the pilot repo, see below): identities not yet provisioned. This is the first foundational task of Autonomous Ops Lite.

This directly resolves issue **#423** (the shared-single-GitHub-identity problem that made `gh pr review --approve` fail on every dispatch-authored PR, worked around all session via the sanctioned COMMENT-review fallback) as a side effect, once each repo has real per-role identities to review with — no separate fix is required beyond provisioning.

### 2. Charters operate inside existing gates, not instead of them

Workspace agents get full authority to manage their charter's domain end-to-end (a `dev` agent implements, a `qa` agent verifies, a `tpm` agent reconciles roadmap/todo, and so on) — but every standing hard gate in this repo's CLAUDE.md remains in force as a charter-external constraint:

- **Brainstorm-First Policy** — no code before an approved spec exists in `docs/superpowers/specs/`.
- **Design → Plan → Build sequence** — spec not committed = no plan; plan not committed = no dispatch.
- **PR Review Discipline** — non-authoring agent reviews via `synlynk pr check`; the reviewer alone merges.
- **Named Release Policy** — releases stay human-signed-off, themed events, not autonomous.

A charter defines *what a role is authorized to decide and do within its domain*. It never grants authority to skip a gate that exists independent of any single role.

### 3. PM interaction is permanently this Claude Code session — no separate chat interface, at any maturation stage

The user's interaction model, now and through the full 7-week maturation arc and past the October 1 preview, is: chat with Claude (this session) as the PM function, primarily to groom new initiatives from idea to design stage. There is no plan, at any point in this roadmap, to stand up a separate PM-agent chat surface (e.g., built on the Support Engineer durable-agent pattern) as the user's primary interface. The `pm` role's GitHub App identity and any autonomous `pm`-role actions (e.g., commenting on issues, updating roadmap rows) are real and isolated per repo, but they are not a chat surface — they are one of the 8 roles' scoped write capabilities, exercised the same way any other role's are: dispatched or autonomous within its charter and gates, never as a conversational interface replacing this session.

## Pilot repo

**cc-videoreframing.** (The base strategy document names rxcc/vdowrx as multi-project dogfood targets in its Week 5 slice — that naming is superseded for this program; cc-videoreframing is the confirmed pilot and second repo throughout.)

## Goals, mechanism, and scope (adopted from source documents)

**Goal 1 (Autonomous Ops)** uses the target operating loop, current-position assessment, autopilot-lite recipe, and release gates exactly as defined in `road-to-autonomous-ops.md`. No changes.

**Goal 2 (Roadmap & Todo alignment)** uses the work-envelope model, devlog contract, and GitHub-issue-as-external-work-surface model exactly as defined in `docs/strategy/2026-08-10-roadmap-todo-governance.md`. No changes. Key authority boundaries carried forward:
- GitHub owns: issue number, title/body, labels, comments, assignees, open/closed state, PR links.
- Synlynk SQLite owns: goal meaning, roadmap placement, story readiness, session attribution, cost/quota evidence, local disposition, GOVERNS lifecycle state.
- The reconciler owns: detecting divergence, creating link candidates, emitting events. It never silently overwrites either system's semantic state.

## This week — Autonomous Ops Lite (by 2026-08-16)

Matches `road-to-autonomous-ops.md`'s own Week-1 slice ("Contract and dogfood"), with modification 1's provisioning work folded in as the new first item:

1. **Provision cc-videoreframing's 8 role identities**, replicating the now-proven synlynk pattern.
2. **Resolve the roadmap-governance strategy** — done by this spec's adoption of `2026-08-10-roadmap-todo-governance.md`.
3. **Choose one real synlynk goal and run the autopilot-lite loop manually** across synlynk and cc-videoreframing, per the base document's 8-step recipe.
4. **Ship v0.14.0** — the named release already scoped in this session (job-status-truthfulness fixes, GH-write reliability slice, GOVERNS event-contract extension, plus dogfooding the Init/Migrate/Upgrade Rollback mechanism live via `synlynk upgrade`/`repair` in both repos) — this is the concrete Goal-1 proof point for the week.
5. **Measure attribution failures and prompt friction** from the manual loop run, feeding directly into Week 2's TPM/session MVP design.

## Weeks 2–7 — maturation arc (adopted from base document, unmodified)

- **08-17 → 08-30**: TPM/session MVP — activity-envelope schema, `session open/status/close`, devlog-session-goal linking, checkpoint reconciliation, first durable TPM loop and nudges.
- **08-31 → 09-13**: GitHub Issue/PR mirror fields and sync provenance, `external_untriaged` disposition, GOVERNS event extension for issue/PR events, release-scope attribution reporting.
- **09-14 → 09-24**: Multi-project dogfood across synlynk and cc-videoreframing with bounded quotas, low parallelism, real Issue/PR workflows, deliberate scope changes, and failure/handoff cases.
- **09-25 → 10-01**: Public preview hardening — document the operating model and limitations, add a narrow `synlynk autopilot` entry point only if the underlying loop is stable, publish measured results, release only if the gates below pass.

## Release gates (adopted verbatim from `road-to-autonomous-ops.md`)

The October 1 preview requires:
- 100% of terminal jobs have cost data or explicit `cost_missing` status.
- 100% of meaningful work has a disposition within one checkpoint.
- No unreviewed autonomous merge or release.
- No quota bypasses.
- No increase in verified rework from automation.
- Ordinary session closeout takes under one minute.
- GitHub Issues in configured scope are linked, parked, or marked out of scope.
- GitHub sync failures are visible and attributable.
- At least one complete multi-project dogfood cycle succeeds (synlynk + cc-videoreframing).
- Failed or abandoned jobs do not lose their devlog or attribution evidence.

## Scope exclusions (adopted verbatim from `road-to-autonomous-ops.md`)

Do not make the October preview depend on:
- full Agent manifest/configuration infrastructure;
- portable implants or Tokq deployment;
- hosted/team state synchronization;
- universal automatic intent classification;
- all-harness consensus on every decision;
- autonomous strategic goal promotion;
- fully autonomous release publishing.

**Additional exclusion specific to this spec's modifications:** no separate PM-agent chat interface, at any point in this roadmap. This is permanent, not deferred.

## Decision

Adopt `road-to-autonomous-ops.md` as the operating plan, `2026-08-10-roadmap-todo-governance.md` as the Goal-2 mechanism, layer in per-repo isolated 8-role identities (synlynk done, cc-videoreframing this week), keep charters strictly inside existing hard gates, and keep this Claude Code session as the sole permanent PM interface. Cut Autonomous Ops Lite by 2026-08-16 through identity provisioning + v0.14.0 + one manual autopilot-lite loop run; mature through the unmodified 7-week arc to the Autonomous Development Loop Preview on 2026-10-01.
