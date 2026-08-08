# GOVERNS Lifecycle Enforcement + Workspace Agent Pilot — Design

**Status:** Draft, pending user review
**Author:** Claude (PM/design), for dispatch to Codex/Grok/Agy
**Related:** `docs/superpowers/specs/2026-07-23-governs-lifecycle-engagement-design.md` (shipped advisory instruction text, PR #464), `docs/superpowers/specs/2026-06-21-support-engineer-agent-design.md` (shipped Support Engineer, the pilot's base), `project-docs/decisions/2026-08-07-tonight-s-brainstorm-agenda-has-two-link.md` (`synlynk decide` panel synthesis this spec builds on), `docs/superpowers/specs/2026-08-06-ux-1.0-field-trial-readiness-design.md` (nudge mechanism reused by this spec, Phase 3a)

## Context

`goal-90e73dfd` tracks a real, previously-undetected gap: the GOVERNS lifecycle checkpoint directives (PR #464) are advisory instruction text only — nothing enforces them, and the `goal_contributions` table was found completely empty before this session, meaning no shipped work had ever actually been linked to a GOVERNS goal, including the goal meant to fix this. Separately, the user wants to revive a "Synlynk workspace agents" concept: SFIA-taxonomy-associated, durable per-project assistant roles, as opposed to the current per-task ephemeral dispatch model. A `synlynk decide` panel (claude/agy/codex/grok) converged on unifying these into one build rather than two: ship the mechanical GOVERNS primitives first, then pilot exactly one durable workspace agent that consumes them to nudge the user at task boundaries.

This spec was brainstormed against that panel synthesis. Mid-brainstorm, scope pressure surfaced twice — a request for team/enterprise networked messaging + universal per-action enforcement, and a request for a full Agent Charter Framework (privileges, personality, wallets, autonomous evolution under a safety-law model). Both were deliberately scoped out of this spec as named future goals (see Out of Scope), keeping this spec to what actually ships: the event bus, the three mechanical primitives, and one pilot agent.

**Also decided in this brainstorm:** the hold on the UX 1.0 field-trial-readiness plan (`docs/superpowers/specs/2026-08-06-ux-1.0-field-trial-readiness-design.md`) is fully lifted — that plan proceeds concurrently with this one, no longer gated on this spec.

---

## Section 1: Data Model & Event Bus

Two new tables in `state.db`:

**`events`**
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | |
| `event_type` | TEXT | one of the 4 types below, extensible later |
| `payload_json` | TEXT | shaped `{context_pack, task_scope, input, actions}` — `actions` may reference synlynk commands+flags, harness commands+flags, or workspace events/data/logs; extensible to skills/plugins/CLIs by convention, not schema-enforced |
| `created_at` | TEXT | ISO timestamp |
| `emitted_by` | TEXT | producer identifier (e.g. `story_done_cmd`, `gh_actions_merge_hook`) |
| `parent_event_id` | INTEGER, nullable | links an event to the event that caused it — the "belongs to something above" chain |
| `authority_scope` | TEXT, nullable | reserved for future workspace/user/agent/process addressing; always `NULL` in this build (local-only) |

**`subscriptions`**
| Column | Type | Notes |
|---|---|---|
| `agent_name` | TEXT | |
| `event_type` | TEXT | |
| `last_seen_event_id` | INTEGER | checkpoint; advances as the agent processes events |

**4 event types wired up in this build:** `pr_merged`, `story_done`, `spec_or_plan_committed`, `cron_heartbeat`.

**Producers:**
- `pr_merged` — a GH Actions step on merge writes the event.
- `story_done` — the new `synlynk story <id> done` command (Section 2) writes it.
- `spec_or_plan_committed` — a CI step (or git hook, implementer's call) fires on commits touching `docs/superpowers/specs/` or `docs/superpowers/plans/`.
- `cron_heartbeat` — the existing Support Engineer cron trigger writes one heartbeat event per scheduled run, independent of other activity.

**Consumption model:** any agent run reads events since its `last_seen_event_id` for each `event_type` it's subscribed to (via its `subscriptions` rows), processes them, and advances the checkpoint. This build wires up exactly one real consumer — the pilot workspace agent (Section 3) — but the schema supports any number of future agents subscribing to any event type without changes.

**Explicitly not built in this section:** team/enterprise networked message delivery (the `authority_scope` field is reserved, not implemented), and enforcement that every workspace action produces or requires an event (see Out of Scope).

---

## Section 2: GOVERNS Mechanical Primitives

**(a) `synlynk story <id> done`** — new CLI subcommand. Sets `status='done'` on the given story in `state.db`, writes a `story_done` event with the story's id and its linked goal id(s) in the payload.

**(b) Goal-link hook at plan approval** — when a plan document is committed under `docs/superpowers/plans/` (detected by the same commit hook/CI step that emits `spec_or_plan_committed`), the hook checks whether the plan's associated story has a `goal_contributions` row. If yes, no-op. If no, it writes a `goal_contributions` row with a new `link_status` column set to `'skipped'` and a `skip_reason` column (e.g. `"no active goal specified at plan-approval time"`) — so the gap that let `goal_contributions` sit silently empty for months is now queryable (`SELECT * FROM goal_contributions WHERE link_status='skipped'`) instead of invisible.

**(c) `synlynk pr check` soft-warn** — when checking a PR whose branch corresponds to a spec/plan-derived story with no linked GOVERNS goal (checked via `goal_contributions`, including `'skipped'` rows), print a warning line to the check output. Does not change the command's exit code — this stays advisory, matching the panel's explicit "soft-warn, not hard-block" recommendation, since the false-positive rate on routine chore/maintenance PRs hasn't been measured yet.

---

## Section 3: Pilot Workspace Agent

One new durable role, built as a sibling module to (and composing) `synlynk/support_engineer.py` — exact file structure (extend in place vs. new `synlynk/workspace_agent.py` importing the existing module) is an implementer decision at plan time, not fixed here.

**Trigger model:** cron-scheduled, same mechanism as Support Engineer today (GH Actions + local crontab) — no new process model. "Durable" in this build means: persisted config + persisted `subscriptions` checkpoint state + role identity (per-role GitHub App identity, already approved 2026-07-25) that's consistent across runs, not a long-lived process.

**Subscriptions:** all 4 event types from Section 1.

**Behavior per run:** read events since checkpoint for each subscribed type; cross-reference current goal/story/todo state in `state.db`; when a meaningful boundary is found — a goal now fully closed (all linked stories done), a story marked done with no next story queued under the same goal, or a `pr_merged` event whose story has no linked goal (including `link_status='skipped'` rows) — emit a nudge via the shared nudge pipeline (Section 4).

**Role config** — `.agents/<name>.json`, alongside existing Support Engineer-style config:
```json
{
  "role": "workspace-lifecycle-nudge",
  "sfia_codes": ["PROB", "PEMT", "BURM"],
  "subscriptions": ["pr_merged", "story_done", "spec_or_plan_committed", "cron_heartbeat"],
  "charter_version": null,
  "schedule": "<reuses Support Engineer's existing cron schedule>"
}
```
`sfia_codes` establishes the SFIA-as-role-vocabulary pattern other future workspace-agent roles will follow (per `synlynk/taxonomy_standards.py`'s existing `SFIA_CODES` table) — this build does not touch `capability_sweep.py`'s scoring/calibration logic, it's a static tag on the role config, not a computed score.

`charter_version: null` is a deliberate placeholder marking this role as "not yet charter-ified" — see Out of Scope. Nothing about privileges, personality, wallets, or autonomous evolution is defined or built for this role beyond what it already inherits from Support Engineer's existing execution model (state.db read access, dispatch capability, per-role GitHub App identity).

---

## Section 4: Nudge Delivery

Reuses `docs/superpowers/specs/2026-08-06-ux-1.0-field-trial-readiness-design.md` Phase 3a (terminal tips), built now as a shared dependency rather than staying held:

- The distinctive-fenced-box terminal tip mechanism, extending the post-`exec`/post-`dispatch` output path in `bin/synlynk.py`.
- The `~/.synlynk/config.json` `nudges` block: `{"nudges": {"enabled": true, "dismissed_ids": [...], "last_shown": {...}}}`.
- `synlynk config nudges off/on/reset` CLI commands.

Two producers now feed this one consumer pipeline: the UX-1.0 surface-adoption nudges (from the other spec, now unblocked and proceeding concurrently) and this pilot agent's goal/story-boundary nudges. Both use the same distinctive presentation (fenced box, forced accept/close/follow, no silent timeout-dismiss) and the same opt-out/replay config — one nudge UX for the user, two producers behind it.

Phase 3b (Vizor banner) and 3c (Slack cross-link) proceed on their own schedule as part of the (now unblocked) UX 1.0 field-trial-readiness plan — not gated by this spec.

---

## Out of Scope

Each item below becomes a named GOVERNS goal (via `synlynk goal create`) after this spec is written, carrying forward the context gathered in this and prior sessions so it isn't lost:

- **Real maturity-tier detection** — replacing the hardcoded `_current_trigger_registry_tier()` return value in `synlynk/instructions.py`.
- **Suggestion-acceptance telemetry** — measuring shown-vs-accepted rates on lifecycle checkpoint suggestions, a precondition the original `goal-90e73dfd` spec named but never built.
- **Release Agent + TPM Agent** — the two 2026-06 named-role specs that were never implemented (`release-agent.json`/`release suggest|run|status`; TPM lifecycle engine).
- **Full multi-role fleet + per-project custom roles** — activating workspace agents across rxcc, cc-videoreframing, and playblazer-ng with roles tailored to each project.
- **Hard CI-blocking on unlinked GOVERNS goals** — upgrading Section 2(c)'s soft-warn to a blocking check, once false-positive rate on routine PRs is measured.
- **Universal GOVERNS enforcement** — the requirement that every prompt/action in a synlynk-managed workspace belong to something above it and trigger something below it. This build only wires 4 named event types; it does not instrument "every activity."
- **Team/enterprise networked messaging** — actual delivery of events across a Workspace→User→Agent→Process/Command authority hierarchy. This build reserves the `authority_scope` schema field but implements only local, single-workspace delivery.
- **Full Agent Charter Framework** — composable role/tools/actions/memory/devlog/privileges/identity/secrets, evolving personality/style, agent wallets with transaction capability, and autonomous persona evolution bounded by a safety-law framework (Asimov's Three Laws + the Zeroth Law). This is a foundational initiative affecting every future workspace agent and needs its own dedicated brainstorm — not squeezed into this pilot's config.
