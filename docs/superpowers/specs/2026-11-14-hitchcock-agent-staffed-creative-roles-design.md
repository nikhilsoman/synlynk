# Hitchcock Autonomy Pass 1: Agent-Staffed Creative Roles

**Date:** 2026-11-14
**Status:** Draft — Pass 1 of 2 (research/design only, no implementation authorized)
**Tracked under:** Epic #5261 ("[Epic] Autonomous-future planning: rxcc, cc-videoreframing (vdowrx), Hitchcock")
**Roadmap entry:** First of two Hitchcock autonomy specs. Pass 2 (business/ops layer — positioning, revenue model, customer onboarding) is a separate, later spec sequenced after this one, per the user's explicit "both, roles first then ops" decision.

---

## Context

Hitchcock already ships a fully autonomous **render pipeline**: `hitchcock produce <scene.json>` runs H-SIR normalization → CKB RAG prompt injection → generation → DAM cataloging → deterministic QC gates (Script Supervisor's 180°/ArcFace continuity check) → SACE pacing/crop → finishing → transmedia export → call sheets, with no human touch once a `scene.json` exists. What is *not* autonomous is everything upstream of that file: Hitchcock's `CollaborationManager` (`engine/collab.py`) models film production as five human-invite-only roles — DIRECTOR, CINEMATOGRAPHER, SOUND_DESIGNER, PRODUCER, VIEWER — who author scene intent and creative direction through a real-time "Creative Direction Panel" (`engine/ui_server.py`'s `DailiesRoomAPI`).

`project-docs/roadmap.md`'s "Positioning" and "Business Goals" sections are literal unfilled placeholders — confirming no business-direction work has happened yet. That gap is explicitly Pass 2's scope, not this one's.

**This spec answers:** what does it mean for an AI agent, not a human, to occupy one of Hitchcock's creative roles — which roles, how an agent "joins," how its decisions reach the pipeline, and how role assignment is governed over time.

**Decided with the user during brainstorming (summarized, detail in Sections 1-5 below):**
- Full 12-role roster, not a single pilot role (Section 1).
- An agent occupies a role via the *existing* `CollaborationManager` invite/join flow — the same surface a human uses — not a new bypass integration point (Section 2).
- This design is built explicitly on top of IB-PMEO Pass 2's not-yet-implemented generalized intent pipeline (`synlynk/intent_pipeline.py`, capture→classify→decompose→dispatch→await→consolidate, `docs/superpowers/specs/2026-11-14-ib-pmeo-pass2-generalized-intent-pipeline-design.md`) rather than inventing a second, parallel dispatch mechanism (Section 3).
- Role assignment starts **per-scene** (re-resolved each dispatch, like `dispatch_agent()`'s existing harness routing) with an explicit, evidence-gated path to **promote to persistent per-production** assignment, mirroring this repo's own Empirical Capability Assessment Policy pattern (Section 4).
- Scene-level role ordering (sequential director-led vs. parallel-then-fold) is **not** fixed to one shape — both are supported, selected per role-combination via registry lookup, decided empirically later (Section 5).

**Dependency note:** this spec makes Hitchcock the second concrete dependent on IB-PMEO Pass 2 (previously only Pass 2's own generic dry-run target). Pass 2 remains on hold for implementation per the user's explicit instruction in this session ("we are likely to hold the implementation plan for a while"). This spec's own implementation is therefore blocked on that hold lifting — not merely benefiting from Pass 2 once it exists.

---

## Section 1 — Role Roster

Twelve roles, each assigned a `(stage, discipline, verb)` triple per IB-PMEO Pass 1's taxonomy (`docs/superpowers/specs/2026-11-14-ib-pmeo-activity-taxonomy-and-archetype-classification-design.md`). Four already exist in `CollaborationManager` as human-invite roles today (marked *existing*); eight are new additions this spec introduces to the registry.

| Role | Status | stage | discipline (SFIA) | verb | archetype |
|---|---|---|---|---|---|
| SCREENWRITER | new | visualize | REQM | author | director |
| DIRECTOR | existing | visualize | ARCH | author | director |
| VISUALIZER | new | visualize | ARCH | structure | director |
| PRODUCTION_DESIGNER | new | execute | DESN | execute | creator |
| COSTUME_DESIGNER | new | execute | DESN | execute | creator |
| CINEMATOGRAPHER | existing | execute | DESN | execute | creator |
| COMPOSER | new | execute | SNDD | execute | creator |
| SOUND_DESIGNER | existing | execute | SNDD | execute | creator |
| VFX_SUPERVISOR | new | execute | DESN | execute | creator |
| EDITOR | new | execute | TEST | verify | inspector |
| PRODUCER | existing | sustain | PRMG | dispatch | orchestrator |
| MARKETING | new | release | MKT | execute | creator |

**Why DIRECTOR and SCREENWRITER both get `author`/`visualize` but different disciplines:** SCREENWRITER (REQM — requirements/intent capture) drafts the beat sheet/scene brief; DIRECTOR (ARCH — the creative-architecture decision) turns that brief into the concrete scene.json fields (VAD mood targets, camera presets, shot list) the pipeline actually consumes. This mirrors Pass 1's existing `spec`/`architecture` vs. `brainstorm` distinction (strategist's `set_intent` vs. director's `author`) applied one level down, inside a single production's creative chain rather than across synlynk's own engineering lifecycle.

**Why EDITOR is `inspector.verify`, not `creator.execute`:** an editor's core activity is judging whether assembled footage serves the scene's intent (pacing, cut points) against a standard — structurally identical to Script Supervisor's existing automated QC gate, not a generation step. This reuses the precedent already running in production rather than inventing a new archetype mapping.

**Why MARKETING is `release`, not `execute`:** transmedia export/distribution is explicitly a GOVERNS `release`-stage activity, not part of scene production — this keeps MARKETING's scope to what ships *out* of a completed production, feeding directly into Pass 2 (business/ops).

## Section 2 — Integration Point: Agents Join via `CollaborationManager`

An agent occupies a role through the *same* mechanism a human does today: `hitchcock collab invite --role <ROLE>` generates an HMAC token; the agent "joins" by calling `hitchcock collab join <token>` (or the equivalent `/api/collab/join` REST call) exactly as a human collaborator's client would. No new bypass integration point is introduced.

**Consequence of this decision:** every role, human or agent, is visible and auditable through the one existing surface — the Dailies Room UI's Creative Direction Panel and `collab list` — rather than creating a second, invisible channel for agent-driven creative decisions. A human producer reviewing a production sees an agent DIRECTOR in the collaborator list exactly as they'd see a human one, with the same invite/revoke lifecycle.

**What this does *not* yet specify:** the agent-side client that receives a join token and then actually drives the Creative Direction Panel's API (`/api/creative-direction`) to set VAD mood, camera presets, and author scene.json fields. That client is this spec's load-bearing new component — Section 3 places it.

## Section 3 — Dispatch: Built on IB-PMEO Pass 2's Pipeline

A role-fill request becomes an `Intent` (source: `cli` or `api`, per Pass 2 Section 2) that enters Pass 2's pipeline:

1. **Capture:** a scene needing a DIRECTOR (etc.) assignment is captured as an `Intent` with `expected_output_format: "scene_json_fields"` and a `governs_link` to the production's goal/story.
2. **Classify:** resolves to the role's `(stage, discipline, verb)` triple from Section 1's table.
3. **Decompose:** a DIRECTOR activity is a **leaf** once an `ExecutorRegistry` entry exists for it — this spec registers one `ExecutorEntry` per role:
   - `executor_kind: "shell_cli"` (or `"http_api"` once a Hitchcock REST client exists), `invocation_spec`: the `hitchcock collab join <token>` + Creative Direction Panel driving sequence, `await_spec: "poll_url"` against the production's scene state.
4. **Dispatch:** Pass 2 hands the `ExecutorEntry`'s `invocation_spec` to `dispatch_agent()`, which resolves a harness (Claude/Agy/Grok/Codex) per the Empirical Capability Assessment Policy's measured routing — **not** a hand-picked harness per role. This spec does not reserve a specific harness for DIRECTOR vs. COSTUME_DESIGNER; that is exactly the kind of routing decision the Capability Assessment Policy already owns.
5. **Await:** the dispatched harness drives the join + Creative Direction Panel flow; `await_result` polls the production's scene state until the role's expected fields (e.g. DIRECTOR's VAD/camera/shot-list fields) are populated or the dispatch fails.
6. **Consolidate:** per Section 5, either folds sequentially into the next role's input or merges in parallel via a registered `FoldStrategy` once all roles for the scene report back.

**Why this, not a Hitchcock-internal dispatch loop:** Hitchcock already depends on synlynk's harness fleet for its own *software delivery* (the `.synlynk/` dogfooding integration found during recon). Building a second, Hitchcock-specific agent-dispatch mechanism for *creative* roles would duplicate harness-resolution, cost-ledger, and policy-gating logic Pass 2 is already designing generically. The cost is the dependency noted in Context — accepted explicitly by the user.

## Section 4 — Assignment Scope: Per-Scene Default, Evidence-Gated Promotion to Persistent

**Default (interim):** each scene's role-fill is a fresh dispatch through Section 3's pipeline — the harness playing DIRECTOR for scene 7 may differ from the harness that played DIRECTOR for scene 6. No persistent "Agy is this production's DIRECTOR" binding exists at launch.

**Promotion path:** this spec adopts the same measured-promotion shape as the repo's own Empirical Capability Assessment Policy (`docs/superpowers/specs/...` — the harness-routing policy governing `.synlynk/policy.json`'s `task_allocation`), applied here to **role persistence** rather than harness choice:

- **Metric:** a per-production, per-role continuity/consistency score — concretely, variance in VAD/style fields and CKB-retrieved reference vectors across consecutive scenes assigned to *different* harnesses for the same role, vs. scenes assigned to the *same* harness. This is a new metric this spec introduces (RSI — **Role Stability Index** — defined here, not borrowed from an existing table); no existing `capability_ratings` column measures creative continuity today.
- **Minimum sample:** ≥5 scenes in one production for a given role before RSI is considered meaningful, mirroring the Empirical Capability Assessment Policy's own ≥5-sample floor.
- **Promotion rule:** if per-scene re-resolution's RSI for a role falls below a threshold (continuity suffers measurably from re-resolution) relative to a same-harness baseline, that role is promoted to a **persistent per-production** `CollaborationManager` invite for the remainder of the production — one agent identity holds it until the production completes or RSI is re-evaluated.
- **No promotion without evidence:** a role is never locked to persistent assignment by default or by convenience; only by a measured RSI finding, same discipline as the Empirical Capability Assessment Policy's "unmeasured is not evidence of poor fit" rule.

**Deferred from this spec:** the RSI formula's exact statistical definition (what counts as "measurable" continuity loss) and the `capability_ratings`/`cost_entries` schema change needed to record it — this spec establishes that the metric and promotion gate must exist, not their implementation.

## Section 5 — Scene-Level Role Ordering: Both Shapes Supported

Per the user's explicit "both supported, too early to say" answer, role ordering for a given scene is **not** a single global pipeline shape. It is itself a decomposition-graph property, resolved the same way Pass 2 resolves any other decomposition: by registry lookup on `(discipline, verb)` combinations.

- **Sequential (director-led):** SCREENWRITER's beat-sheet activity decomposes into a DIRECTOR child activity (scene intent/VAD), which itself decomposes into parallel CINEMATOGRAPHER/PRODUCTION_DESIGNER/COSTUME_DESIGNER/COMPOSER children, which fold upward through EDITOR's verify-gate before VFX_SUPERVISOR's pass. This is the default `decompose_fn` registered for a new production.
- **Parallel-then-fold:** all applicable roles' activities are siblings under one scene-level parent from the start; a `FoldStrategy` (kind: `content_assembly`, per Pass 2 Section 2's worked example of narrative/sequential-assembly folds) merges their outputs. Available as an alternate registered `decompose_fn` for the same `(discipline, verb)` key, selectable per production.

**Why registry-selectable rather than a flag:** this is consistent with Pass 2's own design principle (Section 2 of that spec) that `executor_kind` and `FoldStrategy.kind` are open registries precisely because "how work combines" is domain-dependent — role ordering for a film production is exactly the kind of domain-specific choice that principle was written to absorb, not an exception to it.

**Deferred from this spec:** which ordering actually produces better consolidated scenes in practice — an empirical question for whichever pilot production first exercises this, not decidable at design time.

---

## Deferred (explicitly out of scope for this spec)

- **Business/ops layer** — positioning, revenue model, customer onboarding, pricing. Explicitly Pass 2 of this two-pass Hitchcock initiative, per the user's "roles first then ops" sequencing.
- **IB-PMEO Pass 2's own implementation** (`synlynk/intent_pipeline.py`) — this spec depends on it but does not re-authorize or re-scope its build; that remains on hold per the user's standing instruction.
- **RSI's exact formula and schema change** (Section 4) — flagged as needed, not specified.
- **Agent-side Creative Direction Panel driving client** (Section 2's "what this does not yet specify") — the concrete code that turns a join token into actual panel API calls is an implementation-plan concern, not designed here.
- **VIEWER role** — intentionally excluded from the 12-role roster; it is a read-only observer role in `CollaborationManager` today with no creative-authorship activity to map onto Pass 1's taxonomy.
- **Populating real `ExecutorRegistry`/`FoldRegistry` entries beyond what's needed to validate this design** — an implementation task, same deferral Pass 2 itself already carries.

## Validation Criteria

Before any implementation plan is written against this design:

1. Confirm IB-PMEO Pass 2's hold has been lifted and its pipeline has at least the minimal `ExecutorRegistry`/`decompose`/`FoldRegistry` shape implemented (this spec's Section 3 has nothing to dispatch against otherwise).
2. Run one real `hitchcock collab invite --role DIRECTOR` → agent join → Creative Direction Panel drive → scene.json population cycle by hand (semi-manually, no RSI tracking yet) to confirm the integration point in Section 2 actually works end-to-end before building the dispatch wiring in Section 3 around it.
3. Confirm at least one sequential and one parallel-then-fold scene both produce a valid consolidated scene.json through the existing `hitchcock produce` pipeline unmodified — the whole point of this design is that the render pipeline downstream doesn't need to know or care how its scene.json was authored.
