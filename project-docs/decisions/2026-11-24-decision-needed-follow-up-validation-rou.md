<!-- generated - source of truth is state.db -->
---
decision_id: dec-5c6553ef
topic: "DECISION NEEDED (follow-up/validation round on the already-approved Charter v3 schema from dec 2026-11-24-decision-needed-canonical-workspace-agen): the panel previously converged on Direction C (new unified Charter v3: JSON Schema normative, strict-YAML authoring, JSON data model; reserved blocks governance/lifecycle/requirements/extensions; hardcoded harness_bindings deleted in favor of dispatch-time resolution against capability_ratings/cost_entries).\n\nNikhil then added five long-term synlynk product goals charters must satisfy: (1) agents industry/domain-agnostic, (2) agents fully configurable via Agent Studio (Vizor UI), (3) agents have well-defined scope/boundaries/tools/audit-trails/identity, (4) agents must be able to act in concert/communicate with each other when required, (5) agents must strictly adhere to the synlynk constitution (4 Asimov-style laws with DeliveryTiers, in constitution.py) in letter AND spirit.\n\nGoals 1-3 are judged already covered by the approved Charter v3 design (domain-neutral field names; schema-driven Vizor editor regeneration; governance.tools+boundaries cover scope/tools/audit). Goal 3 has one acknowledged gap: no identity block ties a charter to its GitHub App credential record (.synlynk/github_apps/<role>/) today -- proposed fix is an  block with an  reference field, mirroring how  already uses  references (never raw credentials).\n\nGoals 4 and 5 are judged to have REAL gaps needing this validation round:\n\nGOAL 4 GAP: the only coordination-related field carried into Charter v3 is , a single descriptive string (e.g. "orchestrator") inherited from the old v2.0 schema. This says WHAT KIND of coordinator a role is, not WHO it may talk to, under what protocol, or what a handoff contract looks like. Today inter-agent coordination is purely ad hoc via synlynk dispatch (worktree-isolated subprocess jobs) and shared state.db rows -- there is no schema-level contract for agent-to-agent communication at all. PROPOSED ADDITION: a  block with  (which other roles this role may hand off to / request work from),  (expected input/output shape at a handoff boundary), and  (how -- dispatch job, GitHub PR/issue comment, shared state.db table, message queue, etc.).\n\nGOAL 5 GAP: constitution.py defines 4 "Asimov law" tiers (DeliveryTier) but constitution_gate.py's enforcement is ONLY a textual citation-tag presence check, run in non-blocking  mode by default -- no code path ties charter authority to constitutional law today, and the charter schema has zero fields referencing the constitution at all. PROPOSED ADDITION: a  block with , , and  -- NOTE this is scoped as a schema placeholder only (giving future enforcement something concrete to check against), NOT as implementing enforcement itself, since flipping observe-mode to enforce-mode is judged a separate policy decision outside this schema spec's scope.\n\nVALIDATE OR CHALLENGE: (a) is  (peers/handoff_contracts/communication_channels) the right shape for goal 4, or is there a better-known pattern (e.g. explicit pub/sub topics, a dependency DAG field, borrowing from an existing multi-agent framework's handoff model) that would serve a STANDALONE AGENT BUILDER PRODUCT better than an ad hoc block invented in-house; (b) is  as a placeholder-only field the right scope, or should this validation round push for something stronger (e.g. a required  referencing specific law/tier IDs per SOP step, enforced by the SAME validator that checks REQUIRED_SECTIONS today) given Nikhil's explicit "strictly adhere... in letter AND spirit" framing suggests he wants more than a placeholder; (c) should , , and  all land in the SAME v3 schema version as governance/lifecycle/requirements, or should constitution_binding specifically be deferred to a v3.1 once the observe-to-enforce policy decision is separately made. Give a clear recommendation, not a both-sides hedge."
date: 2026-11-24
panel: [claude, agy, codex]
status: approved
---

## Topic
DECISION NEEDED (follow-up/validation round on the already-approved Charter v3 schema from dec 2026-11-24-decision-needed-canonical-workspace-agen): the panel previously converged on Direction C (new unified Charter v3: JSON Schema normative, strict-YAML authoring, JSON data model; reserved blocks governance/lifecycle/requirements/extensions; hardcoded harness_bindings deleted in favor of dispatch-time resolution against capability_ratings/cost_entries).\n\nNikhil then added five long-term synlynk product goals charters must satisfy: (1) agents industry/domain-agnostic, (2) agents fully configurable via Agent Studio (Vizor UI), (3) agents have well-defined scope/boundaries/tools/audit-trails/identity, (4) agents must be able to act in concert/communicate with each other when required, (5) agents must strictly adhere to the synlynk constitution (4 Asimov-style laws with DeliveryTiers, in constitution.py) in letter AND spirit.\n\nGoals 1-3 are judged already covered by the approved Charter v3 design (domain-neutral field names; schema-driven Vizor editor regeneration; governance.tools+boundaries cover scope/tools/audit). Goal 3 has one acknowledged gap: no identity block ties a charter to its GitHub App credential record (.synlynk/github_apps/<role>/) today -- proposed fix is an  block with an  reference field, mirroring how  already uses  references (never raw credentials).\n\nGoals 4 and 5 are judged to have REAL gaps needing this validation round:\n\nGOAL 4 GAP: the only coordination-related field carried into Charter v3 is , a single descriptive string (e.g. "orchestrator") inherited from the old v2.0 schema. This says WHAT KIND of coordinator a role is, not WHO it may talk to, under what protocol, or what a handoff contract looks like. Today inter-agent coordination is purely ad hoc via synlynk dispatch (worktree-isolated subprocess jobs) and shared state.db rows -- there is no schema-level contract for agent-to-agent communication at all. PROPOSED ADDITION: a  block with  (which other roles this role may hand off to / request work from),  (expected input/output shape at a handoff boundary), and  (how -- dispatch job, GitHub PR/issue comment, shared state.db table, message queue, etc.).\n\nGOAL 5 GAP: constitution.py defines 4 "Asimov law" tiers (DeliveryTier) but constitution_gate.py's enforcement is ONLY a textual citation-tag presence check, run in non-blocking  mode by default -- no code path ties charter authority to constitutional law today, and the charter schema has zero fields referencing the constitution at all. PROPOSED ADDITION: a  block with , , and  -- NOTE this is scoped as a schema placeholder only (giving future enforcement something concrete to check against), NOT as implementing enforcement itself, since flipping observe-mode to enforce-mode is judged a separate policy decision outside this schema spec's scope.\n\nVALIDATE OR CHALLENGE: (a) is  (peers/handoff_contracts/communication_channels) the right shape for goal 4, or is there a better-known pattern (e.g. explicit pub/sub topics, a dependency DAG field, borrowing from an existing multi-agent framework's handoff model) that would serve a STANDALONE AGENT BUILDER PRODUCT better than an ad hoc block invented in-house; (b) is  as a placeholder-only field the right scope, or should this validation round push for something stronger (e.g. a required  referencing specific law/tier IDs per SOP step, enforced by the SAME validator that checks REQUIRED_SECTIONS today) given Nikhil's explicit "strictly adhere... in letter AND spirit" framing suggests he wants more than a placeholder; (c) should , , and  all land in the SAME v3 schema version as governance/lifecycle/requirements, or should constitution_binding specifically be deferred to a v3.1 once the observe-to-enforce policy decision is separately made. Give a clear recommendation, not a both-sides hedge.

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Analysis**

**(a) Coordination shape.** `peers / handoff_contracts / communication_channels` is the right instinct but under-specified as invented in-house. The pattern that has actually converged across multi-agent frameworks is the handoff-as-typed-edge model (OpenAI Agents SDK handoffs, LangGraph edges, A2A/Agent Cards). Each edge names a target, an input/output schema, and a transport. I'd keep the block but restructure it as one list: `coordination.handoffs[]`, where each entry has `to_role`, `input_schema_ref`, `output_schema_ref`, `transport` (enum: dispatch_job | gh_pr_comment | gh_issue | state_db_table | queue), and `trigger`. This does three things:
- It replaces three loosely linked lists with one edge list.
- It makes the role graph derivable as a DAG, which Vizor can render directly and the validator can check for dangling roles and cycles.
- It stays framework-neutral, so it maps cleanly onto A2A Agent Cards if synlynk later interoperates.

Skip pub/sub topics now. synlynk has no broker, so topics would be speculative. Leave `transport` as an enum with `extensions` as the escape hatch.

**(b) Constitution scope.** A bare placeholder is too weak for "letter AND spirit". But enforcement is a separate policy decision, and that part stays out of this spec. The middle path is structural, not behavioral. Make `constitution_binding` required in schema terms: each charter must declare `tier_acknowledgements` (the law/tier IDs, validated against `constitution.py`'s actual DeliveryTier enum) and per-SOP-step `law_refs` for steps that touch governed actions. The existing REQUIRED_SECTIONS validator then checks that the references exist and resolve to real IDs. This is the same class of check as today's citation-tag check. It adds referential integrity, so nothing can cite a nonexistent law. It does not add runtime enforcement, so the observe-to-enforce flip is still not made here. It also gives a future enforcement gate something concrete to read. A permanent optional placeholder would likely go unfilled and never get used.

**(c) Versioning.** Ship `identity`, `coordination`, and `constitution_binding` in v3.0 together. Defer only the semantics of enforcement. Splitting the schema into v3.1 would force a migration for every charter authored in between, and the extra version buys nothing, because the binding block's shape doesn't depend on the observe/enforce decision. Making the block required later is the costly change. Adding it now and defaulting it to a validated minimal form is cheap.

**Recommendation:** Adopt `identity`, a typed-edge `coordination.handoffs[]`, and a `constitution_binding` with validated tier and law IDs. Make `constitution_binding` required in structure (IDs must resolve). Add no runtime enforcement. Land all three in v3.0.

### agy
[model=default; version=1.5.15]

**Last completed task:** PR #5461 (devlog + cost-log for PR #5460 housekeeping round).  
**Next task from `todo.md`:** Isolated generated story [backend] (`story-de2f3459`).

---

### Analysis

**(a) Coordination: Replace Ad-Hoc Transport with Declarative Handoffs**  
The proposed `communication_channels` conflates low-level transport (dispatch, IPC, message queues) with agent boundaries. A standalone agent builder (Agent Studio / Vizor) requires topology and data contracts, not runtime plumbing. We should adopt the proven industry pattern from OpenAI Swarm and AutoGen: replace `communication_channels` with a declarative **`handoffs`** list specifying `target_role`, `condition`, and strict input/output JSON schemas. This maps cleanly to visual node-and-edge connections in Vizor while keeping the agent definition transport-agnostic.

**(b) Constitution: Fail-Closed Schema Validation, Not a Decorative Placeholder**  
A toothless placeholder violates Nikhil’s explicit mandate for strict adherence in letter and spirit. While runtime execution interception can remain in observation mode, **charter parse-time conformance must be mandatory today**. The schema validator that checks `REQUIRED_SECTIONS` must enforce a non-empty `constitution_binding` with an enumerated `delivery_tier` (`T0`–`T3`) and valid `inviolable_laws` IDs matching `constitution.py`. If a charter lacks valid constitutional bindings, it must fail validation immediately.

**(c) Scope: Land All Three in Charter v3.0**  
`identity`, `handoffs`, and `constitution_binding` must ship together in Charter v3.0. Deferring the constitutional block to v3.1 creates immediate schema churn, complicates Vizor form generation, and forces dual migrations. Decoupling schema-level contract requirements from runtime enforcement policy allows us to freeze a stable v3 specification immediately without premature runtime risks.

### Final Position
**I recommend landing `identity`, a refined `handoffs` contract (discarding transport-level `communication_channels`), and a mandatory, schema-validated `constitution_binding` together in Charter v3.0.** Reject inert placeholders: enforce constitutional tiers and law mappings at schema validation time, standardize coordination as declarative graph handoffs optimized for Agent Studio, and finalize the v3 schema without deferral to v3.1.

### codex
[model=default; version=codex-cli 0.169.1]

Direction C should be extended in v3, but with a more contract-first coordination model than a loose `coordination.peers` allowlist. For a standalone Agent Builder, make coordination portable across runtimes: define named interaction contracts with permitted counterpart roles, operation (`delegate`, `request`, `notify`, `escalate`), typed input/output schema references, delivery guarantees or acknowledgement expectations, and allowed channel kinds. Channels should be abstract capabilities (`dispatch`, `issue_comment`, `shared_store`, `queue`), with implementation-specific configuration outside the charter. `peers` may remain as a derived convenience view, but should not be the source of truth. Explicit pub/sub topics are useful only as one channel binding; a dependency DAG is a workflow concern, not an enduring agent-identity concern.

A placeholder-only `constitution_binding` is too weak for Nikhil’s “letter AND spirit” requirement. The schema should require a binding that maps each chartered authority, lifecycle/SOP step, or high-risk tool capability to stable constitution law and DeliveryTier identifiers, plus an expected evidence/audit reference. The normal schema validator can immediately reject missing, unknown, or structurally incomplete mappings. That is not the same as deciding whether `constitution_gate` moves from observe to enforce mode: semantic enforcement, interpretation, and consequence policy can remain a separate decision.

The proposed GitHub-App-backed `identity` block is also appropriate: it should hold an `app_ref`, never credentials, and establish the principal responsible for audit records and external actions.

My recommendation: land `identity`, contract-first `coordination`, and required `constitution_binding` together in Charter v3. Deferring constitutional binding to v3.1 would ship an allegedly governing charter schema without a machine-checkable statement of its governing authority. Ship structural validation now; defer only the observe-to-enforce operational policy and deeper semantic enforcement.

## Synthesis
**Where the panel agrees:** all three members back the same core, and I'm adopting it.
- Ship `identity`, `coordination` and `constitution_binding` in Charter v3.0 together. A v3.1 split would force migrations on every charter authored in between, and the block's shape doesn't depend on the observe-to-enforce decision.
- A placeholder-only `constitution_binding` is too weak for "letter AND spirit". The schema validator that checks `REQUIRED_SECTIONS` should require it and check that its IDs resolve.
- Runtime enforcement stays out of scope. Flipping `constitution_gate.py` from observe to enforce remains a separate policy decision.

**Resolved differences**

- **(a) Coordination.** I'm replacing `peers / handoff_contracts / communication_channels` with a typed-edge list, `coordination.handoffs[]`. This is the pattern in the OpenAI Agents SDK, LangGraph edges and A2A. Each entry has:
  - `to_role`
  - `operation` (`delegate | request | notify | escalate`, from codex)
  - `trigger` or `condition`
  - `input_schema_ref` and `output_schema_ref`
  - `transport`, an abstract enum (`dispatch_job | gh_pr_comment | gh_issue | state_db_table | queue`), with implementation config kept outside the charter
  - an optional `ack` expectation (from codex)

  `peers` becomes a derived view of these edges, not stored. The validator checks that every `to_role` exists, that every schema ref resolves, and that the role graph has no dangling edges or illegal cycles. Vizor can render the graph directly. Pub/sub topics are rejected for now because synlynk has no broker. A queue can be a `transport` value, and `extensions` is the escape hatch. A dependency DAG is a workflow concern, so it is derived and not stored. The old `coordination` string moves into `extensions` or a `role_kind` field.

- **(b) Constitution binding.** It is required and structural. It has three parts:
  - `tier_acknowledgements`: the DeliveryTier IDs the role operates under.
  - `law_refs`: required on each SOP step, lifecycle step or high-risk tool capability under `governance.tools`. Each ref cites the law and tier it implicates.
  - `evidence_ref`: where the audit record for that step lands.

  The validator resolves every ID against the real enums in `constitution.py` and fails closed on missing, unknown or incomplete bindings. It must read those enums directly and not hardcode them. Agy's `T0–T3` naming should not be trusted until it's checked against `DeliveryTier`.

- **(c) Identity.** `identity.app_ref` points to the `.synlynk/github_apps/<role>/` record. It never holds raw credentials, which mirrors how existing `*_ref` fields work. It is the principal that `evidence_ref` audit records attribute to.

Decision: Charter v3.0 will include `identity` (with `app_ref` only), a typed-edge `coordination.handoffs[]` (peers derived, no pub/sub, no stored DAG), and a required, schema-validated `constitution_binding`. That binding has `tier_acknowledgements`, per-step `law_refs` and `evidence_ref`, all resolved against `constitution.py` by the same validator that checks `REQUIRED_SECTIONS`. All three blocks land together in v3.0 with no v3.1 deferral. Runtime enforcement, meaning the observe-to-enforce flip in `constitution_gate.py`, stays a separate policy decision outside this spec.

I haven't written this to the devlog or recorded it with `synlynk decide --record`. Say the word and I'll do that.

## Decision
Decision: Charter v3.0 will include `identity` (with `app_ref` only), a typed-edge `coordination.handoffs[]` (peers derived, no pub/sub, no stored DAG), and a required, schema-validated `constitution_binding`. That binding has `tier_acknowledgements`, per-step `law_refs` and `evidence_ref`, all resolved against `constitution.py` by the same validator that checks `REQUIRED_SECTIONS`. All three blocks land together in v3.0 with no v3.1 deferral. Runtime enforcement, meaning the observe-to-enforce flip in `constitution_gate.py`, stays a separate policy decision outside this spec.

> Signatures: see 2026-11-24-decision-needed-follow-up-validation-rou.json
