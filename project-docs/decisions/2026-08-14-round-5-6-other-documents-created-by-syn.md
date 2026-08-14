---
decision_id: dec-db17d160
topic: "ROUND 5/6 — Other documents created by synlynk commands (doctor/checkpoint/review/probe/decide etc.) — how to handle, standardize, and centralize them.

EVIDENCE — beyond the "big 4" doc categories already covered (project-docs, specs/plans, occasional docs, generated state.db views), synlynk itself has commands that write assorted output artifacts, each with its own ad hoc convention:
- `synlynk decide --record` → project-docs/decisions/<date>-<slug>.md + a companion JSON (this session's own brainstorm is generating 6 of these right now)
- `synlynk canon` (canon.py) → workspace-canon.md at repo ROOT (same tier as CLAUDE.md), gated behind first-time `synlynk start` FTUE flow — meaning already-onboarded repos (like synlynk itself) never get it generated, confirmed missing in this repo despite todo.md referencing it
- `synlynk exit` → SYNLYNK_HANDOFF.md (repo root)
- `synlynk repair` / `synlynk sync` — mutate existing files in place, no distinct output doc
- `synlynk doctor` / `synlynk probe` → write to state.db tables (harness_baselines, harness_records, etc.) + a "fence" comment block injected into CLAUDE.md/AGENTS.md/GEMINI.md (the `<!-- synlynk:harness -->` marker) — not a separate doc at all, but a mutation of the instruction files themselves
- `synlynk status --json` → stdout only, not persisted as a doc (Vizor's data contract per memory)
- docs/handoffs/ vs docs/superpowers/handoffs/ (synlynk repo) — two separate, undeduplicated directories, unclear which command(s) write to which
- Sentinel: sentinel.md — written by check_sentinel_patterns(), root-tier severity/ack file, not covered by any of Rounds 1-4's categories at all
- SYNLYNK_GUIDE.md, GEMINI.md, AI_INSTRUCTIONS.md, .cursorrules — near-duplicate instruction files written once at `init` and never kept in sync with each other or with CLAUDE.md afterward (no round has addressed instruction-file duplication directly, only doc duplication)

QUESTION: Given the manifest-driven CRUD contract decided in Round 4, and the canonical directory + naming standardization decided in Rounds 1-3, where should each of these command-generated artifacts land? Specifically: (1) should workspace-canon.md, SYNLYNK_HANDOFF.md, and sentinel.md move off repo-root into a single dedicated namespace (e.g. project-docs/_generated/ from Round 1) rather than sitting at root alongside CLAUDE.md, or does root placement serve a real purpose (max visibility to a human/agent opening the repo) that a subdirectory would lose? (2) how should the FTUE-gating problem be fixed so canon.md-style baseline artifacts get created/refreshed for already-onboarded repos, not just new ones — should `synlynk audit-docs` (Round 2) itself be the trigger that back-fills missing baseline artifacts on existing repos? (3) what should happen to the multi-instruction-file duplication problem (CLAUDE.md/GEMINI.md/AI_INSTRUCTIONS.md/.cursorrules/SYNLYNK_GUIDE.md) — should there be ONE canonical instruction source with the others generated/synced from it (and if so by which command), given this is structurally the same "proto-doc divergence" risk as Round 2 but for instruction files instead of content docs? (4) does sentinel.md belong in the doc-lifecycle manifest at all, or is it operational telemetry that should live in state.db like doctor/probe output rather than as a durable file?"
date: 2026-08-14
panel: [codex, grok]
status: approved
---

## Topic
ROUND 5/6 — Other documents created by synlynk commands (doctor/checkpoint/review/probe/decide etc.) — how to handle, standardize, and centralize them.

EVIDENCE — beyond the "big 4" doc categories already covered (project-docs, specs/plans, occasional docs, generated state.db views), synlynk itself has commands that write assorted output artifacts, each with its own ad hoc convention:
- `synlynk decide --record` → project-docs/decisions/<date>-<slug>.md + a companion JSON (this session's own brainstorm is generating 6 of these right now)
- `synlynk canon` (canon.py) → workspace-canon.md at repo ROOT (same tier as CLAUDE.md), gated behind first-time `synlynk start` FTUE flow — meaning already-onboarded repos (like synlynk itself) never get it generated, confirmed missing in this repo despite todo.md referencing it
- `synlynk exit` → SYNLYNK_HANDOFF.md (repo root)
- `synlynk repair` / `synlynk sync` — mutate existing files in place, no distinct output doc
- `synlynk doctor` / `synlynk probe` → write to state.db tables (harness_baselines, harness_records, etc.) + a "fence" comment block injected into CLAUDE.md/AGENTS.md/GEMINI.md (the `<!-- synlynk:harness -->` marker) — not a separate doc at all, but a mutation of the instruction files themselves
- `synlynk status --json` → stdout only, not persisted as a doc (Vizor's data contract per memory)
- docs/handoffs/ vs docs/superpowers/handoffs/ (synlynk repo) — two separate, undeduplicated directories, unclear which command(s) write to which
- Sentinel: sentinel.md — written by check_sentinel_patterns(), root-tier severity/ack file, not covered by any of Rounds 1-4's categories at all
- SYNLYNK_GUIDE.md, GEMINI.md, AI_INSTRUCTIONS.md, .cursorrules — near-duplicate instruction files written once at `init` and never kept in sync with each other or with CLAUDE.md afterward (no round has addressed instruction-file duplication directly, only doc duplication)

QUESTION: Given the manifest-driven CRUD contract decided in Round 4, and the canonical directory + naming standardization decided in Rounds 1-3, where should each of these command-generated artifacts land? Specifically: (1) should workspace-canon.md, SYNLYNK_HANDOFF.md, and sentinel.md move off repo-root into a single dedicated namespace (e.g. project-docs/_generated/ from Round 1) rather than sitting at root alongside CLAUDE.md, or does root placement serve a real purpose (max visibility to a human/agent opening the repo) that a subdirectory would lose? (2) how should the FTUE-gating problem be fixed so canon.md-style baseline artifacts get created/refreshed for already-onboarded repos, not just new ones — should `synlynk audit-docs` (Round 2) itself be the trigger that back-fills missing baseline artifacts on existing repos? (3) what should happen to the multi-instruction-file duplication problem (CLAUDE.md/GEMINI.md/AI_INSTRUCTIONS.md/.cursorrules/SYNLYNK_GUIDE.md) — should there be ONE canonical instruction source with the others generated/synced from it (and if so by which command), given this is structurally the same "proto-doc divergence" risk as Round 2 but for instruction files instead of content docs? (4) does sentinel.md belong in the doc-lifecycle manifest at all, or is it operational telemetry that should live in state.db like doctor/probe output rather than as a durable file?

## Panel Inputs

### codex
The manifest should distinguish durable documents, generated projections, and operational telemetry. Command output should not create new ad hoc root files. `workspace-canon.md` and `SYNLYNK_HANDOFF.md` should move to `project-docs/_generated/`, with manifest entries recording owner, generator, refresh policy, and whether manual edits are prohibited. Root placement offers visibility, but that is better handled through a short pointer or clearly named status output than by making generated files look authoritative beside human-maintained instruction files. A compatibility-period root shim could preserve existing workflows.

`audit-docs` should be the reconciliation trigger for existing repositories. It should detect missing or stale baseline artifacts, create them in dry-run/apply modes, and report provenance and drift. FTUE should remain responsible for initial setup, but artifact creation must become idempotent and callable independently by audit, repair, or an explicit refresh command. This avoids permanently stranded repos that completed onboarding before canon generation existed.

Instruction files need the same treatment as proto-docs. The manifest should designate one canonical, human-edited instruction source—preferably `CLAUDE.md` for this repository, or an explicit canonical path per project—and treat `AGENTS.md`, `GEMINI.md`, `AI_INSTRUCTIONS.md`, `.cursorrules`, and `SYNLYNK_GUIDE.md` as generated adapters. A dedicated `sync-instructions` operation, also invocable by `audit-docs --apply`, should regenerate them while preserving tool-specific wrappers and warning on manual edits. The fence mechanism should become one managed projection, not another independent source.

`sentinel.md` is different: its severity/ack semantics make it operational state, not a document. Its authoritative representation should move to state.db, with `status` or `doctor` exposing it. A root-level compatibility projection may remain temporarily for visibility, but it should not be lifecycle-managed as canonical content.

My position: centralize canon and handoff under `project-docs/_generated/`, make `audit-docs` the idempotent backfill/reconciliation path, establish one canonical instruction source with generated adapters, and move sentinel authority into state.db rather than the document manifest.

### grok
I'll gather how these command-generated artifacts are written today and what Rounds 1–4 already decided, then give a concrete placement recommendation.Prior rounds already split generated vs hand-maintained docs. Next I’ll check the actual write paths for canon, exit, sentinel, and instruction files.**Root is for harness contracts, not for every generated leftover.** Round 1 already made `project-docs/` the only human-facing docs namespace and reserved `.synlynk/` for tool state. Most of today’s command artifacts ignore that split.

| Artifact | Today | Land | Mutability |
|---|---|---|---|
| `workspace-canon.md` | repo root, FTUE-only | `project-docs/_generated/workspace-canon.md` | generated (hybrid notes optional) |
| `SYNLYNK_HANDOFF.md` | repo root after `exit` | **keep root** | generated-on-demand, ephemeral |
| `sentinel.md` | already `.synlynk/sentinel.md` (not root; CLAUDE.md is wrong) | stay under `.synlynk/`; source of truth → `state.db` | operational, gitignore |
| `decide --record` | `project-docs/decisions/` | keep that path; archive any `docs/decisions/` proto | hand-maintained + JSON companion |
| session handoffs | `docs/handoffs/` **and** `docs/superpowers/handoffs/` | Round 3: `docs/handoffs/` only | hand-maintained |
| doctor/probe | `state.db` + `<!-- synlynk:harness -->` fences | no extra markdown | instruction-section mutation |
| `status --json` | stdout | stay stdout | not a doc |

**Root placement is justified only when a consumer looks there by contract.** CLAUDE.md / GEMINI.md / AGENTS.md / `.cursorrules` must stay at root — that is how those harnesses load instructions. `SYNLYNK_HANDOFF.md` must stay at root because `exit` deletes `.synlynk/` (and optionally `project-docs/`); a leftover uninstall note buried in `_generated/` is useless. Canon and sentinel do not have that constraint. Canon is a scan receipt; parking it beside CLAUDE.md is why `todo.md` can claim a completed baseline that this repo never has.

**FTUE must not be the only writer.** `audit-docs` should *detect* missing registered artifacts (the Round 2 gap). It must not invent them — that would violate Round 4’s single `create_via`. `synlynk upgrade`, `doctor --fix`, and `audit-docs --fix` should invoke `synlynk canon` / `synlynk instructions update` whenever `.synlynk/config.json` exists. Onboarded repos are the common case; gating canon on `start` is a cold-start bug.

**Instruction files are the same proto-doc problem as Round 2.** Keep one authored body (role charters + lifecycle manifest + per-file content outside fences). `synlynk instructions update` is already the writer; make it the only one. Generate harness-specific files at root from that source. Treat `SYNLYNK_GUIDE.md` and `AI_INSTRUCTIONS.md` as proto-docs: archive or fold them, then fail audit if they drift. The `<!-- synlynk:harness -->` fence is a managed section, not a document.

**Sentinel is telemetry, not a durable doc.** Register it in the lifecycle manifest as operational state so audit knows the path is expected, but do not treat it like decisions or specs. Alerts belong in `state.db`; the markdown file is a disposable ack surface. Doctor/probe stay in the DB plus instruction fences.

**Position:** register every command artifact in the Round 4 manifest. Move canon off root into `project-docs/_generated/`. Keep only harness instruction filenames and `SYNLYNK_HANDOFF.md` at root. Back-fill via `audit-docs --fix` calling the registered creator, not via FTUE. Collapse instruction files to one source projected by `synlynk instructions update`. Put sentinel in `state.db` + `.synlynk/`, not in the durable-docs tree.

## Synthesis
The panel converges on a three-tier model in the Round 4 manifest:

- Durable, human-facing documents belong under `project-docs/`.
- Generated projections belong under `project-docs/_generated/`.
- Operational state belongs in `.synlynk/state.db`, with disposable filesystem projections only when needed.

`workspace-canon.md` should move to `project-docs/_generated/` and be generated idempotently. `SYNLYNK_HANDOFF.md` may remain at the repository root as a deliberate compatibility and visibility surface: `exit` needs to leave a discoverable handoff behind, especially when tool state or project documentation is removed. It should nevertheless be manifest-registered as generated, with provenance and refresh rules. A future root pointer could redirect to a canonical generated handoff if desired.

`audit-docs` should detect missing or stale baseline artifacts and support an explicit apply/fix mode that invokes each artifact’s registered creator. FTUE remains responsible for initial onboarding, but must no longer be the only path capable of creating canon or other baseline artifacts. Existing repositories should be repairable through `audit-docs --fix`, `upgrade`, or an equivalent explicit refresh command.

Instruction files should follow the same source/projection model as proto-docs. One configured file—`CLAUDE.md` for this repository, or an explicit manifest-defined source elsewhere—should be human-authored. `GEMINI.md`, `AGENTS.md`, `AI_INSTRUCTIONS.md`, `.cursorrules`, and `SYNLYNK_GUIDE.md` should either be generated adapters or explicitly retired/archived. A single `synlynk instructions update` operation should regenerate managed sections and adapters; `audit-docs --fix` may invoke it. Tool-specific wrappers remain allowed, but independently edited duplicate policy text should produce drift warnings.

`sentinel.md` should not be treated as a durable document. Its authoritative severity and acknowledgement state belongs in `state.db`, with `doctor`/`status` exposing it. A `.synlynk/` markdown projection may remain temporarily for operational visibility, but it should be gitignored, disposable, and classified in the manifest as operational state rather than lifecycle-managed content.

Decision: register all command-generated artifacts in the manifest, centralize canon under `project-docs/_generated/`, retain only the root instruction entry points and a compatibility-visible `SYNLYNK_HANDOFF.md`, make `audit-docs --fix` the idempotent backfill and reconciliation path, generate all secondary instruction files from one canonical source, and move sentinel authority into `state.db` with only a disposable `.synlynk/` projection.

## Decision
Decision: register all command-generated artifacts in the manifest, centralize canon under `project-docs/_generated/`, retain only the root instruction entry points and a compatibility-visible `SYNLYNK_HANDOFF.md`, make `audit-docs --fix` the idempotent backfill and reconciliation path, generate all secondary instruction files from one canonical source, and move sentinel authority into `state.db` with only a disposable `.synlynk/` projection.

> Signatures: see 2026-08-14-round-5-6-other-documents-created-by-syn.json
