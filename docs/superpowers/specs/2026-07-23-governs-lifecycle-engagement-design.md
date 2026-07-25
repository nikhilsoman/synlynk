# GOVERNS Lifecycle Checkpoint Directives — Design

## Context

The founder observed that a session like the one that produced the 2026-07-23 per-role-GitHub-identity spec — a full brainstorm ending in an approved, committed design doc — never once touched the GOVERNS lifecycle: no `synlynk goal create`, no `goal link`, nothing tying that work back to project-level tracking. The concern: as more "major new feature" brainstorms happen this way, synlynk's own project-lifecycle model (GOVERNS: goal → open → visualize → execute → release → notify → sustain) silently goes unused, because nothing in the engagement surface — commands or conversation — ever prompts a user toward it.

This is **not** a request to build a new trigger mechanism. `synlynk/taxonomy.py`'s `COMMAND_TAXONOMY` (with `governs_stage`, `trigger_phrases`, `hook_event` per command) and its tier-scoped injection into `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.cursorrules` via the `synlynk:start`/`synlynk:end` fence already shipped in **v0.13.0** (2026-07-22, PR #320, `synlynk/instructions.py:37` `render_trigger_phrase_section()`). Multi-agent panel input (`synlynk decide`, panel `claude,agy,codex,grok`, recorded at `project-docs/decisions/2026-07-23-should-synlynk-formally-wire-every-user.md`; Agy's headless call returned no output and is excluded from synthesis) confirmed this and converged unprompted on the same scope: the real gap is narrower than "wire every engagement into GOVERNS" — it's specifically that **nothing currently prompts a goal linkage at the moment a design/planning session concludes.**

This spec adds that one missing behavior, reusing 100% of the existing v0.13.0 plumbing.

## What This Builds

### No new skills catalog

The question of whether this needs "a new skills-catalog of directive files referenced via fenced directives" is answered no. The existing fence mechanism already generates and injects structured content into every supported instruction file; this spec adds one new subsection to that same generated content, alongside the existing `## Trigger registry` section. No second directive-file system, no new file format, no new injection point.

### New section: lifecycle checkpoint directives

A new function, `render_lifecycle_checkpoint_section()`, added next to `render_trigger_phrase_section()` in `synlynk/instructions.py`, produces a fixed block of directive text (not derived from `COMMAND_TAXONOMY` — this isn't a per-command registry, it's a small, hand-written set of checkpoint rules):

```
## Lifecycle checkpoint directives

- When a brainstorming session (per the brainstorming skill) concludes with
  an approved, written spec, and no active GOVERNS goal is linked to the
  work: suggest `synlynk goal create --outcome <spec's one-line thesis>
  --criterion <spec's stated success condition>` before transitioning to
  implementation planning. This is a suggestion, not a gate — proceed if
  the user declines or the work is explicitly one-shot/maintenance.
- When an implementation plan (per the writing-plans skill) is approved
  and about to enter execution, and the plan's spec has no linked goal:
  same suggestion, offered once.
- Do not suggest goal creation at any other point in a session (not on
  ordinary command usage, not on phrase matches, not mid-brainstorm).
```

This block is appended into the same fenced region `render_trigger_phrase_section()` already writes into (`synlynk/instructions.py:409`), directly beneath `## Trigger registry`, so both ship as one coherent generated block and stay in sync automatically with every existing `instructions update`/drift-check call path.

### Trigger is skill-completion, not phrase-matching

This directive is deliberately narrower than the existing trigger-phrase mechanism. `COMMAND_TAXONOMY`'s `trigger_phrases` fire on conversational pattern-matching against arbitrary human text ("let's build X" → `dispatch`). The checkpoint directive above fires only at two specific, structurally-defined moments — brainstorming-skill completion and writing-plans-skill completion — which an agent following those skills already recognizes as discrete steps (both skills have an explicit "present design, get approval" / "plan complete and saved" moment in their own process). No new detection logic is needed on synlynk's side: the directive is instructional text read by the agent, triggered by the agent's own skill-flow state, the same way the agent already knows when a spec has been "approved" per those skills' existing gates.

### Rollout: mechanical half now, default-UX half later

Two halves, deliberately split (this was the converged panel recommendation, and matches the "narrow" trigger-scope decision already made for this spec):

**Ships now** — mechanical, low-risk, entirely reuses shipped v0.13.0 code paths:
- Add `render_lifecycle_checkpoint_section()` and wire it into the existing fence-generation call site.
- Update `tests/test_taxonomy.py`/`tests/test_selftest.py`-style coverage to assert the new section renders and appears in generated `CLAUDE.md`/`AGENTS.md` content, matching the existing test pattern for `render_trigger_phrase_section`.
- This is an **opt-in soft-suggest**: the directive tells the agent to *suggest* `goal create`, never to require or auto-execute it. No CLI behavior changes, no new gating logic, no schema changes.

**Explicitly deferred, not built in this spec:**
- **Promoting this to a hard default across all conversational engagement** (i.e., beyond the two skill-completion checkpoints above) is out of scope until two preconditions are met:
  1. **Real maturity-tier detection.** `synlynk/instructions.py:28-34`'s `_current_trigger_registry_tier()` currently hardcodes `return 2` with an explicit code comment: "No live maturity-tier signal exists in committed code outside taxonomy, so this defaults to Tier 2 until that signal is available." A hard default that fires based on session content, independent of a real tier signal, cannot yet distinguish a Tier-0 exploratory repo from a Tier-2 team project — exactly the failure mode Grok's panel input flagged (goal-spam on sustain/maintenance work never meant to become a tracked Goal).
  2. **One release cycle of opt-in telemetry** on the soft-suggest shipped in this spec (suggestion-shown vs. suggestion-accepted rate) — evidence needed before deciding whether broader defaulting is even desirable, let alone how broad.
- Both preconditions are named here as explicit gates, not vague "future work" — the next spec that proposes broadening this behavior should cite evidence against these two gates specifically.

## Non-Goals

- No change to `COMMAND_TAXONOMY`, `entries_up_to_tier()`, `entries_for_tier()`, or any existing trigger-phrase routing — this spec adds a sibling section, not a modification to that registry.
- No new CLI command or flag. `synlynk goal create`/`goal link` already exist and are unchanged; this spec only adds a directive that tells agents to suggest calling them.
- No enforcement/gating — a user or agent can always skip the suggestion. This is advisory text, not a workflow requirement.
- No change to `_current_trigger_registry_tier()`'s Tier-2 fallback — fixing that is a named precondition for future work, not built here.
- No GOVERNS-stage domain-adaptivity (making the 7-stage lifecycle itself pluggable per industry/domain) — that remains separate, larger, deferred team/enterprise work (tracked in `[[project-capability-taxonomy-enterprise-seed]]`), unrelated to this spec's narrow scope.

## Data Flow

```
brainstorming skill reaches "User approves design?" = yes
  → spec written + committed
  → (this spec's addition) agent reads injected "## Lifecycle checkpoint
    directives" section from its own CLAUDE.md/AGENTS.md
  → agent checks: does this spec have a linked GOVERNS goal? (via
    `synlynk goal list` / existing goal-link state)
  → no linked goal → agent suggests `synlynk goal create --outcome ...
    --criterion ...` to the user, once, non-blocking
  → user accepts → `goal create` + `goal link <story-or-spec-id>` (existing commands)
  → user declines/ignores → brainstorming skill proceeds to writing-plans as normal

writing-plans skill reaches "Plan complete and saved" moment
  → same check/suggest pattern, scoped to the plan's parent spec
```

## Testing

- Extend `tests/test_taxonomy.py` (or add a sibling `tests/test_instructions.py` case if the render function lives outside taxonomy scope) to assert `render_lifecycle_checkpoint_section()` returns the fixed directive block verbatim, and that it appears in generated `CLAUDE.md` content after a `synlynk instructions update` run — mirroring the existing assertion pattern already used for `render_trigger_phrase_section`.
- No behavioral/integration test is needed for "does the agent actually suggest goal creation" — that's advisory prompt content interpreted by the agent at runtime, not code-testable synlynk behavior. This matches how the existing trigger-phrase section itself is tested (content-presence, not agent-behavior).

## Future Work

- **Default-on GOVERNS induction across all conversational engagement** (not just skill-completion checkpoints) — gated on real tier-detection replacing the `_current_trigger_registry_tier()` Tier-2 fallback, and on telemetry evidence from this spec's opt-in rollout. Should be its own spec when those gates are met.
- **GOVERNS-stage domain-adaptivity** — tracked separately, unrelated to this spec (see Non-Goals).
- **Extending checkpoint directives to other skill-completion points** — e.g. `subagent-driven-development`/`executing-plans` finishing all tasks (release-stage), or `finishing-a-development-branch` completing (notify/sustain-stage) — named here as a natural next increment but not built in this spec, which is scoped to the two checkpoints (brainstorm → spec, plan → execution) directly motivating this work.
