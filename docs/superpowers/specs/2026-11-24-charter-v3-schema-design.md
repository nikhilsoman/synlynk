# Charter v3.0: Unified Workspace Agent Charter Schema

**Status:** Proposed — awaiting user review
**Entry point:** gh:#2809, broadened per Nikhil's 2026-11-24 request to cover Agent Studio / Charter operationalization
**Decision records:** `project-docs/decisions/2026-11-24-decision-needed-canonical-workspace-agen.md`, `project-docs/decisions/2026-11-24-decision-needed-follow-up-validation-rou.md`, `project-docs/decisions/2026-11-24-decision-needed-should-agent-studio-the.md`

## Problem

Workspace Agent charters have forked into three incompatible live shapes, plus one hardcoded artifact that violates existing policy:

1. **v1 flat JSON** — 7 charters (`pm`, `architect`, `designer`, `qa`, `maintainer`, `marketing`, and `dev`'s historical shape), stored under `.synlynk/charters/<role>.json`. No `schema_version` field. Example: `pm.json` — `mandate` + `autonomous_authorities` + `escalation_triggers` + `wake_cycle_sop`, nothing else.
2. **v2.0 SFIA JSON** — 2 charters (`tpm`, `wingman`), introduced 2026-11-15 (`docs/superpowers/specs/2026-11-15-sfia-charter-archetypes-and-wingman-design.md`). Adds `sfia_mapping`, `boundaries`, `coordination_pattern`, `tools`, `credentials`, `evidence_contracts`, `capability_refs`. Never backported to the other 9 roles.
3. **Markdown + frontmatter** — `synlynk/charter_schema.py`'s own validator (`REQUIRED_FRONTMATTER_KEYS`, `REQUIRED_SECTIONS`) expects this shape. **Zero live charter files use it.** The validator checks a format nothing produces.
4. **Rogue artifact:** `synlynk/charters.py` defines a Python-dataclass charter table (`CharterSpec`) with a hardcoded `harness_bindings: List[str]` field per role (e.g. `pm → ["claude", "codex"]`, `dev → ["codex", "agy", "grok"]`). This directly violates the Empirical Capability Assessment Policy (CLAUDE.md, 2026-10-04), which requires harness routing to be decided from measured `capability_ratings`/`cost_entries` via `LiveQueryRouter`, never hardcoded into charter content.

Separately, Nikhil set five long-term product goals any charter design must satisfy, and asked whether Agent Studio/Charter v3 should become a standalone synlynk-ecosystem product. Three `synlynk decide` panels (claude, agy, codex) were run to resolve the open design questions; this spec is their reconciled output.

## Decision: adopt Charter v3.0

A new, versioned schema — not a backport of v1 or v2.0, not Markdown+frontmatter. Combines v1's minimal core with v2.0's structured fields, adds three new blocks the panels judged necessary (`identity`, `coordination`, `constitution_binding`), and is designed to be extraction-ready without being extracted yet.

### Canonical form

- **JSON Schema** is the normative contract — the single source of truth for what a valid charter is.
- **JSON** is the data model used by the API and by Vizor's Agent Studio editor.
- **Strict-subset YAML** is the on-disk authoring syntax for hand-edited charters: no anchors, no custom tags, no implicit type coercion, loaded with a YAML 1.2 core-schema loader (avoids the "Norway problem" — `no`/`off`/etc. parsing as booleans). YAML parses losslessly into the JSON model; there is exactly one data model, two serializations of it.
- Markdown is permitted only as prose *inside* designated fields (e.g. a future `mandate_narrative`), never as the charter's container. The dead `REQUIRED_FRONTMATTER_KEYS`/`REQUIRED_SECTIONS` Markdown-frontmatter validator in `charter_schema.py` is removed as part of this migration (see Migration, below).
- Unknown top-level keys are rejected by the validator. All reserved blocks below exist from v3.0's first release, even empty, so adding real content to them later never forces a major version bump.

### Schema blocks

**Core (from v1 — a hand-authored minimal charter stays ~15 lines):**
- `schema_version` — semver, required (e.g. `"3.0.0"`). This is the field whose absence currently distinguishes "v1" charters from everything else.
- `charter_id` — immutable, assigned once.
- `role` — must be a `KNOWN_ROLES` value (currently `dev, qa, pm, architect, tpm, designer, marketing, synlynk-bot, maintainer, secops, infra-devops, wingman` — `synlynk/charter_schema.py:15-18`).
- `mandate` — free text, carried forward unchanged from every existing charter.
- `authorities` — renamed/normalized from v1's `autonomous_authorities`.
- `escalation` — normalized from v1's `escalation_triggers`.
- `sop` — normalized from v1's `wake_cycle_sop` (a list of ordered, numbered steps, matching the shape every real charter already uses).

**Structure (from v2.0):**
- `sfia_mapping` — unchanged shape (`sfia_code`, `sfia_title`, `sfia_level`, `autonomy_level`, `complexity_ceiling`), per `.synlynk/charters/tpm.json`.
- `boundaries` — unchanged, a list of "never" statements.
- `governance` — a **new grouping block** that gathers v2.0's `tools`, `credentials`, and `evidence_contracts` under one namespace (previously flat top-level fields in the v2.0 shape), so the separately-sequenced tool-use-governance project has a single place to own:
  - `governance.tools[]` — each entry carries `id`, `scope`, `mode` (`allow|ask|deny`), optional rate limits, and `audit` (whether invocations get logged). Note: `tpm.json`'s current `tools` field is a flat list of capability-name strings (`"synlynk:story"`, `"synlynk:dispatch"`, …) — migration normalizes these into `{id: "synlynk:story", scope: ..., mode: "allow", audit: true}` entries; the migration tool (below) must not silently drop the existing bare strings.
  - `governance.credentials[]` — references only, never raw values. `tpm.json`'s current `"github_app:synlynk-tpm"` string becomes an `identity.app_ref` (see `identity` block below) rather than living under `governance.credentials` — credential *references* that aren't the role's own primary identity (e.g. a scoped API key) stay here.
  - `governance.evidence_contracts[]` — unchanged list shape from v2.0.

**`identity` (new — closes a gap in goal 3, "well-defined scope with... identity"):**
- `identity.app_ref` — a typed reference to the role's GitHub App credential record (today: `.synlynk/github_apps/<role>/`). Never holds the credential itself — mirrors the existing `secret_ref`/`credentials` reference-only pattern. This is the principal that `constitution_binding.evidence_ref` audit records (below) get attributed to.

**`coordination` (new — closes a real gap in goal 4, "agents must act in concert"):**
- Replaces v2.0's `coordination_pattern`, which was a single descriptive string (or, in `tpm.json`'s actual shape, a dict of named-stage prose — see `coordination_pattern.intake_and_mining`, `.ambiguity_gate`, etc.). That shape says *what kind* of coordinator a role is; it has no schema-level contract for *who* a role may talk to or *how*.
- `coordination.handoffs[]` — a typed-edge list, modeled on the handoff pattern shared by the OpenAI Agents SDK, LangGraph edges, and A2A:
  - `to_role` — must resolve to a `KNOWN_ROLES` value; validator rejects dangling references.
  - `operation` — one of `delegate | request | notify | escalate`.
  - `trigger` or `condition` — when this edge fires.
  - `input_schema_ref` / `output_schema_ref` — the expected shape at the handoff boundary.
  - `transport` — an abstract enum: `dispatch_job | gh_pr_comment | gh_issue | state_db_table | queue`. Implementation-specific transport config (which queue, which table) lives outside the charter, in the adapter/runtime layer — the charter only declares the transport *kind*.
  - `ack` — optional, whether the edge expects an acknowledgment.
- `peers` is **not stored** — it's a derived view computed from `coordination.handoffs[]` (every role this role hands off to, union every role that hands off to it). Storing it separately would let it drift from the edges that are the actual source of truth.
- The validator checks for dangling `to_role` references and rejects illegal cycles. Vizor's Agent Studio can render `coordination.handoffs[]` directly as a graph.
- Explicit pub/sub topics were considered and rejected for v3.0 — synlynk has no message broker today; `queue` is available as a `transport` value for when one exists, and anything broker-specific can live under `extensions` until then. A stored dependency DAG was also considered and rejected — that's a workflow-execution concern (already partially covered by `state.db`'s story dependency graph), not a charter-authoring concern.
- `tpm.json`'s current prose-dict `coordination_pattern` doesn't map cleanly onto typed edges (it describes *process stages*, not *handoffs*) — migration moves that content into `extensions.synlynk.coordination_pattern_legacy` verbatim rather than lossy-converting it, and a human re-authors it as real `coordination.handoffs[]` entries during charter review (see Migration).

**`constitution_binding` (new — closes a real gap in goal 5; required and structural, not a placeholder):**
The panel explicitly pushed back on an earlier placeholder-only framing of this block, given Nikhil's "strictly adhere... in letter AND spirit" framing. Today, `synlynk/constitution.py` defines 4 laws (`law-0` through `law-3`, each with a `DeliveryTier` of `PROSE | CITED | INJECTED`) but `constitution_gate.py`'s enforcement is only a non-blocking textual citation-tag check (`observe` mode) — no code path ties charter authority to constitutional law today, and no charter schema field references the constitution at all.
- `constitution_binding.tier_acknowledgements[]` — the `DeliveryTier`/law IDs this role operates under.
- `constitution_binding.law_refs[]` — **required** on every `sop` step, every `coordination.handoffs[]` entry, and every high-risk `governance.tools[]` capability (`mode: ask` or `mode: deny` entries at minimum). Each ref cites the specific law ID and tier it implicates.
- `constitution_binding.evidence_ref` — where the audit record for that step/handoff/tool-use lands (the `identity.app_ref` principal is who it's attributed to).
- The schema validator — the same one that today checks `REQUIRED_SECTIONS` — resolves every `law_refs` ID directly against the live `CONSTITUTION_LAWS` dict in `synlynk/constitution.py` (never a hardcoded duplicate enum in the charter validator) and **fails closed** on a missing, unknown, or incomplete binding.
- Explicitly out of scope for this spec: flipping `constitution_gate.py` from `observe` to `enforce` mode. That's a separate policy decision. This block gives that future decision something concrete and structural to check against, rather than requiring a breaking schema change when it's made.

**`requirements` (replaces the rogue `harness_bindings` table):**
- `requirements.task_types[]`, `requirements.capability_requirements[]` — free-form, domain-agnostic strings (this is what keeps the schema industry/domain-agnostic per goal 1 — nothing here names a specific tech stack or vertical).
- `requirements.cost_bounds` / `requirements.latency_bounds` — optional numeric envelopes.
- `requirements.harness_constraints.deny[]` — the **only** field anywhere in the schema permitted to name a specific harness, and only as a hard exclusion (e.g. a compliance rule that forbids a given harness for a given role). It is a constraint, never a preference.
- **`synlynk/charters.py`'s `harness_bindings` field and the hardcoded per-role table (lines ~18, ~40, ~56, etc.) are deleted outright**, not deprecated-in-place. Harness selection for every role resolves only at dispatch time, via `LiveQueryRouter` querying `capability_ratings`/`cost_entries` against `requirements`, per the existing Empirical Capability Assessment Policy. `tpm.json`'s current `capability_refs: ["gh-sync-roadmap"]` field maps into `requirements.capability_requirements`.

**`extensions` (escape hatch):**
- A namespaced map (e.g. `extensions.synlynk.*`, `extensions.<vendor>.*`) that the core validator ignores entirely. This is where anything synlynk-specific that shouldn't leak into a provider-neutral core schema lives (see Standalone-Extraction Constraints, below), and where migration parks content it can't automatically restructure (e.g. `tpm.json`'s legacy `coordination_pattern` prose).

**Provenance:**
- `migration_provenance` — records which legacy shape (v1 / v2.0) a charter was migrated from and when, plus deprecation metadata for the dual-read window.

### Harness assignment (resolved)

Charters declare `requirements`, never bindings. `harness_bindings` is deleted from `synlynk/charters.py`. `LiveQueryRouter` resolves `requirements` against `capability_ratings` and `cost_entries` at dispatch time, per the Empirical Capability Assessment Policy (2026-10-04). The only harness-named field a charter may carry is `requirements.harness_constraints.deny[]` — a hard exclusion, not a routing preference, and policy (not the charter) owns the actual routing decision.

### Standalone-extraction constraints (fold in now, don't retrofit later)

Charter v3.0 is being designed **extraction-ready but is not being extracted, packaged, published, or monetized now.** The third decide panel was explicit: a schema alone isn't a competitive product (Tier-1 LLM-orchestrator vendors already ship comparable governance primitives), and the real moat — per-role identity + empirically-driven routing + cross-harness review, actually running — doesn't exist yet (today, only `tpm` has a working autonomy grant + wake-cycle; 2 of 11 roles have zero charter at all). Standalone packaging is explicitly deferred until two milestones are met: **≥5 roles operating end-to-end** (charter, identity binding, autonomy + wake-cycle, review enforcement, audited outcomes), and **≥5 merged jobs per harness on the main task types** (so any routing/capability claim rests on measurement, not assertion — this already is the sample-size bar the Empirical Capability Assessment Policy sets).

That said, three concrete constraints get folded into this spec now, because retrofitting them later is expensive and they cost little today:

1. **Zero synlynk-package imports in the schema core.** The JSON Schema, its validator, the migration engine, and conformance test fixtures live in their own module (not scattered across `synlynk/charters.py`/`charter_schema.py`/`charter_injection.py` as today). The JSON Schema file is the source of truth; the Python validator is thin/generated from it, not hand-maintained logic that can drift from the schema. CI gets an import-lint check enforcing this boundary. All synlynk-specific behavior (dispatch wiring, GitHub App resolution, `state.db` reads) lives in an adapter layer that imports the core module, never the reverse.
2. **Provider-neutral references.** `identity.app_ref`, `governance.credentials[]` refs, and any future `tool_ref`-style field are typed URIs (`github-app:<role>`, `env:<name>`, `vault:<path>`), not GitHub-App-specific fields. The schema names no provider; GitHub App is one resolver implementation behind the `identity_ref`/`secret_ref` indirection, not baked into the schema itself.
3. **Declarative intent, separate from runtime.** `sop`, `coordination.handoffs[]`, and autonomy/wake-cycle content (future `lifecycle` block — reserved, not yet populated, see Follow-ons below) describe *what* should happen, declaratively, never *how* a specific runtime executes it. Harness and tool vocabularies stay open-ended, extended via namespaced `extensions.<vendor>.*` rather than enums baked into the core schema. Evidence (capability scores, audit events, enforcement decisions) sits behind a portable interface; synlynk's own `capability_ratings`/`cost_entries`/`state.db` tables are *one* backend for that interface, not the interface itself.

### Migration

1. Write a deterministic `synlynk charter migrate` command. It lifts the 7 v1 charters (`pm`, `architect`, `designer`, `qa`, `maintainer`, `marketing`, and `dev`'s current shape) and the 2 v2.0 charters (`tpm`, `wingman`) into v3.0, with every new reserved block (`identity`, `coordination`, `constitution_binding`, `requirements`, `extensions`) present but empty-but-valid except where source data maps directly (e.g. `tpm.json`'s `credentials: ["github_app:synlynk-tpm"]` → `identity.app_ref`, `capability_refs` → `requirements.capability_requirements`). Content that doesn't map cleanly (e.g. `tpm.json`'s prose-dict `coordination_pattern`) is parked verbatim under `extensions.synlynk.*`, never silently dropped.
2. Round-trip tests assert that v1 charter *content* survives migration exactly — the migration changes structure, not meaning.
3. Each migrated charter gets explicit human review before write-back — in particular, `tpm`'s legacy `coordination_pattern` content needs a human to actually re-author it as `coordination.handoffs[]` entries; migration only parks it in `extensions`, it does not auto-convert it.
4. The charter loader dual-reads v1, v2.0, and v3.0 through an adapter for one bounded release window, emitting deprecation warnings on every legacy read. After that window: legacy loading paths, `synlynk/charters.py`'s `harness_bindings` table, and the dead Markdown-frontmatter validator (`REQUIRED_FRONTMATTER_KEYS`/`REQUIRED_SECTIONS` in `charter_schema.py`) are all deleted.
5. Vizor's Agent Studio charter editor (epic #5185, phase 1 shipped) is regenerated from the published JSON Schema rather than hand-bound to today's field set — this is what makes "fully configurable via Agent Studio" (goal 2) actually hold as the schema grows, instead of the editor permanently lagging the schema the way it does today. The editor ships one adapter release that reads old versions and writes v3.0, with server-side validation. Backend and editor release together, gated on a `schema_version` check. The editor must support create/edit/validate/diff/revision-history for every v3.0 block, including the new `governance`/`identity`/`coordination`/`constitution_binding`/`requirements` blocks — not just the subset the current editor covers.

### Explicitly out of scope / follow-ons (already-sequenced, not re-litigated here)

- **`lifecycle` block** (`wake_cycle_sop`, `autonomy` posture, `registration_state`) — reserved space only. The 4-layer role-lifecycle alignment project (registration / GitHub identity / autonomy grant / daemon wake-cycle wiring) is a separately-sequenced sub-project; this spec only guarantees the schema has a stable home for it when that project lands, so it doesn't force another schema version bump.
- **Tool-use governance enforcement** — `governance.tools[]`'s `scope`/`mode`/`audit` fields exist in this schema, but wiring real code consumers for them (today, 3 non-communicating mechanisms — `_ROLE_PERMISSION_DEFAULTS`, `policy.json`'s `permission_profiles`, and the charter's own dead `tools:` field — exist and don't talk to each other) is its own sequenced project.
- **`constitution_gate.py` observe→enforce flip** — `constitution_binding` gives this a structural home; actually flipping enforcement is a separate policy decision.
- **Standalone packaging/publishing/monetization** — explicitly deferred behind the two milestones stated above. If/when those are met, the panel's recommendation is that the standalone offering would be the enforcement-and-evidence layer (a conformance suite, an open versioned schema spec/RFC, and eventually the Capability Registry, gh:#5229) — not the schema alone.

## Testing / validation approach

- JSON Schema conformance tests: every real charter (post-migration) validates against the published schema; every known-invalid fixture (missing `law_refs`, dangling `coordination.handoffs[].to_role`, unknown top-level key) fails validation with a specific error.
- Round-trip tests: v1/v2.0 → v3.0 migration preserves all source content (nothing silently dropped — verified by diffing migrated-charter content against source, field by field).
- `requirements` resolution test: a charter with only `requirements` (no `harness_bindings`-equivalent) successfully resolves to a harness via `LiveQueryRouter` against seeded `capability_ratings` fixtures.
- Import-lint test (standalone-extraction constraint #1): CI fails if the core schema/validator module imports anything from the rest of the `synlynk` package.

## GOVERNS linkage

Per the Brainstorm-First and Multi-Task Series Tracking policies, this spec needs a GOVERNS goal and (given the scope — this is one of four sub-projects under the broader Agent Studio initiative entry-pointed at gh:#2809) should be linked under a parent tracking issue before stories are generated from the implementation plan. Not yet created — flagged here as the first action once this spec is approved, before invoking `writing-plans`.
