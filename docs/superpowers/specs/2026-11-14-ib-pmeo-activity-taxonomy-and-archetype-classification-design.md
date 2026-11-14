# IB-PMEO Pass 1: TPM Sweep Precedent, Current Activity Set & Cross-Industry Activity Taxonomy

**Date:** 2026-11-14
**Status:** Draft — Pass 1 of 2 (research/design only, no implementation authorized)
**GOVERNS linkage:** `goal-18372f86` ← `story-7fd63985`. Tracked under epic #5258.
**Roadmap entry:** First of two specs resolving the IB-PMEO functional-protocol research kicked off under #5258. Pass 2 (the intent capture→classification→decomposition→dispatch→consolidation pipeline itself, agenda item 6) is a separate, later spec building on this one's taxonomy.

---

## Context

This spec answers agenda items 1-5 of the IB-PMEO brainstorm: review the TPM sweep/wake-cycle mechanism as existing precedent, catalog the activity types it performs, catalog the activity set already in frequent use across synlynk's own dogfooding, construct a cross-industry activity taxonomy, and classify it against the archetypes already used in Workspace Agent definitions.

**Prior art this spec builds on without re-deriving:**

- `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md` — the Intent Capture Layer (approved, not yet fully built) that turns raw intent into GOVERNS goals/stories for synlynk's own engineering.
- `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` — the 8-role org chart (pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) and role→harness dispatch policy.
- `docs/superpowers/specs/2026-11-10-autonomous-fleet-orchestrator-and-organogram-designer-design.md` (ratified `dec-4a53a2ee`) — the 6 universal archetypes (orchestrator/strategist/director/creator/inspector/custodian), the `Agent = (Archetype, SFIA Discipline, Industry Domain)` formula, and worked cross-industry tables (Software/SaaS, Film, Video Production, Biopharma). This spec adds the one layer that spec does not yet have: an **activity-level** (verb-level) taxonomy — what an agent *does*, not just what agent exists.
- `docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md` (Track 4 of epic #5245, `story-906cfb5b`) — the business-model/tiering layer for IBPD-as-a-service. Distinct layer; this spec's taxonomy is substrate the Track-4 thesis could eventually point at, not a restatement of it.

---

## Section A — TPM Sweep/Wake-Cycle Mechanism (agenda items 1-2)

`run_tpm_wake_cycle()` (`synlynk/tpm_sweep.py:199`) is a working, narrow instance of the capture→classify→route→dispatch→await→consolidate pattern this brainstorm's Pass 2 will generalize. Its stages:

1. **Capture:** `archive_superseded_stories()` + `ingest_backlog()` (`synlynk/backlog.py:460`) pull raw signal — currently only open GitHub issues (`fetch_open_github_issues()`).
2. **Classify:** `triage_backlog()` (`backlog.py:553`) calls `_classify_role_and_stage()` (`backlog.py:281`), a keyword/label matcher that assigns:
   - a **role** (qa, architect, pm, marketing, tpm, designer, dev — matched against GitHub labels, `@role` mentions, then keyword fallback),
   - a **GOVERNS stage** (goal, open, visualize, execute, release, notify, sustain),
   - a **complexity tier** (1-3, keyword-driven: "typo/doc" → 1, "architecture/overhaul/swarm" → 3, else 2).
3. **Ambiguity-route:** back in `run_tpm_wake_cycle()`, each triaged item is routed by a simple decision tree — no linked goal → `needs_architect_input`; tier 3 → `needs_pm_priority_input`; else → `tpm_drafted`.
4. **Dispatch:** `run_sweep_pass()` (`tpm_sweep.py:130`) checks `check_authority()` + `evaluate_asimov_invariants()` per ready story, resolves a harness via `_resolve_harness()` (role→policy lookup), then calls `dispatch_agent()`.
5. **Await/consolidate:** a separate loop, `poll_and_process_proposal_comments()` (`tpm_sweep.py:265`) → `process_proposal_comments()` (`tpm_sweep.py:722`), fetches comments on a packaged release-proposal issue and parses a fixed command grammar (`/approve`, `/revise <text>`, `/drop <story-id>`, `/prioritize <story-id>`, `/hold`) to mutate story readiness/priority and resolve the approval ticket. `post_proposal_interim_rollup()` (`tpm_sweep.py:664`) posts progress back to the same issue as each constituent story completes — the consolidation step.

**What this precedent establishes, and what it doesn't:** the full capture→classify→route→dispatch→await→consolidate shape already exists and runs unattended today (gated by `AutonomyLevel` — L1 advisory-only, L2/L3 actually dispatch). What it does *not* do: operate on any capture surface besides GitHub issues, classify against anything richer than a hand-written keyword list, or decompose one intent into multiple dependent activity blocks (`triage_backlog` classifies a whole issue as one story; it does not split one issue into several typed sub-activities). Those three gaps are exactly Pass 2's scope.

## Section B — Activity Set Already in Frequent Use (agenda item 3)

The operative vocabulary today is the `task_type` string threaded through `synlynk/dispatch.py` and routed via CLAUDE.md's Capability-Based Task Allocation table:

```
implement, test, css, templates, content, subpages, canvas, js, infra,
refactor, cli-plumbing, pm, review, deploy, brainstorm, spec, architecture,
forensics, reasoning, fix, feat, build, research, audit
```

Observed characteristics:
- **Flat, not hierarchical** — no grouping by discipline, lifecycle stage, or archetype; `_resolve_harness()`-style routing works only because every one of these strings is hand-mapped to a harness in policy.
- **SWE-specific** — every value describes a software-delivery action; none generalizes to a non-SWE domain (e.g. nothing here describes a video-render, a lab-protocol-compliance-check, or a legal-discovery-review activity).
- **Ungrounded in archetype** — `task_type` values map to harnesses directly, never through the archetype layer `dec-4a53a2ee` already ratified. `implement`/`fix`/`feat`/`build` are all effectively `creator.execute`; `review`/`audit`/`forensics` are all effectively `inspector.verify`; this redundancy is invisible today because nothing enforces the archetype relationship.

This is the list the new taxonomy (Section C) must be able to subsume without breaking existing dispatch routing — each existing `task_type` string needs a non-ambiguous mapping onto the new (stage, discipline, verb) triple, not a parallel system living alongside it.

## Section C — Cross-Industry Activity Taxonomy (agenda items 4-5)

**Decision (made with the user during brainstorming):** the taxonomy is **3-axis**: GOVERNS stage × SFIA discipline × verb. Stage and (discipline+verb) are different axes — stage is lifecycle position, discipline+verb is domain+action — not alternative designs, so all three compose rather than compete.

**The verb axis is new; the other two already exist and are reused unchanged:**
- **GOVERNS stage:** `goal, open, visualize, execute, release, notify, sustain` — already enforced in `state.db`, no change.
- **SFIA discipline + Industry Domain:** already ratified in `dec-4a53a2ee`'s worked tables (Software/SaaS, Film, Video Production, Biopharma), no change.
- **Verb (new):** extracted directly from the 6 archetypes' already-ratified "Capability-Neutral Contract" prose (`dec-4a53a2ee` §2), rather than invented fresh:

| Archetype | Verbs (textually grounded in the ratified contract) |
|---|---|
| orchestrator | `ingest`, `cluster`, `decompose`, `dispatch`, `track` |
| strategist | `set_intent`, `align`, `gate` |
| director | `author`, `structure`, `gate` |
| creator | `receive_brief`, `execute` |
| inspector | `review`, `verify`, `gate` |
| custodian | `maintain`, `sync`, `integrity_check` |

`gate` is one verb, not three — strategist/director/inspector each hold a different *kind* of gate (scope, plan, advance), but the action is structurally identical (a go/no-go checkpoint), so the taxonomy parameterizes `gate` by archetype rather than tripling the verb.

**An activity is the triple `(stage, discipline, verb)`.** Worked examples spanning Section B's existing list and the cross-industry tables:

| Existing/example activity | stage | discipline (SFIA) | verb | archetype |
|---|---|---|---|---|
| `implement` (today's dev task_type) | execute | PROG | execute | creator |
| `fix` / `feat` / `build` (today's task_types) | execute | PROG | execute | creator *(same triple as `implement` — confirms Section B's redundancy finding)* |
| `review` / `audit` / `forensics` (today's task_types) | execute or sustain | TEST | verify | inspector |
| `spec` / `architecture` (today's task_types) | visualize | ARCH | author | director |
| `brainstorm` (today's task_type) | visualize | REQM | set_intent | strategist |
| sound-designer audio mix (Video Production table) | execute | SNDD | execute | creator |
| biostatistician protocol compliance check (Biopharma table) | sustain | DATM | verify | inspector |
| VFX vendor wave assembly (Film table) | execute | PRMG | dispatch | orchestrator |
| workspace hygiene sweep (synlynk's own custodian) | sustain | ITOP | maintain | custodian |

**Why this resolves Section B's redundancy problem:** collapsing `implement`/`fix`/`feat`/`build` onto one triple is not a loss of information — those four strings never carried distinct routing semantics (all four map to the same harness policy entries today); the taxonomy makes that explicit instead of leaving four synonyms live in the dispatch surface.

---

## Deferred (explicitly out of scope for this spec)

- **The intent capture→classification→decomposition→dispatch→consolidation pipeline itself** (agenda item 6) — Pass 2, a separate design spec building on this taxonomy.
- **Migrating existing `task_type` call sites in `dispatch.py` to the new triple** — an implementation task for a future plan, not authorized here.
- **New SFIA discipline codes or new industry-domain worked examples beyond what `dec-4a53a2ee` already has** — this spec reuses that spec's coverage; extending it further is out of scope.
- **Formal schema (JSON/YAML) for an activity record** — Pass 2's concern, once the pipeline that produces/consumes activity records is being designed.

## Validation Criteria

Before Pass 2 depends on this taxonomy: confirm at least 5 more of today's `task_type` strings (beyond the worked examples above) map to exactly one `(stage, discipline, verb)` triple without forcing an awkward fit. If more than one genuinely doesn't fit, the verb list needs revision before Pass 2 builds on it.
