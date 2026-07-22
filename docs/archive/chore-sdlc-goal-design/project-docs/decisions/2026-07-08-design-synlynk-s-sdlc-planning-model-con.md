---
decision_id: dec-f144d0e6
topic: "Design Synlynk's SDLC/planning model. CONTEXT: rxcc roadmap is purely feature/version-organized with no layer connecting cross-epic tickets to a business outcome. Synlynk's own cycle model (Dream->Plan->Work->Ship->Maintain->Engage) makes a Dream = a version arc; there is no goal concept above Dream. OKR (quarterly Objective+KeyResults, cascading Company->Team->Individual) is the classic industry answer but assumes human sprint velocity. Other models worth weighing: SAFe (Portfolio/Program/Team epics + WSJF), Shape Up (fixed appetite, betting table, six-week cycles), North Star Metric, RICE scoring. Synlynk dispatches work to an agent fleet (Claude/Agy/Grok/Codex) at a pace of hours/days not sprints. Must work at 3 abstraction levels simultaneously: dev (story/PR), team (single project roadmap), enterprise (portfolio across all synlynk-managed projects). There is already a parked, unscoped backlog item: BS-8 goal hierarchy (meta + milestone + story) + synlynk goals CLI + three-layer context injection. QUESTIONS TO ANSWER: (1) Top-level planning unit - narrative Business Goal (outcome+success criterion+deadline) vs OKR-style Objective+KeyResults - coexist or same thing renamed? (2) How does Goal relate to existing Dream - rename Dream to Goal, put Goal above Dream owning several version-arc Dreams, or keep Dream as-is and add Goal as orthogonal tag on stories/epics? (3) Given agent-fleet velocity what is the right goal-review cadence - continuous, weekly, monthly - should quarterly OKR cadence be dropped entirely? (4) How do dev/team/enterprise nest - strict tree (enterprise Goal -> team Epic -> dev Story) or many-to-many? (5) What orders the Now/Next/Later queue under a Goal - RICE, WSJF, or something simpler suited to a fast dispatch loop? (6) Should Goal be first-class in the data model (new synlynk goal CLI, new state.db table, building on parked BS-8) or stay a roadmap.md documentation convention only? (7) How do Live Issues / pure-maintenance work not tied to any Goal get represented without cluttering the Goal-oriented view? Give a concrete recommended structure, not just principles."
date: 2026-07-08
panel: [claude, agy, grok, codex]
status: approved
---

## Topic
Design Synlynk's SDLC/planning model. CONTEXT: rxcc roadmap is purely feature/version-organized with no layer connecting cross-epic tickets to a business outcome. Synlynk's own cycle model (Dream->Plan->Work->Ship->Maintain->Engage) makes a Dream = a version arc; there is no goal concept above Dream. OKR (quarterly Objective+KeyResults, cascading Company->Team->Individual) is the classic industry answer but assumes human sprint velocity. Other models worth weighing: SAFe (Portfolio/Program/Team epics + WSJF), Shape Up (fixed appetite, betting table, six-week cycles), North Star Metric, RICE scoring. Synlynk dispatches work to an agent fleet (Claude/Agy/Grok/Codex) at a pace of hours/days not sprints. Must work at 3 abstraction levels simultaneously: dev (story/PR), team (single project roadmap), enterprise (portfolio across all synlynk-managed projects). There is already a parked, unscoped backlog item: BS-8 goal hierarchy (meta + milestone + story) + synlynk goals CLI + three-layer context injection. QUESTIONS TO ANSWER: (1) Top-level planning unit - narrative Business Goal (outcome+success criterion+deadline) vs OKR-style Objective+KeyResults - coexist or same thing renamed? (2) How does Goal relate to existing Dream - rename Dream to Goal, put Goal above Dream owning several version-arc Dreams, or keep Dream as-is and add Goal as orthogonal tag on stories/epics? (3) Given agent-fleet velocity what is the right goal-review cadence - continuous, weekly, monthly - should quarterly OKR cadence be dropped entirely? (4) How do dev/team/enterprise nest - strict tree (enterprise Goal -> team Epic -> dev Story) or many-to-many? (5) What orders the Now/Next/Later queue under a Goal - RICE, WSJF, or something simpler suited to a fast dispatch loop? (6) Should Goal be first-class in the data model (new synlynk goal CLI, new state.db table, building on parked BS-8) or stay a roadmap.md documentation convention only? (7) How do Live Issues / pure-maintenance work not tied to any Goal get represented without cluttering the Goal-oriented view? Give a concrete recommended structure, not just principles.

## Panel Inputs

### claude
**Position: narrative Business Goal, not OKR; Goal sits above Dream as a new first-class layer; continuous review; loose many-to-many nesting; simple cost/value heuristic for ordering; first-class in the data model but built minimally on the parked BS-8; Live Issues get a standing non-Goal lane.**

1. **Goal shape**: Skip OKR. Key Results assume human quarterly cadence and are gamed even by humans — an agent fleet will optimize the metric, not the outcome, faster than you can notice. Use a narrative Business Goal: outcome + one success criterion + deadline (or "ongoing"). It's legible to both a founder and a dispatch prompt.

2. **Goal vs Dream**: Don't rename Dream — it's your version-arc unit and already load-bearing in the cycle model. Add Goal *above* Dream: one Goal owns 1–N Dreams across time. This gives you the missing layer without breaking Dream/Plan/Work/Ship/Maintain/Engage.

3. **Cadence**: Continuous. Quarterly is a human-meeting artifact; at hours/days dispatch velocity, review Goal health at every Ship event and let `synlynk status` surface drift async, not on a calendar.

4. **Nesting**: Many-to-many, not strict tree. A story can serve two Goals (e.g., a refactor that's both a cost-reduction Goal and unblocks a feature Goal); forcing a tree causes people to fake-split work to fit taxonomy.

5. **Ordering**: Skip RICE/WSJF — both need estimation inputs your agents can't honestly produce yet. Use a 2-factor heuristic: Goal-criticality (does this move the active success criterion) × unblocked-now (no dependency wait). That's a sort agents can self-apply at dispatch time.

6. **Data model**: First-class, but thin. Extend BS-8's parked scope: a `goals` table (id, outcome, criterion, deadline, status), a nullable `goal_id` FK on epics/stories, and `synlynk goal` CLI for create/list/link. Don't build KR tracking — that's the OKR trap re-entering through the schema.

7. **Live Issues**: Represent as `goal_id = NULL` with a `lane: maintenance` tag, shown in a separate queue, not scored against Goal-criticality. Un-Goaled work should be visible, not hidden, but never compete in the same ranked list as Goal-serving work.

### agy
Last completed task: N/A (Initial design consultation)
Next task from `todo.md`: Respond to SDLC/planning model design panel query

We recommend implementing the parked BS-8 goal hierarchy as a first-class data model in `state.db` and the CLI, rather than keeping it as a markdown convention. This enables the three-layer context injection vital for guiding autonomous agents.

Here is the concrete recommended structure:
1. **Top-Level Unit**: Narrative **Business Goals** (outcome + success criterion + deadline) replace OKRs, which assume slower human sprint cycles.
2. **Goal vs. Dream**: **Goal sits above Dream**. A Business Goal owns multiple version-arc Dreams.
3. **Review Cadence**: Drop quarterly OKRs. Move to a **weekly review** of Goals and continuous agent dispatch.
4. **Nesting**: A **strict tree** (Enterprise Goal -> Team Epic -> Dev Story) to simplify agent dependency mapping and context injection.
5. **Queue Ordering**: **WSJF-Lite** (Business Value / estimated Agent Hours), automatically re-calculated as agents complete tasks.
6. **Data Model**: First-class representation in `state.db`. The `synlynk goals` CLI will inject active Goal metadata into agent prompts.
7. **Maintenance/Live Issues**: Represented via an orthogonal, persistent **"Run-the-Engine" (RTE) Goal** category. Maintenance tickets map here to keep thematic Business Goals clean.

My position is that Synlynk must treat Goals as first-class, CLI-queryable prompt injection sources rather than static documentation. By placing Goals above Dreams in a strict execution tree and scheduling work via WSJF-Lite, Synlynk creates a machine-readable planning layer matching the high velocity of its agent fleet.

### grok
**Analysis**

Current synlynk model uses `roadmap_arcs` + `roadmap_phases` + stories (with `phase` + cycle tags) + 6-cycle HUD/launch overlay (Dream/Plan/Work/Ship/Maintain/Engage). Dreams effectively equal version arcs; there is no durable outcome layer above them. This matches the rxcc symptom: purely feature/version lists with no cross-epic thread to a business result. The parked BS-8 item explicitly called for "goal hierarchy (meta + milestone + story) + synlynk goals CLI + three-layer context injection," and earlier agentic-PM brainstorms sketched Project → Arc → Phase → Epic → Story → Event.

Industry models must be filtered for agent-fleet reality (hours/days dispatch, no human sprint velocity, three simultaneous abstraction levels):

- OKR cadence and SAFe WSJF are mismatched (too slow, too heavy).
- Shape Up's fixed appetite + betting table is the closest cultural fit.
- RICE is usable but overkill for a fast loop.
- North Star is a measurement lens, not a planning primitive.

**Concrete recommended structure**

1. **Top-level unit**: Narrative **Business Goal** (outcome statement + 1-3 measurable success criteria + rough target window/deadline). OKR-style Objectives + Key Results coexist as a *view* or reporting format auto-derived from Goals + signals (e.g., "reduce flatlines 50%"), not the stored primitive.

2. **Goal ↔ Dream relation**: Keep Dream as-is (the ideation/intention *cycle* label and version-arc container). Place **Goal above Dream**: a Goal owns one or more Dreams/version arcs plus cross-cutting epics that deliver its outcome. Do not rename Dream.

3. **Cadence**: Continuous + signal-driven (job complete, sentinel, scan delta, PR merge). `synlynk goals review` or HUD health pulse at most weekly. Drop quarterly OKR rituals entirely; use short "bet windows" (1-6 weeks) modeled on Shape Up appetite.

4. **Nesting (dev/team/enterprise)**: Default **strict tree** for clarity and context injection (Portfolio Goal → Team Goal → Arc/Phase/Epic → Story). Add a lightweight `goal_contributions` junction for many-to-many cross-cuts (one Live Issue or security epic contributing to two Goals). Stories carry a primary `goal_id`.

5. **Now/Next/Later ordering under a Goal**: Simpler dispatch-native signal: explicit priority + topological depends_on + urgency (live-issue severity + sentinel hits + scan gaps + age, decayed by est_tokens). No full RICE/WSJF matrix; agents propose re-sorts in Plan cycle. Launch/viz surface swimlanes per Goal.

6. **Data model**: **First-class**. Implement the parked BS-8 meta-goals story: add `goals` table + `goal_links`/`goal_contributions`, `synlynk goal` subcommand (create/list/assign/close/review/bet), and FKs from arcs/stories. Roadmap.md, todo.md, and viz become projections. Update `generate_context` (and dispatch loop) to perform true three-layer injection:
   - Meta: active Goals + success criteria (workspace/portfolio scoped)
   - Milestone: current Dream/Arc/Phase/Epic + done_criteria
   - Story: specific task + verify

7. **Live Issues / pure maintenance**: Stories may exist with `cycle=maintain` or `sustain` tag and *no* Goal (or auto-linked to a single always-present "Platform Health" Goal). In Goal-oriented views (viz Gantt, launch, `synlynk goals`), show them collapsed in a "Sustain / Unscoped" lane or filter. HUD and Maintain/Engage cycle always surface them regardless of Goal. LIVE-N and sentinel items create/link sustain stories without polluting active Goal queues.

**Recommendation**

Adopt the Business Goal as the new top primitive, implemented first-class in state.db with `synlynk goal` CLI and three-layer context injection. Dreams and cycles remain orthogonal activity labels and version containers. Use tree + limited junctions, signal-driven (not calendar) prioritization, and explicit sustain lanes. This directly closes the rxcc-style gap, fits agent velocity, works at all three abstraction levels, and turns the parked BS-8 item into the canonical planning spine rather than an afterthought documentation convention.

This is the position: ship Goal as first-class data + CLI + context layer on top of (not instead of) the existing Dream/cycle/story model.

### codex
Synlynk should use a **Business Goal** as the top-level planning object, with **OKR as a presentation format**, not a parallel system. In other words: `Goal` is the durable entity; `Objective` and `Key Results` are fields on it when you need quarterly reporting. That matches BS-8’s three-layer goal stack and avoids duplicating semantics. See [BS-8 goal hierarchy](/Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-27-bs8-harness-capability-awareness-loop-dispatch-design.md#L183) and the existing state-db PM hierarchy in [state-db agentic PM](/Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md#L89).

Keep **Dream** as the version/arc execution layer, not a rename of Goal. The right model is **Goal -> one or more Dreams -> Epics -> Stories**. That preserves Synlynk’s current cycle language while putting the outcome above the version arc. A Goal can span several Dreams; a Dream should not be asked to carry business outcome semantics by itself.

Review cadence should be **continuous at dispatch time, weekly for operational review, monthly for portfolio correction**. I would not keep a rigid quarterly OKR operating cadence as the primary mechanism; quarterly checkpoints can remain a reporting artifact for humans, but the agent fleet needs shorter control loops.

Nesting should be **mostly strict tree with explicit cross-links**, not pure many-to-many. One story should have one primary Goal/Epic parent for routing and reporting, but it may reference secondary Goals for traceability. That keeps the dispatch engine deterministic.

For ordering Now/Next/Later, use a **simple dispatch score**: dependency readiness first, then deadline risk, then impact, then effort/tokens. Do not start with full RICE or WSJF; they are too heavy for hours-to-days agent throughput.

Goal must be **first-class in `state.db` and a `synlynk goals` CLI**. The parked BS-8 item should become the implementation path, not a docs-only convention. Live Issues and pure maintenance should live in an orthogonal **Interrupts / Maintenance** lane with `goal_id = NULL` and `type = live_issue|maintenance`, so they stay visible without polluting Goal views.

My recommendation: **Goal is the business-outcome layer, Dream stays the version arc, the system runs on rolling weekly/monthly reviews, and the model must be first-class in state.db now.**

## Synthesis
## Synthesis

All four converge on the shape of this system even where they disagree on details:

**1. Goal shape** — Unanimous: skip OKR as the stored primitive. Key Results assume human quarterly cadence and get gamed by an agent fleet optimizing the metric, not the outcome. Use a narrative **Business Goal**: outcome + success criterion(s) + deadline/window. Codex's refinement is worth keeping — Objective/KR can exist as an optional *reporting view* derived from Goals, for whoever still wants a quarterly slide, but it's not what's stored.

**2. Goal vs Dream** — Unanimous: don't rename Dream, don't collapse it into Goal. **Goal sits above Dream** as a new outcome layer; a Goal owns one or more Dreams (version arcs) plus the epics/stories that serve it. This is the cleanest fix for the rxcc symptom (no outcome layer above version-organized work) without breaking the existing cycle model.

**3. Cadence** — Consensus on dropping quarterly OKR rituals. The real disagreement is continuous-only (claude) vs. continuous-with-a-human-checkpoint (agy: weekly; grok/codex: weekly operational + monthly portfolio). Given synlynk still has a human (you) steering portfolio-level tradeoffs even though dispatch itself runs at machine speed, the checkpoint is worth keeping as a cheap async pulse, not a ritual: **continuous signal-driven review at dispatch/Ship time, plus a standing weekly `synlynk goals status` rollup for human sanity-check.** No monthly/quarterly layer.

**4. Nesting** — 3 of 4 (agy, grok, codex) favor a tree for deterministic routing and context injection; only claude wants pure many-to-many. The tree is right for the common case (a story needs one unambiguous parent to inject context and route dispatch), but claude's concern about fake-splitting work to fit taxonomy is real. Resolution: **strict tree as primary (Goal → Dream → Epic → Story), with an optional secondary `goal_contributions` link for genuine cross-cutting work** (grok's junction table, echoed by codex's "secondary Goals for traceability"). One primary parent, occasional additional references — not fully many-to-many.

**5. Ordering** — Consensus against full RICE/WSJF (too much estimation overhead for hours/days dispatch); agy's WSJF-Lite is the outlier and still requires an hours-estimate input the fleet can't honestly produce yet. The rest converge on the same shape: **dependency-unblocked-now, then deadline/urgency risk, then Goal-criticality/impact** — a score cheap enough for an agent to self-apply at dispatch time, no estimation ritual required.

**6. Data model** — Unanimous: first-class in `state.db`, not a markdown convention. This is exactly the parked **BS-8** scope (goal hierarchy + `synlynk goal` CLI + three-layer context injection) — ship it as the implementation path rather than re-scoping. Minimal schema: `goals` table (id, outcome, criterion, deadline, status), `goal_id` FK on epics/stories, `goal_contributions` junction for secondary links, `synlynk goal` CLI (create/list/link/status). Skip KR tracking fields entirely — that's the OKR trap re-entering through the schema, as claude flagged.

**7. Live Issues / maintenance** — Unanimous: orthogonal, not absent. `goal_id = NULL` with a `lane`/`type` tag (`maintenance`/`live_issue`), surfaced in its own queue/lane in `synlynk status` and the viz layer, never scored against Goal-criticality or mixed into the ranked Now/Next/Later list under a Goal. Grok's suggestion of an always-present "Platform Health" pseudo-Goal is an unnecessary wrapper — a nullable `goal_id` + lane tag is simpler and keeps the Goal view genuinely goal-only.

---

**Decision:** Synlynk adopts a narrative **Business Goal** (outcome + success criterion + deadline) as the new top-level planning primitive, implemented first-class in `state.db` by shipping the parked **BS-8** goal-hierarchy work (`goals` table, nullable `goal_id`/`goal_contributions` FKs on epics/stories, `synlynk goal` CLI, three-layer context injection). **Dream is unchanged** and sits *below* Goal as the version-arc execution container (one Goal owns 1–N Dreams). Nesting is a **strict tree by default** (Goal → Dream → Epic → Story) with an optional `goal_contributions` junction for genuine cross-cutting work, avoiding both taxonomy-forcing and unbounded many-to-many sprawl. Review is **continuous and signal-driven** (at Ship events, sentinel triggers, PR merges) with a lightweight **weekly `synlynk goals status` rollup** for human oversight — no quarterly OKR cadence anywhere in the loop. Now/Next/Later ordering under a Goal uses a **simple three-factor dispatch score** (dependency-unblocked-now → deadline/urgency risk → Goal-criticality), explicitly rejecting RICE/WSJF as too estimation-heavy for hours/days agent throughput. Live Issues and pure maintenance work carry `goal_id = NULL` with a `lane: maintenance` tag, visible in their own queue and always surfaced by `synlynk status`, but never ranked against Goal-serving work.

## Decision
**Decision:** Synlynk adopts a narrative **Business Goal** (outcome + success criterion + deadline) as the new top-level planning primitive, implemented first-class in `state.db` by shipping the parked **BS-8** goal-hierarchy work (`goals` table, nullable `goal_id`/`goal_contributions` FKs on epics/stories, `synlynk goal` CLI, three-layer context injection). **Dream is unchanged** and sits *below* Goal as the version-arc execution container (one Goal owns 1–N Dreams). Nesting is a **strict tree by default** (Goal → Dream → Epic → Story) with an optional `goal_contributions` junction for genuine cross-cutting work, avoiding both taxonomy-forcing and unbounded many-to-many sprawl. Review is **continuous and signal-driven** (at Ship events, sentinel triggers, PR merges) with a lightweight **weekly `synlynk goals status` rollup** for human oversight — no quarterly OKR cadence anywhere in the loop. Now/Next/Later ordering under a Goal uses a **simple three-factor dispatch score** (dependency-unblocked-now → deadline/urgency risk → Goal-criticality), explicitly rejecting RICE/WSJF as too estimation-heavy for hours/days agent throughput. Live Issues and pure maintenance work carry `goal_id = NULL` with a `lane: maintenance` tag, visible in their own queue and always surfaced by `synlynk status`, but never ranked against Goal-serving work.

> Signatures: see 2026-07-08-design-synlynk-s-sdlc-planning-model-con.json
