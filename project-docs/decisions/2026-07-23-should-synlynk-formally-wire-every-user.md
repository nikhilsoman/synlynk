---
decision_id: dec-4ecba2fe
topic: "Should synlynk formally wire every user engagement — explicit CLI commands AND conversational trigger phrases, even without an explicit command — into the GOVERNS lifecycle by default? Concretely: should a brainstorming/design session automatically end by suggesting 'synlynk goal create' and linking the work to GOVERNS tracking? Should this be delivered as a new skills-catalog of directive files referenced via the existing synlynk:start/end fenced-directive mechanism in CLAUDE.md/AGENTS.md (per the approved-but-unimplemented 2026-07-17 command-taxonomy-and-trigger-registry spec)? And critically: should this ship now, or is it too large a change to default project-lifecycle UX to introduce before a later release?"
date: 2026-07-23
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Should synlynk formally wire every user engagement — explicit CLI commands AND conversational trigger phrases, even without an explicit command — into the GOVERNS lifecycle by default? Concretely: should a brainstorming/design session automatically end by suggesting 'synlynk goal create' and linking the work to GOVERNS tracking? Should this be delivered as a new skills-catalog of directive files referenced via the existing synlynk:start/end fenced-directive mechanism in CLAUDE.md/AGENTS.md (per the approved-but-unimplemented 2026-07-17 command-taxonomy-and-trigger-registry spec)? And critically: should this ship now, or is it too large a change to default project-lifecycle UX to introduce before a later release?

## Panel Inputs

### claude
This is a governance/architecture question for a decision panel — no skill fits it directly (no code being written, no feature being brainstormed by me). I'll answer directly.

**Analysis**

The spec exists but is unimplemented — that's a signal, not a blocker. A week sitting approved-but-unbuilt usually means either (a) nobody's picked it up, or (b) it quietly failed a gut check on scope. Worth distinguishing before treating "ship now" as the default.

Two separable questions are being bundled: *should engagements link to GOVERNS* (yes, clearly good — untracked brainstorming is exactly the kind of work that currently falls through the cracks) and *should this be automatic, default-on, for every conversational trigger phrase, without explicit command*. Those have very different risk profiles.

Auto-suggesting `synlynk goal create` at the end of a design session is low-risk — it's a nudge, reversible, ignorable. Wiring *conversational trigger phrases* (not just explicit CLI commands) into a skills-catalog that fires by default is a much bigger surface: false positives on ordinary conversation, a new directive-file catalog to maintain, and a change to default project-lifecycle UX that every existing project inherits silently on upgrade. That's the kind of thing that should go through brainstorming-first policy per CLAUDE.md's own Design → Plan → Build sequence, and given the spec is dated 2026-07-17 with no plan doc yet, that sequence hasn't happened.

The GOVERNS-linking half is small and mechanical enough to ship as an opt-in behind a flag or config toggle first, get real usage signal, then decide on default-on. The trigger-phrase/skills-catalog half is the part that's "too large to default" — it changes behavior for every user's every conversation, not just command paths.

**Recommendation:** Ship the explicit-command half now (CLI commands ending sessions suggest `goal create`), opt-in by default. Do not ship the conversational-trigger / skills-catalog half until a dedicated plan doc exists and it's piloted opt-in on synlynk's own repo for at least one release cycle. Splitting the PR this way avoids retrofitting a v0.Y.0 default-UX change that turns out to annoy users mid-brainstorm.

### codex
Wiring every user engagement into the GOVERNS lifecycle by default is directionally appealing, but I would not make it the default behavior yet. The core idea is strong: it reduces friction, makes lifecycle capture more consistent, and prevents high-value brainstorming work from disappearing into untracked conversational drift. The “suggest `synlynk goal create`” step is especially sensible as a soft affordance, because it preserves user agency while nudging the session into a durable workflow.

The risk is scope and surprise. Automatically treating explicit CLI commands and informal trigger phrases as lifecycle entry/exit events changes the product’s default UX, not just its internals. That means every ambiguous “let’s brainstorm” or “design this flow” interaction becomes semantically loaded, and that can create false positives, accidental tracking, and user confusion about when a session is “officially” governed. The proposed skills-catalog of directive files via `synlynk:start/end` is also a meaningful architecture shift: it is good for extensibility and policy clarity, but it adds a new layer of indirection at the exact point where the product should still be proving the interaction model.

My recommendation is to stage this. Ship the registry and directive-file mechanism behind an explicit opt-in or limited beta first, then validate whether default suggestions improve capture without harming flow. Keep conversational trigger phrases as advisory hints, not hard lifecycle transitions, until there is evidence they are reliable across real sessions. The current release should focus on making explicit commands dependable and easy to discover.

My position: do not ship this as a default, always-on UX change now. Implement the underlying registry and `synlynk:start/end` plumbing, but release it behind opt-in semantics first and defer default automatic lifecycle wiring to a later release after validation.

### grok
I'll pull the relevant GOVERNS and command-taxonomy specs so the panel position is grounded in what's already approved vs. shipped.## Panel analysis: GOVERNS as default engagement wiring

**What already exists.** v0.13.0 shipped the hard part of the 2026-07-17 taxonomy: `COMMAND_TAXONOMY` tags every leaf with `governs_stage`, maturity tier, and `trigger_phrases`, and injects a tier-scoped phrase→command map via `synlynk:start`/`synlynk:end`. Conversational routing into GOVERNS stages is already product policy—not a greenfield bet. The open question is whether *every* session, including pure design/brainstorm work, should close by creating or linking a Goal.

**The good case for “wire everything.”** synlynk’s stated posture is to disappear into agent homes, not invent a second UI. If agents only act on explicit CLI verbs, GOVERNS stays a dashboard for power users. Phrase-driven reach-for-command is the right ambient surface. Design sessions that produce durable intent *should* often land as `goal create` / `goal link`, so roadmap, cost, and viz stay honest.

**Where full defaulting breaks.** Earlier SDLC consensus was explicit: not everything is a Goal. Live issues, maintenance, probes, and exploratory brainstorms often need nullable `goal_id` / sustain lanes—not a forced business goal. Auto-suggesting `goal create` after every design session will (1) pollute Tier‑1 with pseudo-goals, (2) train agents to nag, and (3) fight maturity-tier reveal before the tier detector is real (today instructions still default to Tier 2). That is a default-project-lifecycle UX change, not a thin skills catalog.

**Delivery vehicle.** Yes to a **skills/directive catalog** under the existing fence—phrase maps, stage exit criteria, optional “if durable outcome, offer goal create.” No to a new parallel control plane or mandatory end-of-session goal mutation. Keep directives tier-scoped, suggest-not-coerce, and measurable (telemetry: suggestions shown vs accepted).

**Position.** Wire **commands and conversational triggers** into GOVERNS routing by default via the taxonomy + fenced trigger registry (continue/finish that track). Do **not** ship “every engagement ends in `goal create`” as default UX now. Prefer an **opt-in / soft-close skill**: after design/brainstorm, agents *may* propose `synlynk goal create` (or link) when outcomes look durable; never invent goals for sustain/maintenance/one-shot Q&A. Deliver as fenced directive modules, not a lifecycle rewrite. **Ship the thin skills-catalog + suggest path after a focused design; defer hard default GOVERNS capture to a later release once tier detection and goal hygiene are proven.**

## Synthesis
This is a synthesis task, not implementation work — no skill applies (no code being written, no brainstorm to run, just consolidating three panel positions into one call).

All three panelists converge on the same shape despite different framing: the underlying plumbing (COMMAND_TAXONOMY, `governs_stage` tagging, trigger-phrase routing via `synlynk:start`/`synlynk:end`) is already shipped in v0.13.0 and doesn't need re-litigating. The actual decision point is narrower than the question implies — it's specifically about the *last step*: should ending a design/brainstorm session auto-suggest `synlynk goal create` by default. All three say no to hard-default, all three say yes to building it as an opt-in/soft-suggest skill, and all three flag the same failure mode (Tier-1 pollution with pseudo-goals for sustain/maintenance/one-shot work that was never meant to become a Goal). Grok adds the sharpest technical reason: tier detection isn't real yet (defaults to Tier 2), so a hard default would fire before the system can even tell which sessions warrant it.

Decision: Ship the skills-catalog of directive files (phrase→command maps, stage exit criteria) via the existing `synlynk:start`/`synlynk:end` fenced mechanism now, since that's mechanical and low-risk — but the "session ends → suggest `synlynk goal create`" behavior ships as an **opt-in soft-suggest**, not a default, and only for explicit CLI-command session ends, not free-form conversational trigger phrases. Defer default-on automatic GOVERNS linking for conversational triggers to a later release, gated on: (1) a dedicated plan doc per the Design → Plan → Build sequence, (2) real tier-detection working (not the current Tier-2 fallback), and (3) at least one release cycle of opt-in telemetry (suggestion shown vs. accepted) proving the suggestion rate doesn't degenerate into Tier-1 goal-spam. This splits the PR cleanly: the registry/plumbing half ships now, the default-UX half waits for evidence.

## Decision
Decision: Ship the skills-catalog of directive files (phrase→command maps, stage exit criteria) via the existing `synlynk:start`/`synlynk:end` fenced mechanism now, since that's mechanical and low-risk — but the "session ends → suggest `synlynk goal create`" behavior ships as an **opt-in soft-suggest**, not a default, and only for explicit CLI-command session ends, not free-form conversational trigger phrases. Defer default-on automatic GOVERNS linking for conversational triggers to a later release, gated on: (1) a dedicated plan doc per the Design → Plan → Build sequence, (2) real tier-detection working (not the current Tier-2 fallback), and (3) at least one release cycle of opt-in telemetry (suggestion shown vs. accepted) proving the suggestion rate doesn't degenerate into Tier-1 goal-spam. This splits the PR cleanly: the registry/plumbing half ships now, the default-UX half waits for evidence.

> Signatures: see 2026-07-23-should-synlynk-formally-wire-every-user.json
