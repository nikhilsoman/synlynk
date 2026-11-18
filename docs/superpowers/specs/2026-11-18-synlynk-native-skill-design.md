# synlynk-Native Skill — Design

## Status

Design approved via brainstorm, 2026-11-18. Separate spec from, and sequenced **after**,
`docs/superpowers/specs/2026-11-18-harness-routing-manifest-mechanics-design.md` (PR #5369) — does not block
and is not blocked by that work. Closes the "fold in vs. defer" question on issue #5367 (folded in, as the
structural centerpiece of this spec, not patched separately).

## Problem Statement

Two related problems, both load-bearing enough to fix together:

1. **Instruction-file duplication (issue #5367).** synlynk's own SOPs/ceremonies are hand-written into
   `CLAUDE.md` and then separately, manually, hand-duplicated into `AGENTS.md`, `GEMINI.md`, `.cursorrules`.
   There is no mechanical guarantee a rule added to one reaches the others. A recent example: the
   "plan committed → generate GOVERNS-linked stories autonomously" rule (this same harness-parity thread)
   had to be hand-copied across files with no enforcement that it actually was.

2. **External dependency on `superpowers` for the ceremony/process layer.** synlynk currently relies
   entirely on the third-party `superpowers` marketplace plugin (brainstorming, writing-plans, TDD,
   debugging, worktrees, subagent-dispatch, code review) for *how work gets done*, while synlynk's own
   `CLAUDE.md`/`AI_INSTRUCTIONS.md` only govern *synlynk-specific policy* layered on top. synlynk is
   heading toward Intent-Based Product Development with its own evolving constitution and invariant set
   (Agent Studio charters, GOVERNS, empirical capability routing) that is not guaranteed to stay aligned
   with superpowers' own evolution, since the two are maintained independently with no coordination.

## Why now, and why absorb rather than depend

**Measured split (this brainstorm, by line count of content actually loaded in a synlynk session):**

| Source | Lines | Share | What it is |
|---|---|---|---|
| superpowers (14 skills) | 3,207 | ~82% | Generic, domain-agnostic SWE craft methodology (TDD mechanics, debugging method, plan format, worktree hygiene) |
| synlynk-unique (`CLAUDE.md` + `AI_INSTRUCTIONS.md`, de-duplicated) | ~697 | ~18% | Fast-evolving, non-negotiable governance (GOVERNS linkage, cross-harness+model review, cost-capture provenance, capability-based routing) |

The 82% superpowers provides is low-churn commodity craft (MIT-licensed, safe to fork) that rarely changes.
The 18% synlynk provides is small but is the part that actually constitutes synlynk's "constitution" and is
under active revision in this very PR thread. Absorbing the 82% costs little to maintain going forward;
continuing to depend on it externally risks the 82% and the 18% drifting apart with no mechanism to catch it.

**Prior evaluations checked (none directly answers this question, surfaced for the record):**
- `docs/superpowers/specs/2026-06-27-bs7-skill-pack-interoperability-design.md` (BS-7) — proposed synlynk and
  skill packs coexist at separate layers via a `git-drift` fencing tool. Never built; answers a *coexistence*
  question, not an *absorption* question.
- `project-docs/decisions/2026-11-09-decide-panel-agent-role-management-agent.md` (`dec-0d41e039`) — decided
  synlynk's *tool/control-plane* distribution surface should be a thin MCP server, not a skill pack. Answers
  the control-plane distribution question, not the instruction-loading question this spec addresses.
- `docs/strategy/deepseek-harness-and-over-the-horizon-expansion.md` — a parked, unexplored one-line mention
  of an Antigravity-IDE-only native skill pack. Too narrow to have evaluated this question.

## What makes `superpowers` universal and consistent across harnesses

Inspected directly (`~/.claude/plugins/cache/superpowers-marketplace/superpowers/5.1.0/`). Not "hooks per
verb" — five concrete, reusable mechanisms:

1. One canonical `skills/` markdown tree — content authored once.
2. Thin per-harness manifest adapters sitting side by side (`.claude-plugin/plugin.json`,
   `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `gemini-extension.json`) — each just points
   that harness's native loader at the same shared content; none duplicates it.
3. One `SessionStart` hook (`hooks/hooks.json`, firing on `startup|clear|compact`) that forcibly injects a
   single meta-skill (`using-superpowers`) establishing the hard rule "if a skill might apply, you must
   invoke it" — this is the actual adherence mechanism, not per-verb hooks.
4. A tool-name translation layer (`skills/using-superpowers/references/{codex,copilot,gemini}-tools.md`) so
   skill prose written against Claude Code's tool names still resolves on a harness with different tool
   names.
5. Root `CLAUDE.md`/`GEMINI.md` are thin pointers into the one shared tree, not separate copies.

This spec replicates mechanisms 1–5 for synlynk's own content.

## Decision: absorb, don't depend (and don't half-measure)

Considered and rejected during brainstorm: (a) complementary-only (synlynk skill covers only synlynk SOPs,
keep depending on superpowers for ceremonies) — rejected because it leaves synlynk's adherence story split
across two independently-evolving sources, the exact risk this spec exists to close; (b) thin wrappers that
delegate to superpowers' skills for anything overlapping — rejected because it only works when superpowers
happens to be installed, which is not guaranteed on every harness/marketplace.

**Decision: fork and adapt.** synlynk's own skill tree bundles its own versions of the ceremonies it
currently gets from superpowers, with synlynk's SOPs woven directly into the relevant step of each ceremony
rather than cross-referenced from a separate file. superpowers becomes optional/redundant once this ships.
superpowers is MIT-licensed; fork is legally clean. synlynk credits it as reference origin in the new tree's
top-level README.

## Architecture

One canonical tree, mirroring superpowers' proven shape:

```
skills/synlynk/
  using-synlynk/SKILL.md                    # meta-skill, forced-injection via SessionStart hook
  # --- forked ceremonies (superpowers-derived, synlynk SOPs baked in) ---
  brainstorming/SKILL.md
  writing-plans/SKILL.md                    # + GOVERNS-linkage step baked in
  writing-skills/SKILL.md
  test-driven-development/SKILL.md
  systematic-debugging/SKILL.md
  using-git-worktrees/SKILL.md              # + synlynk worktree-naming convention baked in
  subagent-driven-development/SKILL.md
  dispatching-parallel-agents/SKILL.md      # + capability-based harness routing baked in
  finishing-a-development-branch/SKILL.md   # + worktree hygiene sweep baked in
  requesting-code-review/SKILL.md           # + cross-harness+model review rule baked in
  receiving-code-review/SKILL.md
  verification-before-completion/SKILL.md
  executing-plans/SKILL.md
  # --- synlynk-unique skills (new, this spec) ---
  using-agent-studio/SKILL.md
  using-github/SKILL.md
  managing-work-items/SKILL.md
  using-memory-and-devlogs/SKILL.md
.claude-plugin/plugin.json
.codex-plugin/plugin.json
.cursor-plugin/plugin.json
gemini-extension.json
hooks/hooks.json                            # SessionStart → inject using-synlynk
```

### The four synlynk-unique skills

Clustered by recurring task shape, not by subsystem noun — mirrors how superpowers itself clusters by task
rather than by concept. Each covers a load-bearing cross-cutting concern explicitly (see rationale below),
rather than spawning further skills per concern:

- **using-agent-studio** — roles/charters, Capability-Based Task Allocation table and its per-cell
  floor-of-5 exception, empirical capability-based routing, **and 100% GOVERNS adherence as a
  dispatch-preflight gate** (GOVERNS is not a separate skill — it is a gate this skill enforces at
  dispatch time).
- **using-github** — gh role-shim pattern, non-author review requirement, cross-harness+model review gate,
  merge-authority check (`synlynk policy check-merge`), `--requires-gh-write` routing, the
  personal-token-off-limits rule.
- **managing-work-items** — roadmap.md/todo.md as state.db-rendered (not hand-edited) views, the Roadmap
  Drift Gate (decisions/goals/roadmap_arcs consistency — **goals are a node type this skill covers, not a
  separate skill**), the "plan committed → generate GOVERNS-linked stories autonomously" rule.
- **using-memory-and-devlogs** — anti-amnesia mid-session checkpointing, devlog format, project-docs memory
  conventions. About session hygiene, not a product subsystem — a distinct cluster from the three above.

**Explicitly not added as separate skills** (folded into the above instead, to avoid recreating #5367's
fragmentation at skill-granularity): `using-GOVERNS` (folded into `using-agent-studio` + `managing-work-items`),
`using-goals` (folded into `managing-work-items`), `using-agents` (synlynk's harness-routing additions are
baked into the forked `dispatching-parallel-agents`, not a new skill).

**Deferred, not in this tree:** `using-vizor` — narrower, lower-frequency trigger (only fires per the existing
conditional Workspace Map Update Protocol, when a PR changes a cross-repo relationship). Safe to add later
without disturbing this mechanism; not essential to Stage 0.

## Content scope — Stage 0 (this spec's deliverable)

- Fork and adapt the 13 ceremony skills listed above, plus author the 4 synlynk-unique skills and the
  `using-synlynk` meta-skill.
- `using-synlynk` + the per-harness manifest adapters + `hooks/hooks.json` replace the current
  `CLAUDE.md` "Harness Instructions" section and `AI_INSTRUCTIONS.md` as the single source of truth.
  `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`.cursorrules` become thin generated pointers into this tree —
  this is the structural fix for issue #5367 (closes it, not a templating patch on top of it).
- All control-plane operations referenced by any skill (`synlynk dispatch`, `synlynk pr check`,
  `synlynk cost log`, `synlynk policy check-merge`, `synlynk story done`, `synlynk checkpoint`, etc.) are
  invoked via Bash shell-outs to the already-installed `synlynk` CLI, exactly as today. **Zero new
  packaging, zero new runtime infrastructure in this spec.**
- `using-synlynk`'s own content is kept deliberately thin — a map of what skills exist and when to reach
  for them — not a copy of today's full CLAUDE.md. The deep procedural content lives in the individual
  skills, loaded on demand, which is the actual point of this migration (today's CLAUDE.md is always-loaded
  regardless of relevance; a skill tree is not).

## Deferred stages (referenced, not designed here)

- **Stage 1 — skill + registered MCP server.** Once the already-decided (`dec-0d41e039`) thin synlynk MCP
  server (dispatch/pr-check/GOVERNS/cost/charter as typed tools) exists, the same plugin manifests register
  it, upgrading shell-outs to typed tool calls where it matters. Additive; does not require redoing Stage 0.
- **Stage 2 — full control-plane bundling.** Plugin install also bootstraps the python daemon/state.db/
  worktree hooks, so "install one plugin" suffices on a fresh machine with no separate `pipx install
  synlynk` step. Most packaging-heavy stage; explicitly not critical right now per the project owner.
- **Domain/industry skill packs** (legal, fintech, healthcare, etc., selected dynamically by Agent Studio
  charter binding). Same file format as the universal tree so authoring stays consistent, but distributed as
  separate optional registry entries via the Capability Registry (not bundled by default), once that
  registry is further along. Not designed in this spec.
- **Issue #5353** (cross-harness instruction-adherence verification, "Spec B" of the harness-parity thread) —
  out of scope here. This new mechanism is the natural thing to verify once it exists, but that verification
  design is separate future work.

## Out of scope (explicit)

- Any change to the harness-routing-manifest-mechanics work in PR #5369 — fully independent.
- Building the dynamic domain-pack discovery/charter-binding loader (considered as "Approach 2" during
  brainstorm, rejected for Stage 0 as the highest-risk, most build-before-value option).
- Retiring or modifying the `superpowers` plugin itself — this spec forks content, it does not touch the
  installed superpowers plugin or ask users to uninstall it.

## Tech debt / follow-up tickets

- File a ticket for domain/industry skill pack design, once Agent Studio's Capability Registry is further
  along (referenced, not filed as part of this spec — no immediate action needed).
