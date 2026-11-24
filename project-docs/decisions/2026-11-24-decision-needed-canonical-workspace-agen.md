<!-- generated - source of truth is state.db -->
---
decision_id: dec-e7aca9bf
topic: "DECISION NEEDED: Canonical Workspace Agent Charter schema design, as a load-bearing foundation Nikhil wants designed right ONCE and lived with long-term — this is intended to be synlynk's core differentiator and potentially a standalone Agent Builder product competing with CrewAI, AutoGen/AG2, LangGraph, OpenAI Agents SDK, Google ADK/Vertex Agent Builder, and AWS Bedrock Agents.\n\nCURRENT STATE (confirmed by code audit, gh:#2809 entry point): charters have forked into THREE incompatible live schema shapes simultaneously: (1) v1 flat JSON — 7 charters (pm, architect, dev, designer, qa, maintainer, marketing), no schema_version field, simple mandate+authorities+escalation+SOP; (2) v2.0 SFIA JSON — 2 charters only (tpm, wingman, added 2026-11-15), adds sfia_mapping, boundaries, coordination_pattern, tools, credentials, evidence_contracts — never backported to the other 9 roles; (3) Markdown+frontmatter — charter_schema.py's OWN validator (REQUIRED_FRONTMATTER_KEYS, REQUIRED_SECTIONS) expects this shape, but ZERO live charter files use it — the validator checks against a format nothing actually uses. There is also a 4th rogue artifact: charters.py has a hardcoded harness_bindings table (pm->claude/codex, dev->codex/agy/grok, etc.) assigning harnesses per role in code — this directly violates the repo's own Empirical Capability Assessment Policy (2026-10-04), which mandates harness routing be decided from measured capability_ratings/cost_entries data, never hardcoded into charter content.\n\nDOWNSTREAM FACTS the schema must support: tools/credentials fields exist in the v2.0 schema but are EMPTY [] on all 16 real charter instances with ZERO code consumers — tool-use governance (a separate, already-sequenced follow-on project) will need to read real data out of whatever field this schema settles on. Separately, role lifecycle has 4 independent gates (registration, GitHub identity, autonomy grant, daemon wake-cycle wiring) that are not charter-schema problems per se but the charter is the artifact that should eventually declare a role's wake_cycle_sop and autonomy posture, so the schema needs a stable place for that. Vizor's Agent Studio charter editor (epic #5185, shipped phase 1) already has a live UI bound to whatever JSON shape is canonical today — a schema change requires a coordinated editor migration, not just a backend change.\n\nTHREE CANDIDATE DIRECTIONS on the table:\nA) Extend the v2.0 SFIA JSON shape to all 11 roles (newest, most structured, already has tools/credentials/evidence_contracts fields, but only 2/11 roles use it today — heaviest migration of the other 9).\nB) Adopt Markdown+frontmatter (the shape the existing validator already expects nothing currently uses) — human-readable/diffable prose, but means building out REQUIRED_SECTIONS content for all 11 roles from scratch and losing JSON's structured-field ergonomics for tools/credentials/evidence_contracts unless frontmatter carries those as structured sub-blocks.\nC) Design a new unified schema from scratch, informed by all three existing shapes (keep v1's simplicity, keep v2.0's SFIA/tools/credentials/evidence_contracts structure, drop the markdown-frontmatter format as dead weight since nothing uses it) — highest short-term design cost, cleanest long-term artifact, no technical-debt inheritance.\n\nGiven the long-term/differentiator/standalone-product framing, give your recommendation among A/B/C (or a hybrid), AND address: (1) should the schema be JSON, YAML, Markdown+frontmatter, or something else entirely for a product that external users would eventually author charters in by hand; (2) how should harness assignment be represented going forward given hardcoded harness_bindings must be removed; (3) what must the schema reserve space for now so the already-sequenced tool-use-governance and lifecycle-alignment follow-on projects aren't blocked later; (4) migration strategy for the 9 non-migrated charters and the Vizor charter editor."
date: 2026-11-24
panel: [claude, agy, codex]
status: approved
---

## Topic
DECISION NEEDED: Canonical Workspace Agent Charter schema design, as a load-bearing foundation Nikhil wants designed right ONCE and lived with long-term — this is intended to be synlynk's core differentiator and potentially a standalone Agent Builder product competing with CrewAI, AutoGen/AG2, LangGraph, OpenAI Agents SDK, Google ADK/Vertex Agent Builder, and AWS Bedrock Agents.\n\nCURRENT STATE (confirmed by code audit, gh:#2809 entry point): charters have forked into THREE incompatible live schema shapes simultaneously: (1) v1 flat JSON — 7 charters (pm, architect, dev, designer, qa, maintainer, marketing), no schema_version field, simple mandate+authorities+escalation+SOP; (2) v2.0 SFIA JSON — 2 charters only (tpm, wingman, added 2026-11-15), adds sfia_mapping, boundaries, coordination_pattern, tools, credentials, evidence_contracts — never backported to the other 9 roles; (3) Markdown+frontmatter — charter_schema.py's OWN validator (REQUIRED_FRONTMATTER_KEYS, REQUIRED_SECTIONS) expects this shape, but ZERO live charter files use it — the validator checks against a format nothing actually uses. There is also a 4th rogue artifact: charters.py has a hardcoded harness_bindings table (pm->claude/codex, dev->codex/agy/grok, etc.) assigning harnesses per role in code — this directly violates the repo's own Empirical Capability Assessment Policy (2026-10-04), which mandates harness routing be decided from measured capability_ratings/cost_entries data, never hardcoded into charter content.\n\nDOWNSTREAM FACTS the schema must support: tools/credentials fields exist in the v2.0 schema but are EMPTY [] on all 16 real charter instances with ZERO code consumers — tool-use governance (a separate, already-sequenced follow-on project) will need to read real data out of whatever field this schema settles on. Separately, role lifecycle has 4 independent gates (registration, GitHub identity, autonomy grant, daemon wake-cycle wiring) that are not charter-schema problems per se but the charter is the artifact that should eventually declare a role's wake_cycle_sop and autonomy posture, so the schema needs a stable place for that. Vizor's Agent Studio charter editor (epic #5185, shipped phase 1) already has a live UI bound to whatever JSON shape is canonical today — a schema change requires a coordinated editor migration, not just a backend change.\n\nTHREE CANDIDATE DIRECTIONS on the table:\nA) Extend the v2.0 SFIA JSON shape to all 11 roles (newest, most structured, already has tools/credentials/evidence_contracts fields, but only 2/11 roles use it today — heaviest migration of the other 9).\nB) Adopt Markdown+frontmatter (the shape the existing validator already expects nothing currently uses) — human-readable/diffable prose, but means building out REQUIRED_SECTIONS content for all 11 roles from scratch and losing JSON's structured-field ergonomics for tools/credentials/evidence_contracts unless frontmatter carries those as structured sub-blocks.\nC) Design a new unified schema from scratch, informed by all three existing shapes (keep v1's simplicity, keep v2.0's SFIA/tools/credentials/evidence_contracts structure, drop the markdown-frontmatter format as dead weight since nothing uses it) — highest short-term design cost, cleanest long-term artifact, no technical-debt inheritance.\n\nGiven the long-term/differentiator/standalone-product framing, give your recommendation among A/B/C (or a hybrid), AND address: (1) should the schema be JSON, YAML, Markdown+frontmatter, or something else entirely for a product that external users would eventually author charters in by hand; (2) how should harness assignment be represented going forward given hardcoded harness_bindings must be removed; (3) what must the schema reserve space for now so the already-sequenced tool-use-governance and lifecycle-alignment follow-on projects aren't blocked later; (4) migration strategy for the 9 non-migrated charters and the Vizor charter editor.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Recommendation: C, built on A's structure, with a strict-subset YAML authoring format.**

**Position on direction.** A inherits v2.0's SFIA-specific shape. That's a reasonable starting point, but it hasn't been exercised: it's used by 2 of 11 roles, and its tools and credentials fields are empty with no consumers. B optimizes for a format nothing uses. C is the honest choice. Take v2.0's structure as the skeleton, keep v1's brevity as the minimum valid charter, and drop the markdown validator. The migration cost is modest, since v1 is a strict subset of v2.0 in intent.

**(1) Format.** Author in YAML, with JSON Schema as the normative definition. YAML supports comments and multi-line prose, so it works for hand-authoring and diffs well. JSON is the canonical machine form, and the Vizor editor and API keep exchanging JSON. YAML parses to the same data model. Allow a long-form `charter.md` body only as an optional prose field, `mandate_narrative`. Don't make frontmatter the container. That is how you avoid B's worst trade-off while keeping readable prose. CrewAI, ADK and Bedrock agent definitions are all YAML or JSON, so this matches what external users expect.

**(2) Harness assignment.** Remove it from the charter entirely. A charter declares requirements, not bindings. Use `capability_requirements: [long_context, gh_write, ...]` and `task_types: [review, implement]`. Routing resolves those requirements against `capability_ratings` and `cost_entries` at dispatch time. An optional `harness_constraints: {deny: [...]}` field covers hard exclusions, such as a compliance rule. It is a constraint, not a preference. Delete `harness_bindings` in code.

**(3) Reserved space now.**
- `tools`: an object list with `id`, `scope`, `mode` (allow/ask/deny), `rate_limits` and `audit`.
- `credentials`: references only (`secret_ref`, `identity_ref`), never values.
- `evidence_contracts`.
- `lifecycle`: `wake_cycle_sop`, `autonomy` (level, grant_ref) and `registration_state`.
- `extensions`: a namespaced map the validator ignores. Unknown top-level keys are rejected.
- `schema_version`, required and semver. Include the other reserved fields from day one, even if empty. This avoids a major bump later.

**(4) Migration.** Write a deterministic `charter migrate` that lifts v1 and v2.0 into the new shape. Round-trip tests should confirm that the 9 v1 charters change only structurally. The loader accepts the old versions through an adapter for one release and emits a deprecation warning. For Vizor, ship the editor against the schema's JSON Schema, so form fields are generated from it rather than hand-bound. Then the editor needs one adapter release rather than a rewrite. Backend and editor release together, behind the `schema_version` check.

**Final position:** Go with C. The schema is JSON Schema-defined and authored in YAML. It follows v2.0's structure and v1's minimal core, has no harness bindings and reserves tools, credentials, lifecycle and extensions now. Migration is automated with an adapter window and a schema-driven Vizor editor.

### agy
[model=default; version=1.5.15]

**Last completed task:** Housekeeping devlog & cost-log for PR #5460 (`#5461`).  
**Next task from `todo.md`:** Isolated generated story (`story-de2f3459`).

---

### Panel Analysis & Recommendation: Direction C (Unified Canonical Specification)

1. **Format — YAML backed by JSON Schema:** For an enterprise Agent Builder competing against CrewAI, LangGraph, and Vertex/Bedrock, **YAML** (backed by strict Pydantic/JSON Schema validation) is the industry standard. Markdown+frontmatter is too brittle for deeply nested evidence contracts and security scopes. Raw JSON lacks human authoring ergonomics (no comments, strict punctuation). YAML bridges both worlds: clean, diffable human git-authoring with 1:1 lossless JSON serialization for programmatic consumers and UI editors. Purge the dead markdown validator.

2. **Harness Decoupling:** Static `harness_bindings` must be excised completely from the charter schema. A charter defines **role requirements and capability boundaries** (e.g., `required_competencies`, `task_types`, `quality_floor`), not execution backends. Execution assignment belongs exclusively to runtime dispatch (`LiveQueryRouter`), dynamically evaluating measured `capability_ratings` and `cost_entries` to uphold the 2026-10-04 Empirical Capability Assessment Policy.

3. **Reserved Downstream Namespaces:** The schema must immediately lock in two forward-compatible, typed blocks:
   - `governance`: Houses `tools: []`, `credentials: []`, and `evidence_contracts: []` for the pending tool-use governance project.
   - `lifecycle`: Houses `autonomy_posture` (e.g., `interactive | supervised | autonomous`), `wake_cycle_sop`, and gate statuses (registration, GitHub identity, autonomy grant, daemon wiring).

4. **Migration Strategy:**
   - **Charters:** Build an automated codemod (`synlynk charter migrate`) that lifts the 7 v1 and 2 v2 charters into canonical YAML, injecting default SFIA ratings and baseline governance/lifecycle stubs.
   - **Vizor Agent Studio:** Because YAML maps losslessly to JSON, serve the new canonical schema via a versioned API adapter (`schema_version: "3.0"`). Vizor's Phase 1 form-bound JSON editor consumes and writes the JSON representation directly, allowing the UI to remain functional while unlocking YAML for CLI/git workflows.

**Final Position:** I recommend **Direction C using a YAML canonical schema**. Unifying SFIA rigor, explicit governance stubs, and lifecycle definitions into a clean schema—while stripping hardcoded harness bindings in favor of dynamic empirical routing—delivers the hardened, debt-free foundation required for a standalone product competing with Google ADK, CrewAI, and OpenAI Agents SDK.

### codex
[model=default; version=codex-cli 0.169.1]

Use option C: define a new, versioned, data-first Charter v3 informed by v1 and v2. Treat the current Markdown/frontmatter validator as dead experimental infrastructure, not the product’s foundation.

The canonical persisted representation should be JSON validated by a published JSON Schema. JSON gives unambiguous machine contracts, robust migrations, API compatibility, and clean editor integration. For humans, offer YAML as an import/export and hand-authoring syntax, parsed into the exact same JSON model; Vizor should provide structured forms plus a prose editor. Markdown belongs in explicit rich-text fields such as `instructions` and `operating_guidance`, not as the schema container.

V3 should retain v1’s directness (`mandate`, authorities, escalation) and v2’s structured concepts (SFIA, boundaries, tools, credential requirements, evidence). Reserve typed fields now for:

- `autonomy`: level, scoped permissions, approval gates, and prohibited actions.
- `lifecycle`: durability, activation state, identity requirements, wake triggers/schedule, wake-cycle SOP, and operational dependencies.
- `tool_access` and `credential_requirements`: stable tool identifiers, scopes, grant references, and audit/evidence requirements—never secrets.
- `verification`/`evidence_contracts`, `coordination`, and `policy_refs`.
- Schema metadata: `schema_version`, immutable charter ID, migration provenance, compatibility/deprecation metadata.

Harness assignment must leave charters. A charter may declare capability requirements and constraints—e.g., “requires browser automation,” “independent reviewer,” cost/latency bounds—but never preferred providers. The live router should select eligible harnesses from measured capability and cost data, while policy governs hard exclusions. This removes the invalid `harness_bindings` coupling without making roles less expressive.

Migrate through versioned adapters: inventory and transform all nine v1 records into reviewed V3 drafts, map v2 losslessly, dual-read during a bounded compatibility window, then remove legacy loading and the Markdown-only validator. Ship Vizor with V3 editing, import/preview migration, server-side schema validation, and explicit per-charter human approval before write-back.

My position: choose C, implemented as a JSON-Schema-defined V3 with YAML ergonomics and Markdown only for narrative content. It is the only option that avoids enshrining today’s accidental split as the future Agent Builder contract.

## Synthesis
The three panelists agree on C. They differ on three points, which I resolve below.

## Where the panel differed

- **Canonical form.** Claude and Codex want JSON Schema as the normative definition, with JSON as the machine form. Agy wants YAML to be canonical.
  - Resolution: JSON Schema defines the contract and the data model is JSON. YAML is the on-disk authoring syntax and parses losslessly to that model. Vizor and the API exchange JSON.
  - YAML is restricted to a strict subset: no anchors, no custom tags, no implicit type coercion, with a YAML 1.2 core schema loader. That avoids YAML's known problems, such as the Norway problem.
- **Where governance fields live.** Agy proposes a `governance` block, Claude uses flat top-level fields, and Codex uses `tool_access` and `credential_requirements`.
  - Resolution: keep v2.0's field names (`tools`, `credentials`, `evidence_contracts`) and group them under one `governance` block. That keeps migration of the 2 v2.0 charters trivial and gives tool-use governance a single namespace to own.
- **Markdown.** All three panelists reject it as the container.
  - Resolution: allow it only as prose inside designated fields (`mandate_narrative`, `operating_guidance`).

## The schema (Charter v3)

- **Core, from v1.** `schema_version` (semver, required), an immutable `charter_id`, `mandate`, `authorities`, `escalation` and `sop`. This is also the minimum valid charter, so a hand-authored charter can be about 15 lines.
- **Structure, from v2.0.** `sfia_mapping`, `boundaries`, `coordination_pattern`, and `governance: {tools, credentials, evidence_contracts}`.
  - Tool entries carry `id`, `scope`, `mode` (allow/ask/deny), rate limits and audit.
  - Credentials are references only (`secret_ref`, `identity_ref`), never values.
- **`lifecycle`, reserved now.** `wake_cycle_sop`, `autonomy` (level, scoped permissions, approval gates, `grant_ref`) and `registration_state`.
  - The four role-lifecycle gates are recorded here as status, not owned by the charter.
- **`requirements`.** `task_types`, `capability_requirements`, cost and latency bounds, and an optional `harness_constraints.deny` for hard exclusions such as compliance rules.
- **Extensibility.** A namespaced `extensions` map the validator ignores. Unknown top-level keys are rejected. All reserved blocks exist from day one, even when empty, so adding them later never forces a major version bump.
- **Provenance.** `migration_provenance` and deprecation metadata.

## Harness assignment

Charters declare requirements, never bindings. `harness_bindings` is deleted from `charters.py`. `LiveQueryRouter` resolves `requirements` against `capability_ratings` and `cost_entries` at dispatch time, per the 2026-10-04 Empirical Capability Assessment Policy. The only harness-named field a charter may carry is a hard `deny` constraint. It is a constraint, not a preference, and policy owns it.

## Migration

1. Write a deterministic `synlynk charter migrate`. It lifts the 7 v1 and 2 v2.0 charters into v3 with empty-but-valid reserved blocks. Round-trip tests assert that v1 charters change only structurally and that no v1 content is lost.
2. Each migrated v1 charter gets explicit human review before write-back.
3. The loader dual-reads v1, v2.0 and v3 through an adapter for one bounded release window, emitting deprecation warnings. After that window, legacy loading and the Markdown-only validator in `charter_schema.py` are removed.
4. Vizor Agent Studio's editor is regenerated from the published JSON Schema rather than hand-bound. It ships one adapter release that reads old versions and writes v3, with server-side validation. Backend and editor release together, gated on the `schema_version` check.

**Decision:** Adopt Direction C: a new, versioned Charter v3 whose normative contract is a published JSON Schema over a JSON data model. Charters are authored on disk as strict-subset YAML, and Vizor and the API exchange JSON. It combines v1's minimal core with v2.0's SFIA, boundaries and coordination structure. It reserves `governance` (tools, credentials, evidence_contracts), `lifecycle` (wake_cycle_sop, autonomy, registration_state), `requirements` and a namespaced `extensions` map from day one. Hardcoded `harness_bindings` is deleted, and harness selection is resolved only at dispatch time from measured `capability_ratings` and `cost_entries`. The 9 non-v2.0 charters move through an automated, human-reviewed `charter migrate` with a one-release dual-read window. Vizor's editor becomes schema-driven, and the dead Markdown validator is removed. Next step: per the Brainstorm-First policy, this goes into a committed spec under `docs/superpowers/specs/`, with a GOVERNS goal and parent issue linked at save time, before any plan or dispatch.

## Decision
**Decision:** Adopt Direction C: a new, versioned Charter v3 whose normative contract is a published JSON Schema over a JSON data model. Charters are authored on disk as strict-subset YAML, and Vizor and the API exchange JSON. It combines v1's minimal core with v2.0's SFIA, boundaries and coordination structure. It reserves `governance` (tools, credentials, evidence_contracts), `lifecycle` (wake_cycle_sop, autonomy, registration_state), `requirements` and a namespaced `extensions` map from day one. Hardcoded `harness_bindings` is deleted, and harness selection is resolved only at dispatch time from measured `capability_ratings` and `cost_entries`. The 9 non-v2.0 charters move through an automated, human-reviewed `charter migrate` with a one-release dual-read window. Vizor's editor becomes schema-driven, and the dead Markdown validator is removed. Next step: per the Brainstorm-First policy, this goes into a committed spec under `docs/superpowers/specs/`, with a GOVERNS goal and parent issue linked at save time, before any plan or dispatch.

> Signatures: see 2026-11-24-decision-needed-canonical-workspace-agen.json
