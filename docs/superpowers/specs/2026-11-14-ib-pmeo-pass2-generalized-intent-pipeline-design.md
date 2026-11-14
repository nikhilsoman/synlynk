# IB-PMEO Pass 2: Generalized Intent Pipeline (Capture → Classify → Decompose → Dispatch → Await → Consolidate)

**Date:** 2026-11-14
**Status:** Draft — Pass 2 of 2 (research/design only, no implementation authorized)
**GOVERNS linkage:** `goal-18372f86` ← `story-7fd63985`. Tracked under epic #5258.
**Roadmap entry:** Second of two specs resolving the IB-PMEO functional-protocol research kicked off under #5258. Builds on Pass 1's taxonomy (`docs/superpowers/specs/2026-11-14-ib-pmeo-activity-taxonomy-and-archetype-classification-design.md`) to design the pipeline itself (agenda item 6).

---

## Context

Pass 1 answered "what is an activity" — the `(stage, discipline, verb)` triple, grounded in the 6 ratified archetypes' Capability-Neutral Contracts and the existing GOVERNS stage/SFIA discipline axes. Pass 2 answers "how does a raw intent become a tree of dispatched, awaited, and consolidated activities" — the generalized version of the capture→classify→route→dispatch→await→consolidate shape Pass 1 Section A found already running, narrowly, inside `run_tpm_wake_cycle()`.

**Cross-industry grounding:** this spec was deliberately validated against a light recon of three real, non-synlynk-engineering codebases the user operates, to confirm the design generalizes rather than re-deriving synlynk's own SWE dispatch shape under a new name:

- **Hitchcock** (`~/dev/hitchcock`) — multi-role (DIRECTOR/CINEMATOGRAPHER/SOUND_DESIGNER/PRODUCER/VIEWER) generative film pipeline. Every stage is reachable via a discrete CLI verb (`hitchcock produce`, `collab invite`, `ckb query`, etc.) — activities map directly to shell-outable commands.
- **cc-videoreframing** (`~/dev/cc-videoreframing`) — a fully automated 9-stage batch video-reframing pipeline with zero human roles, one CLI entrypoint (`reframe.py`).
- **rxcc** (`~/dev/rxcc`) — a patient-EMR aggregation product: `apps/` (admin, api, web, worker) + `packages/` (ocr-eval, fhir, lexicon, loinc, vocab, whatsapp, ...), all TypeScript, no CLI surface at all. An activity here can only be reached through rxcc's own deployed API, not an in-process function call or a shell command — this spec treats that as a hard constraint, not a simplification.

These three targets differ sharply in role structure and in what a "callable unit" even looks like, which is exactly the variation the pipeline's executor abstraction (Section 2) must absorb without three different pipeline implementations.

**Prior art this spec builds on without re-deriving:**

- Pass 1 (`2026-11-14-ib-pmeo-activity-taxonomy-and-archetype-classification-design.md`) — the `(stage, discipline, verb)` taxonomy and its mapping of today's `task_type` vocabulary.
- `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md` — the approved Intent Capture Layer. This spec's Stage 1 (Capture & Normalize) delegates to it rather than re-specifying intent ingestion.
- `synlynk/tpm_sweep.py`'s `run_tpm_wake_cycle()` — the existing, narrower, production instance of this same pipeline shape (GitHub issues only, flat classification, no recursive decomposition).

---

## Section 1 — Core Decision: Build Target

**Decision (made with the user during brainstorming):** Pass 2 is built as a **new standalone module** (`synlynk/intent_pipeline.py`), with no dependency on or modification to `tpm_sweep.py`. `tpm_sweep.py` keeps running unmodified on its existing mechanism; migrating it onto this new pipeline is a separate, later, optional task. This avoids risking the one capture→dispatch mechanism that already runs unattended in production, in exchange for maintaining two systems until that migration happens.

## Section 2 — Data Structures

```
Intent:
  id
  source                   # github_issue | cli | api | ... (per the approved Intent Capture Layer)
  raw_payload
  expected_output_format   # e.g. "github_comment", "json_report", "cli_stdout"
  governs_link              # goal/story id — required, no ungoverned intents

Activity:
  id
  parent_id                # nullable; nullable only at the tree root
  triple                   # (stage, discipline, verb) — Pass 1's taxonomy
  archetype                # derived from verb per Pass 1's archetype->verb table
  payload                  # activity-specific arguments
  status                   # pending | decomposed | dispatched | awaiting | complete | failed

ExecutorRegistry:          # (stage, discipline, verb) -> ExecutorEntry
  ExecutorEntry:
    executor_kind          # shell_cli | http_api | saas_platform | ...  (open, registry-extensible — not a closed enum)
    invocation_spec        # kind-specific: command template | endpoint+auth | platform action id
    await_spec             # exit_code | poll_url | webhook_event

FoldRegistry:              # (discipline, verb) -> FoldStrategy
  FoldStrategy:
    kind                   # data_aggregation | content_assembly | status_rollup | ...  (open, registry-extensible)
    reduce_fn               # (parent_activity, [child_results]) -> parent_result
    failure_mode           # fail_fast | partial_result_with_flag  (default: fail_fast)
```

**Why `executor_kind` and `FoldStrategy.kind` are open registries, not closed enums:** the underlying claim validated with the user is that essentially all business activity ultimately routes through some software-accessible surface — a CLI, an internal API, or a third-party SaaS platform's own API — so a new target (a new SaaS platform, a new internal package) registers a new executor kind rather than requiring a schema change. The same openness applies to fold strategies: how child results combine into a parent result is itself domain-dependent (a data-aggregation activity's children fold by numeric/structural merge; a content-production activity's children fold by narrative/sequential assembly), so `FoldStrategy` is resolved by lookup, not hard-coded once.

## Section 3 — Pipeline Stages

1. **Capture & normalize** — `capture_intent(raw) -> Intent`. Delegates entirely to the approved Intent Capture Layer; this spec adds nothing here beyond requiring `expected_output_format` and `governs_link` to be present on the resulting `Intent`.
2. **Classify & route** — `classify_activity(intent_or_subintent) -> Activity`. Extends `_classify_role_and_stage()`'s existing keyword/label-matching pattern to emit a full `(stage, discipline, verb)` triple per Pass 1's taxonomy, rather than today's role+stage+tier.
3. **Recursive decomposition** — `decompose(activity)`. **Leaf rule (decided with the user): an activity is a leaf the moment its triple resolves to an entry in `ExecutorRegistry`.** If no entry exists, a registered `decompose_fn` (keyed the same way, by triple or by archetype) splits it into narrower child `Activity` records, each of which re-enters this same check. This mirrors `dispatch_agent()`'s existing harness-resolution-by-policy-lookup pattern — decomposition terminates by registry lookup, not by a depth limit or a hand-coded heuristic.
4. **Mapping / dispatch construction** — `construct_dispatch(leaf) -> DispatchSpec`, built purely from the matching `ExecutorEntry`. The construction logic itself is executor-kind-agnostic; it just hands the entry's `invocation_spec` to whichever executor implementation registered that kind.
5. **Await** — `await_result(dispatch)`, polling/waiting per the entry's `await_spec` (process exit code, poll endpoint, or webhook event), feeding the resulting `ActivityResult` back onto the `Activity` node.
6. **Consolidation** — `consolidate(tree)`. **Bottom-up fold through the decomposition tree (decided with the user): each non-leaf node's children are consolidated first; the node then resolves its own `FoldStrategy` from `FoldRegistry` by its `(discipline, verb)` and applies `reduce_fn` to its children's results.** This recurses to the root, where the final fold's output is checked against the originating `Intent.expected_output_format`.

## Section 4 — Error Handling

Two gap cases, both deliberately reusing Section A's existing ambiguity-route vocabulary rather than inventing new states:

1. **No executor and no decomposer.** A composite activity has no `ExecutorRegistry` entry *and* no registered `decompose_fn` for its triple/archetype. This escalates as `needs_architect_input` — structurally identical to today's "no linked goal" ambiguity route in `run_tpm_wake_cycle()`.
2. **Leaf dispatch failure.** A leaf's `await_result` reports failure. Propagation is governed by the parent's `FoldStrategy.failure_mode`: `fail_fast` (default) aborts the whole subtree's consolidation and propagates failure upward; `partial_result_with_flag` folds whatever sibling results succeeded and flags the gap explicitly in the consolidated result rather than silently omitting it.

## Section 5 — Testing / Validation

- **Unit level:** each registry lookup (`ExecutorRegistry`, `FoldRegistry`, `decompose_fn` resolution) is tested in isolation against known triples.
- **End-to-end dry run:** uses one real `shell_cli` executor entry against Hitchcock's or cc-videoreframing's actual CLI (both already expose one) — this is the cross-industry, non-synlynk-engineering proof this pass was scoped to produce. rxcc's `http_api`-shaped executor and any `saas_platform`-shaped executor are explicitly **not** built in this pass (Deferred, below) — the dry run validates the executor abstraction holds, not that every target is wired up.
- **Backward-compatibility:** confirm today's `task_type` strings still resolve through `classify_activity` to the same triples Pass 1's own Validation Criteria already checked — this spec reuses that check rather than re-deriving it.

---

## Deferred (explicitly out of scope for this spec)

- **Populating `ExecutorRegistry`/`FoldRegistry` beyond the 1–2 worked examples needed for the end-to-end dry run.** Real coverage (rxcc's `http_api` shape, any `saas_platform` entry such as Atlassian/Stripe, Hitchcock's and cc-videoreframing's full command surfaces) is a future implementation task, not authorized here.
- **Migrating `tpm_sweep.py` onto this pipeline** (Section 1) — a separate, later, optional task.
- **Intent capture surfaces beyond what the already-approved Intent Capture Layer supports.**
- **Formal persistence/schema for `Activity` trees in `state.db`** — this spec defines the in-memory shape; durable storage is an implementation-plan concern.
- **The full "what synlynk can build/manage/operate to revenue" audit of Hitchcock/rxcc/cc-videoreframing** and any autonomous-future roadmap per project — explicitly deferred by the user to a separate, later epic/brainstorm. This spec's recon of those three repos is scoped only to extracting pipeline/role/tool-surface shape for this design's validation, not a business audit.

## Validation Criteria

Before any implementation plan is written against this design: run the Section 5 end-to-end dry run against at least one real Hitchcock or cc-videoreframing CLI command through a hand-registered `ExecutorEntry`, and confirm the resulting `ActivityResult` folds to a correct consolidated output with no pipeline code specific to that CLI's shape (i.e., the same pipeline code would work unchanged if pointed at a different `shell_cli`-kind target).
