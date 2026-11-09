<!-- generated - source of truth is state.db -->
---
decision_id: dec-4f8713bc
topic: "DECIDE PANEL: Should bidirectional sync with GitHub (and future Linear/Jira) be owned by the TPM agent charter via tool-use, rather than by synlynk native code?

CONTEXT: synlynk's TPM role charter (.synlynk/charters/tpm.json) already has a wake_cycle_sop: ingest committed plans, decompose into stories in state.db, tag roles, link stories to GOVERNS goals, run `synlynk tpm sweep` to dispatch ready stories, poll in-flight jobs, escalate blockers. The Agent Studio design spec (docs/superpowers/specs/2026-11-09-vizor-agent-role-management-design.md, already decide-panel-approved twice -- gh:#5185/goal-658aa384) separately calls tpm's scope "expanded (was near-idle): cross-role scheduling, release coordination" and introduces a unified Capability Registry (native synlynk code hooks / local-harness MCPs+Skills via harness_bindings / remote third-party connector manifests like Zapier MCP, Composio, Smithery) as one manifest shape any role can draw on.

TODAY'S ACTUAL IMPLEMENTATION: GitHub-state sync is a native synlynk CLI command, `synlynk gh sync-roadmap` -- a one-way state.db -> GitHub Issues/Milestones projection, implemented as Python inside bin/synlynk.py / synlynk/, not as a tool any agent charter references or invokes. tpm's charter has no autonomous_authority or harness_binding naming it. This was just found to be a gap: tpm owns synlynk-internal story/goal state, but ticket sync to GitHub (and by extension any future Linear/Jira/Asana equivalent) lives outside any agent's charter, as native platform code.

PROPOSAL UNDER REVIEW: Nikhil's explicit position: "I am trying to ensure common functionality that needs to scale/touch 3P components happens via agent role tool-use rather than via synlynk native code." Concretely: (a) make bidirectional GitHub sync (and future Linear/Jira) an explicit autonomous_authority on tpm's charter, invoked as a Capability Registry tool-use (harness_binding or remote-connector manifest entry) rather than a hardcoded native CLI command; (b) generalize this as a standing architectural principle -- any functionality that needs to scale across or touch third-party/external systems should be modeled as agent-role tool-use (charter authority + Capability Registry entry), not synlynk native code, so new integrations (Linear, Jira, Asana, Slack) are added by registering a new tool/connector against an existing role's charter, not by writing new native synlynk subsystems each time.

Evaluate and give a clear, concrete recommendation on EACH of the following, in order:

1. Should GitHub sync specifically (today's `synlynk gh sync-roadmap`) be migrated to be a tpm-charter-owned, Capability-Registry-mediated tool-use, both for the current one-way state.db->GitHub projection and for genuine bidirectional sync (GitHub issue edits/comments flowing back into state.db) if/when that's built? What changes are needed in tpm's charter (.synlynk/charters/tpm.json) and in the Capability Registry manifest shape (per the already-approved spec) to support this concretely?

2. Is "any 3P-touching/scaling functionality should be agent-role tool-use, not native synlynk code" a sound general architectural principle, or does it have real exceptions? Where exactly is the line between "native synlynk platform code" (e.g. git worktree management, state.db itself, dispatch orchestration) and "agent-role tool-use" (e.g. GitHub/Linear/Jira sync, Slack notifications, Zapier/Composio-mediated actions)? Give a test Nikhil can apply to future features.

3. Given the already-approved spec's Capability Registry explicitly supports remote third-party connector manifests (Zapier MCP/Composio/Smithery) as one of three manifest sources, does today's native `gh sync-roadmap` command need to be REPLACED by a registry-mediated connector, or can it be WRAPPED as a native-code Capability Registry entry (per the spec's "native synlynk code hooks" category) that tpm's charter references as a tool-use authority -- i.e., does this proposal require new engineering work beyond what's already scoped in the approved spec's phases, or can it be satisfied by Phase 1's existing capability_registry.py + charter authority wiring plus a migration of tpm.json into agent_store?

4. Does adopting this principle change anything about the Phase ordering or scope already committed in docs/superpowers/plans/2026-11-09-vizor-agent-role-management.md (19 tasks, 7 phases, Phase 7 held pending trust/dedup gate for remote connector ingestion)? Flag anything that needs to be added as a new task vs. deferred as a follow-on story under goal-658aa384.

5. Overall verdict: approve the principle for adoption into the Agent Studio spec/charter model now, approve with modifications, or defer pending more concrete design? List concrete action items, each tagged [must-do-now], [design-now-build-later], or [defer-safely].

300-500 words total, structured by numbered item plus overall verdict.
"
date: 2026-11-09
panel: [claude, agy, codex]
status: approved
---

## Topic
DECIDE PANEL: Should bidirectional sync with GitHub (and future Linear/Jira) be owned by the TPM agent charter via tool-use, rather than by synlynk native code?

CONTEXT: synlynk's TPM role charter (.synlynk/charters/tpm.json) already has a wake_cycle_sop: ingest committed plans, decompose into stories in state.db, tag roles, link stories to GOVERNS goals, run `synlynk tpm sweep` to dispatch ready stories, poll in-flight jobs, escalate blockers. The Agent Studio design spec (docs/superpowers/specs/2026-11-09-vizor-agent-role-management-design.md, already decide-panel-approved twice -- gh:#5185/goal-658aa384) separately calls tpm's scope "expanded (was near-idle): cross-role scheduling, release coordination" and introduces a unified Capability Registry (native synlynk code hooks / local-harness MCPs+Skills via harness_bindings / remote third-party connector manifests like Zapier MCP, Composio, Smithery) as one manifest shape any role can draw on.

TODAY'S ACTUAL IMPLEMENTATION: GitHub-state sync is a native synlynk CLI command, `synlynk gh sync-roadmap` -- a one-way state.db -> GitHub Issues/Milestones projection, implemented as Python inside bin/synlynk.py / synlynk/, not as a tool any agent charter references or invokes. tpm's charter has no autonomous_authority or harness_binding naming it. This was just found to be a gap: tpm owns synlynk-internal story/goal state, but ticket sync to GitHub (and by extension any future Linear/Jira/Asana equivalent) lives outside any agent's charter, as native platform code.

PROPOSAL UNDER REVIEW: Nikhil's explicit position: "I am trying to ensure common functionality that needs to scale/touch 3P components happens via agent role tool-use rather than via synlynk native code." Concretely: (a) make bidirectional GitHub sync (and future Linear/Jira) an explicit autonomous_authority on tpm's charter, invoked as a Capability Registry tool-use (harness_binding or remote-connector manifest entry) rather than a hardcoded native CLI command; (b) generalize this as a standing architectural principle -- any functionality that needs to scale across or touch third-party/external systems should be modeled as agent-role tool-use (charter authority + Capability Registry entry), not synlynk native code, so new integrations (Linear, Jira, Asana, Slack) are added by registering a new tool/connector against an existing role's charter, not by writing new native synlynk subsystems each time.

Evaluate and give a clear, concrete recommendation on EACH of the following, in order:

1. Should GitHub sync specifically (today's `synlynk gh sync-roadmap`) be migrated to be a tpm-charter-owned, Capability-Registry-mediated tool-use, both for the current one-way state.db->GitHub projection and for genuine bidirectional sync (GitHub issue edits/comments flowing back into state.db) if/when that's built? What changes are needed in tpm's charter (.synlynk/charters/tpm.json) and in the Capability Registry manifest shape (per the already-approved spec) to support this concretely?

2. Is "any 3P-touching/scaling functionality should be agent-role tool-use, not native synlynk code" a sound general architectural principle, or does it have real exceptions? Where exactly is the line between "native synlynk platform code" (e.g. git worktree management, state.db itself, dispatch orchestration) and "agent-role tool-use" (e.g. GitHub/Linear/Jira sync, Slack notifications, Zapier/Composio-mediated actions)? Give a test Nikhil can apply to future features.

3. Given the already-approved spec's Capability Registry explicitly supports remote third-party connector manifests (Zapier MCP/Composio/Smithery) as one of three manifest sources, does today's native `gh sync-roadmap` command need to be REPLACED by a registry-mediated connector, or can it be WRAPPED as a native-code Capability Registry entry (per the spec's "native synlynk code hooks" category) that tpm's charter references as a tool-use authority -- i.e., does this proposal require new engineering work beyond what's already scoped in the approved spec's phases, or can it be satisfied by Phase 1's existing capability_registry.py + charter authority wiring plus a migration of tpm.json into agent_store?

4. Does adopting this principle change anything about the Phase ordering or scope already committed in docs/superpowers/plans/2026-11-09-vizor-agent-role-management.md (19 tasks, 7 phases, Phase 7 held pending trust/dedup gate for remote connector ingestion)? Flag anything that needs to be added as a new task vs. deferred as a follow-on story under goal-658aa384.

5. Overall verdict: approve the principle for adoption into the Agent Studio spec/charter model now, approve with modifications, or defer pending more concrete design? List concrete action items, each tagged [must-do-now], [design-now-build-later], or [defer-safely].

300-500 words total, structured by numbered item plus overall verdict.


## Panel Inputs

### claude
[model=default; version=2.1.319 (Claude Code)]

1. **GitHub sync specifically:** Yes, migrate it — but as a wrapper, not a rewrite. `synlynk gh sync-roadmap` becomes a `native_code` Capability Registry entry whose handler imports today's Python function unchanged; tpm.json gains an `autonomous_authority` entry naming that capability ID and (for now) a manual/scheduled trigger condition. Bidirectional sync later is a *second* registry entry (webhook/poll handler feeding state.db), gated by tpm's existing escalate-blockers pathway for conflict resolution — don't build it until it's needed.

2. **General principle — sound but needs a line.** Test: if removing the integration would change *what* gets decided (routing, scheduling, conflict resolution, trust/dedup judgment), it's agent-role tool-use. If it only changes *how bytes move* (worktree creation, state.db I/O, process spawning, auth plumbing) with no judgment call, it's native platform code — a capability can still be registry-listed even if purely mechanical, but it doesn't need charter authority. GitHub sync clears the bar because "what happens on conflicting edits" is a judgment call; `git worktree add` doesn't.

3. **No new engineering beyond approved scope.** Phase 1's `capability_registry.py` + charter authority wiring already covers the `native_code` manifest category. This is a migration task (wrap existing function, edit tpm.json, add one registry entry), not new infrastructure.

4. **Plan impact:** add one small task to whichever Phase 1/2 task block does charter-authority wiring ("migrate gh sync-roadmap to native_code capability + tpm authority"). Phase 7 (remote connector trust/dedup gate) is unaffected — this stays native_code, not a remote connector, so it doesn't need the trust gate. No phase reordering required.

**Overall verdict: approve with modifications.** The principle is correct as a decision test (judgment vs. mechanism), not as a blanket "3P = tool-use" rule.

Action items:
- [must-do-now] Add tpm.json `autonomous_authority` entry + wrap `sync-roadmap` as native_code registry capability — small, unblocks the gap now.
- [design-now-build-later] Write the judgment-vs-mechanism test into the Agent Studio spec as the canonical line for future integrations (Linear/Jira/Slack).
- [defer-safely] Bidirectional GitHub sync (issue edits → state.db) — new capability, build when there's a concrete trigger, not speculatively.
- [defer-safely] Linear/Jira/Asana connectors — follow-on stories under goal-658aa384, not new tasks now.

### agy
[model=default; version=1.5.3]

### 1. GitHub Sync Migration & TPM Charter Changes
**Yes, migrate it.** GitHub sync should be owned by the TPM charter via Capability Registry tool-use. 
- **Charter (`.synlynk/charters/tpm.json`):** Add `sync:project_trackers` to `autonomous_authority`. Under `wake_cycle_sop`, add sync invocation after plan decomposition and during triage sweeps. Bind `tracker_sync` in `harness_bindings`.
- **Capability Registry Manifest:** Register an entry under `source: native` with tool name `tracker.sync_roadmap` exposing parameters (`provider: "github" | "linear"`, `direction: "export" | "import" | "bidirectional"`). For true bidirectional sync, TPM agent sessions invoke read tools (fetching issue status/comments) and apply updates to `state.db` via role-governed mutation tools rather than an uninspected background daemon.

### 2. The Architectural Principle & Boundary Test
The principle is sound, with one vital boundary: **Kernel state and local harness execution must remain native platform code; external world interaction belongs to agent tool-use.**
- **The Boundary Test:** *Does the operation require external API credentials/semantics outside the local repository and execution runtime, or does it interpret external human intent?*
  - **Native Platform Code (Kernel):** Worktrees, `state.db` ACID transactions, process lifecycle, dispatch scheduling, local telemetry.
  - **Agent Tool-Use (Edges):** Third-party APIs (GitHub, Linear, Slack, Zapier), external sync, notifications, and cross-system mappings where schema mismatches require contextual reasoning.

### 3. Wrap vs. Replace & Engineering Scope
**Wrap, do not replace.**
`synlynk gh sync-roadmap` does not need to be rewritten or swapped for a remote connector immediately. Wrap the existing Python logic as a `native` source hook in `capability_registry.py`. TPM's charter simply references this capability. This satisfies the architectural requirement within Phase 1 scope (`capability_registry.py` + charter validation in `agent_store`), incurring zero new architectural debt while deferring connector-based rewrites to Phase 7.

### 4. Impact on Phase Ordering & Scope
**No change to Phase ordering or the 19-task plan.**
Phase 7 already isolates remote connector ingestion behind the trust/deduplication gate. Wrapping native commands fits cleanly into **Phase 1 (Data Model & Schema)** and **Phase 2 (Agent Store CRUD)** as test fixture validations without altering the committed plan critical path.

### 5. Overall Verdict & Action Items
**Verdict: APPROVE WITH MODIFICATIONS.** Adopt the principle immediately, preserving native platform ownership of local core runtime state.

- **[must-do-now]**: Declare `tracker.sync_roadmap` as a native capability manifest in Phase 1 schema definitions.
- **[design-now-build-later]**: Update `.synlynk/charters/tpm.json` in the store migration (Phase 2) to grant `sync:project_trackers` authority and reference the wrapped tool.
- **[defer-safely]**: Bidirectional sync conflict-resolution agent prompts and migration to remote 3P connectors (Composio/Smithery Linear/Jira tools) under Phase 7 / follow-on goal tickets.

### codex
[model=default; version=codex-cli 0.163.0]

1. **GitHub sync:** Migrate ownership to TPM, including both current projection and future inbound synchronization. Add explicit authorities such as `sync_external_tracker`, `pull_external_updates`, and `reconcile_external_state`, with boundaries for credentials, conflict handling, rate limits, and human escalation. Add a Capability Registry manifest for the connector, including provider, operations, directionality, scope, provenance, workspace, and required approvals. TPM’s wake cycle should invoke reconciliation as part of sweep/tracking, not merely dispatch stories.

2. **General principle:** Adopt it with a boundary: external-system *effects and protocols* belong to role-authorized capabilities; synlynk’s local control plane remains native. Thus GitHub/Linear/Jira/Slack/Zapier actions are capabilities, while `state.db`, worktrees, dispatch scheduling, readiness computation, policy enforcement, and local audit/versioning remain native. Future-feature test: “Does this require credentials, network APIs, provider-specific schemas, or durable external side effects?” If yes, model it as a registered capability owned by a chartered role. If it defines synlynk’s local invariants or execution substrate, keep it native.

3. **Replacement vs wrapping:** No immediate replacement is required. `gh sync-roadmap` can initially become a native-code Capability Registry hook, referenced by TPM authority. This satisfies the approved three-source registry model and enables later replacement with a remote connector without changing TPM’s charter contract. Phase 1 wiring plus migration of `tpm.json` into `agent_store` is sufficient for the first step, but genuine bidirectional sync still needs connector semantics, event/polling behavior, idempotency, conflict policy, and tests.

4. **Plan impact:** Do not reorder phases. Add one Phase 5/6 task for “TPM external-sync capability contract and native-hook adapter,” and record bidirectional reconciliation as a follow-on under `goal-658aa384`. Remote Zapier/Composio/Smithery ingestion remains gated by Phase 7 trust/dedup review.

5. **Overall verdict:** **Approve with modifications.** [must-do-now] Add TPM authorities, registry manifest fields, and the native adapter contract. [design-now-build-later] Specify bidirectional conflict/idempotency and provider-neutral sync semantics. [defer-safely] Remote connector ingestion and additional providers until the existing trust/dedup gate passes. The principle should enter the charter/spec model now, with native platform code limited to the adapter and control-plane primitives.

## Synthesis
## Synthesized Decision

**1. GitHub sync migration:** All three reviewers converge: wrap, don't rewrite. `synlynk gh sync-roadmap`'s existing Python becomes a `native_code` Capability Registry entry (handler = today's function, unchanged), and `.synlynk/charters/tpm.json` gains an explicit `autonomous_authority` (e.g. `sync:project_trackers` / `sync_external_tracker`) naming that capability ID, invoked from `wake_cycle_sop` during sweep/triage rather than as an out-of-charter CLI command. Bidirectional sync (GitHub edits/comments → `state.db`) is a *separate*, later registry entry with its own conflict/idempotency semantics, not built now.

**2. General principle — sound with a boundary test, not absolute.** Converged test: **does the operation require external credentials/APIs/provider schemas and involve a judgment call (routing, conflict resolution, trust/dedup), or does it govern local invariants/execution substrate with no external judgment?** The former (GitHub/Linear/Jira/Slack/Zapier/Composio actions) → agent-role tool-use via Capability Registry. The latter (`state.db` transactions, git worktrees, dispatch scheduling, process lifecycle, local policy enforcement) → stays native platform code, registry-listable at most, no charter authority needed. GitHub sync clears the bar because "what happens on a conflicting edit" is a judgment call; `git worktree add` doesn't.

**3. No new engineering beyond already-approved scope.** This is a migration task — wrap the existing function as a `native_code` manifest entry, edit `tpm.json`, migrate it into `agent_store` — fully covered by Phase 1's `capability_registry.py` + charter-authority wiring. It is explicitly NOT a remote-connector replacement and does not touch Phase 7's trust/dedup gate.

**4. No phase reordering.** Add one small task to the Phase 1/2 charter-authority-wiring block: "migrate `gh sync-roadmap` to a `native_code` capability + grant tpm authority." Phase 7 is unaffected. Bidirectional GitHub sync, and Linear/Jira/Asana/Slack connectors generally, become follow-on stories under `goal-658aa384`, not new tasks in the current plan.

**5. Action items:**
- [must-do-now] Wrap `gh sync-roadmap` as a `native_code` Capability Registry entry; add the corresponding `autonomous_authority` to `tpm.json`; wire into `wake_cycle_sop`.
- [design-now-build-later] Codify the judgment-vs-mechanism boundary test as the canonical litmus in the Agent Studio spec, so future integrations (Linear, Jira, Slack) are evaluated against it rather than case-by-case.
- [defer-safely] Bidirectional GitHub sync (conflict resolution, idempotency, polling/webhook semantics) — build when a concrete trigger exists.
- [defer-safely] Linear/Jira/Asana/Slack connectors via Composio/Smithery — follow-on stories under `goal-658aa384`, gated by Phase 7's existing trust/dedup review.

---

**Decision:** Approve the principle with modifications — adopt "external-system-touching, judgment-bearing functionality is agent-role tool-use via the Capability Registry; local control-plane mechanics stay native" as the standing architectural rule now, migrate `synlynk gh sync-roadmap` into a `native_code` Capability Registry entry under a new `tpm.json` `autonomous_authority` (wrap, don't rewrite, no new engineering beyond Phase 1's already-approved scope), make no changes to phase ordering in the committed plan beyond one small Phase 1/2 wiring task, and defer bidirectional sync plus all future Linear/Jira/Asana/Slack connectors as follow-on stories under `goal-658aa384`, still gated by Phase 7's trust/dedup review.

## Decision
**Decision:** Approve the principle with modifications — adopt "external-system-touching, judgment-bearing functionality is agent-role tool-use via the Capability Registry; local control-plane mechanics stay native" as the standing architectural rule now, migrate `synlynk gh sync-roadmap` into a `native_code` Capability Registry entry under a new `tpm.json` `autonomous_authority` (wrap, don't rewrite, no new engineering beyond Phase 1's already-approved scope), make no changes to phase ordering in the committed plan beyond one small Phase 1/2 wiring task, and defer bidirectional sync plus all future Linear/Jira/Asana/Slack connectors as follow-on stories under `goal-658aa384`, still gated by Phase 7's trust/dedup review.

> Signatures: see 2026-11-09-decide-panel-should-bidirectional-sync-w.json
