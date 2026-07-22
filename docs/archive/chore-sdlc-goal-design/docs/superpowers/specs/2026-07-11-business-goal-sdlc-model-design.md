# Business Goal Layer + GOVERNS SDLC Model
## Design Spec

**Date:** 2026-07-11
**Session:** Business Goal / SDLC naming (Nikhil + Claude, panel-validated)
**Status:** Approved — ready for implementation plan
**Epic:** BS-8 (goal hierarchy) + docs/rollout work
**Target:** v0.12.0

---

## Problem Statement

Synlynk's roadmap model (`roadmap_arcs` / `roadmap_phases` / stories, tagged with a 6-stage cycle: Dream→Plan→Work→Ship→Maintain→Engage) organizes work by version arc, with no layer connecting cross-arc work to a business outcome. This was surfaced concretely by a gap analysis on rxcc's roadmap: purely feature/version-organized, no way to see whether a cluster of tickets across specs is actually moving a business result.

Separately, the cycle-stage vocabulary itself had drifted: `LAUNCH_TASK_TEMPLATES` uses `"cycle": "design"`, `"build"`, `"sustain"` — none of which are in the canonical `CYCLES` list (`synlynk/hud.py:13`) — and one prompt template's own text lists a third vocabulary (`dream/design/plan/build/ship/sustain`). "Dream" as a stage name was also a weak fit for what the stage actually does (audit/discovery of an existing arc, not aspiration).

This spec resolves both: a new **Business Goal** layer above the existing Dream/arc model, and a renamed, redefined 7-stage cycle — **GOVERNS** — replacing the drifted 6-stage vocabulary.

Both were arrived at through three rounds of `synlynk decide` panel review (Claude, Agy, Grok, Codex), not unilateral design. Decision records: `project-docs/decisions/2026-07-08-design-synlynk-s-sdlc-planning-model-con.md`, `2026-07-11-pick-the-best-7-letter-verb-acronym-for.md`, `2026-07-11-second-round-a-new-sdlc-proposal-just-ca.md`, `2026-07-11-third-round-amending-our-locked-decision.md`.

---

## Part 1 — Business Goal Layer

### Shape

A **Business Goal** is a narrative unit: outcome + success criterion + deadline (or "ongoing"). Not OKR-style Objective+KeyResults — an agent fleet optimizing a Key Result number will hit the metric and miss the outcome, faster than a human would and with less chance of anyone noticing. Objective/KR can exist later as a derived *reporting view* over Goals, but it is never the stored primitive.

```
goals table: id, outcome, criterion, deadline, status
```

### Position in the hierarchy

Goal sits **above** Dream, which is unchanged — Dream remains the version-arc container it already is. A Goal owns one or more Dreams plus the epics/stories that serve it.

```
Goal ──┬── Dream (v0.12.0 arc) ── Epic ── Story
       └── Dream (v0.13.0 arc) ── Epic ── Story
```

Nesting is a **strict tree by default** (Goal → Dream → Epic → Story) — one primary parent per story, so context injection and dispatch routing stay deterministic. An optional `goal_contributions` junction table allows a story to reference a *secondary* Goal for genuinely cross-cutting work (e.g., a security epic that serves both a compliance Goal and a platform-stability Goal), without making the tree many-to-many by default.

### Review cadence

Continuous and signal-driven — Goal health is evaluated at Ship events, sentinel triggers, and PR merges, not on a calendar. A lightweight standing `synlynk goals status` rollup gives a weekly human sanity-check pulse. No quarterly OKR ritual anywhere in the loop.

### Dispatch ordering

Now/Next/Later under a Goal is ordered by a **three-factor score**, cheap enough for an agent to self-apply at dispatch time with no estimation ritual:

1. Dependency-unblocked-now
2. Deadline/urgency risk
3. Goal-criticality (does this move the active success criterion)

This explicitly rejects RICE and WSJF as too estimation-heavy for hours/days agent throughput — the fleet can't honestly produce an hours-estimate input today.

### Live Issues / pure maintenance

Orthogonal, not absent. Carries `goal_id = NULL` with a `lane: maintenance` tag, surfaced in its own queue/lane by `synlynk status` and the viz layer — visible always, but never ranked against Goal-serving work in the same list.

### Data model

First-class in `state.db`, implemented by shipping the parked **BS-8** scope:
- `goals` table (id, outcome, criterion, deadline, status)
- Nullable `goal_id` FK on `roadmap_arcs` and stories
- `goal_contributions` junction table for secondary links
- `synlynk goal` CLI: `create` / `list` / `link` / `status`
- Three-layer context injection (Goal → Dream/Arc → Story) feeding `generate_context()`

No KR-tracking fields — that reopens the OKR trap through the schema.

---

## Part 2 — GOVERNS Stage Model

### Why the rename

The prior `CYCLES` vocabulary (`dream/plan/work/ship/maintain/engage`) had already drifted in the codebase (see Problem Statement) and "Dream" didn't fit what the stage actually does. Three panel rounds evaluated alternatives (GESTATE, GARNERS, GRAPPLE, GARDEN, and a competing externally-proposed Goal→Scope→Scan→Dispatch→Ship→Sustain→Grow structure) against four criteria: memorability, literal grounding in real CLI verbs (so the mnemonic requires no extra memorization), narrative coherence, and fit for a fast agent-fleet-native SDLC rather than a human-paced one.

**GOVERNS** won unanimously, twice, on literal command grounding: 5 of 7 letters map directly to real `synlynk` commands users already type. The competing external proposal scored only 2/7 (`scan`, `dispatch`) and didn't spell a pronounceable word — rejected in round 2 for trading away the property that actually drives adoption.

### The seven stages

| Letter | Stage | Command | Scope |
|---|---|---|---|
| **G** | **Goal** | `synlynk goal` (new, BS-8) | Product intent, outcome, success criterion, deadline. 100% human. |
| **O** | **Open** | `synlynk open` | Kick off a work session/branch scoped to a story. Human sets guardrails, agent drafts approach. |
| **V** | **Visualize** | `synlynk viz` | Map architecture/structure before building. Agent proposes structure, human refines. |
| **E** | **Execute** | `synlynk exec` / `synlynk dispatch` | The build itself. ~90% agent-swarm via dispatch, human tech-lead greenlights. |
| **R** | **Release** | `synlynk release` | Cut the release: automated gates + human sign-off. Writes the blog stub to `docs/blog/`. |
| **N** | **Notify** | (documentation convention, no single command) | **Market-facing.** Release notes, blog posts, changelog broadcast, outbound comms for *this release*. Adoption/retention signal feeds back into the Goal layer — Notify owns this release's market surface, not ongoing GTM strategy or multi-release campaigns (those live in the outer Goal loop). |
| **S** | **Sustain** | `synlynk repair` / `synlynk doctor` / `synlynk status` | **Full operational continuity**, in two named sub-modes: **Sustain/Maintain** (patching, dep bumps, routine upkeep) and **Sustain/Alert** (sentinel, repair, doctor, operator paging). Agent-first, human-bounded oversight. |

### Resolving the growth-coverage gap (round 3)

The original 6-stage cycle's "Engage" stage covered both code-review-as-checkpoint *and* adoption/growth outreach. When compressed into GOVERNS, "Notify" was initially defined narrowly as operator-facing sentinel alerts only, and "Sustain" as pure ops maintenance — dropping the growth/outbound half of Engage entirely, with no stage covering blog posts, outbound marketing, or changelog broadcast.

Round 3 fixed this by **flipping which audience Notify serves** (market, not operator) rather than adding an 8th stage or a new word. Rationale, confirmed unanimously by the panel:

- "Notify" reads more naturally as "notify your users of a release" than "notify the operator" — the redefinition doesn't strain the word.
- Outbound comms realistically starts at Release and continues concurrently through the Sustain tail; it has no clean start/end boundary distinct from that, so forcing it into a discrete 8th stage would misrepresent its actual tailing, concurrent nature.
- Operator alerting fits naturally under Sustain — "keeping it running" already includes noticing when it breaks. Splitting "detect" (Notify) from "fix" (Sustain) was the awkward split, not the redefined one.
- Naming Sustain's two sub-modes explicitly (Maintain vs. Alert) pre-empts Sustain becoming an undifferentiated junk drawer — the same category-error risk that caused this gap in the first place.

### Workforce-mix annotation

Adopted from the competing external proposal as a documentation layer *alongside* GOVERNS, not baked into the acronym:

| Stage | Mix |
|---|---|
| Goal | 100% human — product intent, ROI, north-star |
| Open | Hybrid — human scopes, agent drafts |
| Visualize | Hybrid — agent maps structure, human refines architecture |
| Execute | ~90% agent-swarm via `dispatch`/`exec`, human tech-lead greenlights |
| Release | Hybrid — automated gates + human sign-off |
| Notify | Hybrid — agent drafts release notes/blog stub, human reviews outbound tone |
| Sustain | Agent-first, human-bounded oversight |

---

## Part 3 — Rollout Mechanics

**`synlynk init`** — new projects get a `## Business Goals` section in the `roadmap.md` template, using the same `<!-- goal:G1 -->` HTML-comment tagging convention already used for `gh:`/`pr:` tags on stories.

**`synlynk migrate`** — `_migrate_import()` gains a parse pass: `## Business Goals` → `goals` table, then resolves `<!-- goal:G1 -->` tags on existing arcs/stories into `goal_id` FKs. Untagged items get `goal_id = NULL`. Non-destructive; `--dry-run` shows the plan first, matching the fail-loud-but-safe posture already shipped in #126.

**`synlynk scan --deep`** — the natural home for enterprise-level rollup: aggregates the `goals` table from every project's `.synlynk/state.db` in a workspace into a portfolio view. No new command needed.

**Vizor (`viz.py`, `synlynk status --json`)** — the existing `dreams` list (built from `roadmap_arcs`) nests one level deeper under a new `goals` list; each Goal card contains its child Dream arcs (unchanged stage-bar rendering, now using the 7 GOVERNS stages) plus rolled-up cost/status. Goals with no Dreams yet render as bare cards. Live Issues/maintenance render in a separate always-visible lane, never inside a Goal card.

**HUD (`synlynk watch`, `hud.py`)** — stays transient/operational. `CYCLES` (`hud.py:13`) is updated from the 6-stage list to the 7-stage GOVERNS list with matching `CYCLE_COLOURS`. Gains a compact "current Goal" header line + a Now/Next/Later queue ordered by the three-factor dispatch score. Does not grow full Goal cards — that stays Vizor's job.

**Abstraction-level mapping:**
- **Dev**: a Story under a Dream, in one repo's Vizor.
- **Team**: Goal cards for one project.
- **Enterprise**: `scan --deep` workspace rollup across projects.

---

## Open Items for Implementation Planning

- `LAUNCH_TASK_TEMPLATES` (`synlynk/__init__.py:108+`) needs every `"cycle"` value updated from the drifted `design`/`build`/`sustain` vocabulary to the 7 GOVERNS stage keys.
- `task_to_cycle` map (`synlynk/__init__.py:5539`) needs remapping: `"review"` currently maps to `"engage"`, which no longer exists — likely moves to `"execute"` (agent-swarm review) or splits based on whether it's a code-review checkpoint (Execute) vs. release-readiness check (Release).
- BS-8 scope (goals table, CLI, context injection) is the implementation vehicle for Part 1 and is unscoped as an implementation plan — next step.
