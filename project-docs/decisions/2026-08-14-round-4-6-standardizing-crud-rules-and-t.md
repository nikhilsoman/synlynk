---
decision_id: dec-4f246e5a
topic: "ROUND 4/6 — Standardizing CRUD rules and their enforcement functions for reliability and uniformity of instruction.

EVIDENCE — the "rules" governing context docs today live in at least 5 disconnected places with no shared enforcement primitive:
1. Prose instructions in CLAUDE.md (global ~/.claude/CLAUDE.md AND per-repo CLAUDE.md) — e.g. Blog Post Protocol, Worktree Hygiene Protocol, Cost Capture Protocol — all discipline-based, zero tooling backing, silently rot (Round 3 showed Blog Post Protocol failing in 3/4 repos).
2. Auto-generated files with a hand-written header warning ("Do NOT hand-edit this file... source of truth is state.db") e.g. .synlynk/project-docs/todo.md, .synlynk/project-docs/roadmap.md — these headers are the ONLY enforcement, nothing stops a human or agent from editing them anyway, and per Round 1 findings a repo can end up with a real, actively-hand-maintained project-docs/todo.md at a DIFFERENT path simultaneously.
3. CLI commands that partially manage doc lifecycle: `synlynk migrate` (project-docs/ → state.db), `synlynk story create/update` (writes state.db, regenerates todo.md), `synlynk roadmap add` (regenerates roadmap.md) — these exist but there's no single command that audits whether the CRUD rule is actually being followed post-hoc.
4. .gitignore as an implicit "this is ephemeral" signal — used inconsistently: .synlynk/* is gitignored in synlynk itself (with 2 explicit exceptions) but cc-videoreframing gitignores its real canonical project-docs/ location while tracking the stale one.
5. Skill-injected conventions (docs/superpowers/specs, docs/superpowers/plans) — the ONE thing that actually held (confirmed Round 3), because the rule lives in tool-injected context at time-of-use rather than as static prose the agent must remember to consult.

QUESTION: Design a single, uniform "CRUD contract" primitive that every context-doc category (project-docs canonical docs, state.db-generated docs, specs/plans/decisions/rca/blog/archive, and future doc types) can register against, such that: (a) CREATE always happens through one code path per doc type (CLI command or skill trigger, never raw file write by a human or agent), (b) READ/UPDATE rules make clear whether a doc is hand-maintained (freely editable) or generated (edits are lost/rejected), (c) DELETE/ARCHIVE follows the Round-2-decided archive pattern automatically rather than by discipline, and (d) the contract is machine-checkable (a `synlynk audit-docs`-style command from Round 2 can verify compliance) rather than relying on prose in CLAUDE.md. Should this be one unified manifest-driven system (extending the Round-1 doc-lifecycle-manifest concept) that both generated and hand-maintained docs register into, or do generated (state.db-backed) and hand-maintained (human-authored) docs need fundamentally different contracts? How does this interact with the `.gitignore` ambiguity found in evidence point 4 — should gitignore-status be DERIVED from the manifest's hand-maintained/generated flag rather than set independently per repo?"
date: 2026-08-14
panel: [codex, grok]
status: approved
---

## Topic
ROUND 4/6 — Standardizing CRUD rules and their enforcement functions for reliability and uniformity of instruction.

EVIDENCE — the "rules" governing context docs today live in at least 5 disconnected places with no shared enforcement primitive:
1. Prose instructions in CLAUDE.md (global ~/.claude/CLAUDE.md AND per-repo CLAUDE.md) — e.g. Blog Post Protocol, Worktree Hygiene Protocol, Cost Capture Protocol — all discipline-based, zero tooling backing, silently rot (Round 3 showed Blog Post Protocol failing in 3/4 repos).
2. Auto-generated files with a hand-written header warning ("Do NOT hand-edit this file... source of truth is state.db") e.g. .synlynk/project-docs/todo.md, .synlynk/project-docs/roadmap.md — these headers are the ONLY enforcement, nothing stops a human or agent from editing them anyway, and per Round 1 findings a repo can end up with a real, actively-hand-maintained project-docs/todo.md at a DIFFERENT path simultaneously.
3. CLI commands that partially manage doc lifecycle: `synlynk migrate` (project-docs/ → state.db), `synlynk story create/update` (writes state.db, regenerates todo.md), `synlynk roadmap add` (regenerates roadmap.md) — these exist but there's no single command that audits whether the CRUD rule is actually being followed post-hoc.
4. .gitignore as an implicit "this is ephemeral" signal — used inconsistently: .synlynk/* is gitignored in synlynk itself (with 2 explicit exceptions) but cc-videoreframing gitignores its real canonical project-docs/ location while tracking the stale one.
5. Skill-injected conventions (docs/superpowers/specs, docs/superpowers/plans) — the ONE thing that actually held (confirmed Round 3), because the rule lives in tool-injected context at time-of-use rather than as static prose the agent must remember to consult.

QUESTION: Design a single, uniform "CRUD contract" primitive that every context-doc category (project-docs canonical docs, state.db-generated docs, specs/plans/decisions/rca/blog/archive, and future doc types) can register against, such that: (a) CREATE always happens through one code path per doc type (CLI command or skill trigger, never raw file write by a human or agent), (b) READ/UPDATE rules make clear whether a doc is hand-maintained (freely editable) or generated (edits are lost/rejected), (c) DELETE/ARCHIVE follows the Round-2-decided archive pattern automatically rather than by discipline, and (d) the contract is machine-checkable (a `synlynk audit-docs`-style command from Round 2 can verify compliance) rather than relying on prose in CLAUDE.md. Should this be one unified manifest-driven system (extending the Round-1 doc-lifecycle-manifest concept) that both generated and hand-maintained docs register into, or do generated (state.db-backed) and hand-maintained (human-authored) docs need fundamentally different contracts? How does this interact with the `.gitignore` ambiguity found in evidence point 4 — should gitignore-status be DERIVED from the manifest's hand-maintained/generated flag rather than set independently per repo?

## Panel Inputs

### codex
The evidence points to a single failure mode: lifecycle rules exist, but enforcement is fragmented across prose, filenames, generators, and `.gitignore`. The successful specs/plans convention confirms that enforcement works best when the rule is injected at the point of action, not merely documented.

A unified manifest-driven CRUD contract should be the source of truth for every registered document category. Each entry should define: canonical path and identifier, owner/storage backend, creation mechanism, read visibility, update mode (`hand-maintained`, `generated`, or perhaps `append-only`), deletion behavior, archive destination/metadata, and validation rules. Creation should route through a registered CLI command or skill trigger. The primitive need not force identical implementation: a generated document may be rendered from `state.db`, while a hand-authored document may be created from a template and then edited normally. They share lifecycle semantics, but differ in their update and integrity checks.

For generated documents, the contract should make the rendered file explicitly non-authoritative. `audit-docs` should detect unauthorized modifications by comparing content or provenance hashes, identify duplicate canonical paths, verify generator availability, and report stale or missing outputs. For hand-maintained documents, auditing should validate location, required metadata, naming, and archive state without rejecting legitimate edits. Delete should be disabled or converted automatically into archive, preserving history and recording who/when/why where available.

`.gitignore` should not independently decide whether a document is canonical or ephemeral. The manifest should derive the expected tracking policy from lifecycle attributes, then `audit-docs` should flag mismatches between that policy and repository `.gitignore`/Git tracking. Exceptions should be explicit manifest overrides, not accidental repository behavior.

I recommend one unified, manifest-driven CRUD system with category-specific policies—not two separate contracts. Generated and hand-maintained docs require different enforcement algorithms, but the same registration, command routing, audit, archive, and git-status model. This gives future document types one extension point and makes reliability measurable rather than dependent on discipline.

### grok
I'll review the existing lifecycle, audit, and generated-doc patterns so the recommendation is grounded in how the repo actually works today.The fleet already has a CRUD problem, not a prose problem. Round 1 split *where* generated and hand-maintained files live. Round 2 made a lifecycle manifest plus `synlynk audit-docs` the control plane. Round 3 showed the only convention that held was a write-path injection, not a CLAUDE.md reminder. Round 4 should attach operations to that same manifest instead of inventing a second contract family.

**One contract, two mutability modes.** Generated (`state.db` views) and hand-maintained (specs, plans, RCA, decisions, blog, archive) share one registration schema. They differ only in the verbs:

| Field | Generated | Hand-maintained |
|---|---|---|
| `create_via` | one CLI (`story create`, `roadmap add`, `cost log`, `memory add`) | one skill or `synlynk doc create <type>` |
| `update` | write the store; markdown is a view | edit the file |
| `delete` | archive + stamp `superseded-by` (Round 2) | same |
| `git` | derived: ignore (or one declared cache policy) | derived: track |

A second contract would recreate today’s five enforcement sites. Hybrid files (e.g. canon with `## Human notes`) are just a third `mutability` value, not a third system.

**CREATE never means a raw write.** The manifest names the only legal creator. Agents and humans may still type into a generated file; that is a detected violation, not a supported path. Today’s banner plus warn-and-continue (`_detect_hand_edit`) is insufficient: `audit-docs` must fail CI / `pr check` when a generated path differs from regeneration, when a process doc appears outside its registered glob, or when a file exists with no registered creator.

**READ is the mutability flag.** Generated: trust `state.db`, treat markdown as disposable. Hand-maintained: the file is the source. Headers become machine-readable stamps (`<!-- synlynk:generated -->`) derived from the manifest, not hand-written folklore.

**`.gitignore` is derived, never independent.** That is the cc-videoreframing failure: ignore status was set per repo and contradicted the live tree. `generated` / `generated-on-demand` → ignore (except explicit exceptions like `roles.yaml`). `hand-maintained` and `archived` → tracked. `audit-docs` fails if ignore rules and mutability disagree.

Skills remain the create-time injector (Round 3). CLAUDE.md protocols become generated summaries of the manifest, not the source of rules.

**Position:** extend the Round 1/2 lifecycle manifest into a single CRUD contract. Generated and hand-maintained docs register the same way and differ only by `mutability`. Derive gitignore from that flag. Enforce with `audit-docs`, not discipline. Two contracts would just rename the current split.

## Synthesis
The panel converges on one unified, manifest-driven CRUD contract, extending the Round-1 lifecycle manifest. Generated and hand-maintained documents should not have separate systems; they should share registration, creation routing, archiving, auditing, and repository-policy rules while declaring different mutability modes.

Each document type should register:

- canonical identifier and path/glob
- authoritative backend: file, `state.db`, or another store
- sole `create_via` command or skill trigger
- mutability: `generated`, `hand-maintained`, or optionally `append-only`/`hybrid`
- read authority and update behavior
- required metadata and validation
- archive/delete policy, including automatic archive records and supersession links
- expected Git tracking policy

Generated files remain disposable views: updates must go through their backend, and `audit-docs` must detect content drift, missing or stale regeneration, duplicate canonical files, unregistered files, and unavailable creators. Hand-maintained files remain freely editable, with audits focused on canonical location, metadata, naming, and archive state. Both types use the same automatic archive behavior; deletion should resolve to archival rather than rely on discipline.

Creation must be routed through the registered command or skill. Static headers can remain as generated provenance markers, but they are advisory; enforcement comes from the command paths and `audit-docs`, which should be capable of failing CI or `pr check` for violations. CLAUDE.md should become generated guidance from the manifest, not an independent source of truth.

`.gitignore` status should be derived from the manifest’s mutability and storage policy. Generated or cache-like outputs should default to ignored, while hand-maintained and archived documents should default to tracked. Any exception must be explicit in the manifest and audited against both `.gitignore` and actual Git tracking. This directly prevents repositories from silently maintaining stale canonical copies at conflicting paths.

Decision: adopt one manifest-driven CRUD contract with category-specific mutability policies; route all creation through registered CLI or skill entry points, enforce generated-file integrity and canonical placement through `synlynk audit-docs`, automatically archive deletions, and derive `.gitignore` expectations from the manifest rather than configuring them independently per repository.

## Decision
Decision: adopt one manifest-driven CRUD contract with category-specific mutability policies; route all creation through registered CLI or skill entry points, enforce generated-file integrity and canonical placement through `synlynk audit-docs`, automatically archive deletions, and derive `.gitignore` expectations from the manifest rather than configuring them independently per repository.

> Signatures: see 2026-08-14-round-4-6-standardizing-crud-rules-and-t.json
