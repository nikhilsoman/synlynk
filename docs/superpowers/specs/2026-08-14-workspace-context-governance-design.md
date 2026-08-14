# Workspace Context Governance — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to turn this spec into an implementation plan before any code is written. Per Brainstorm-First Policy, no implementation may begin until this spec is committed and Nikhil signs off.

**Origin:** gh:#936 and the broader pattern of workspace context drift observed across all four active synlynk-managed repos (synlynk, rxcc, cc-videoreframing, playblazer-ng).

**Goal (as stated by the user):** achieve total dependability of every item of context that the workspace requires — from creation, through hand-maintained or generated updates, to rotation/archive/reference/storage/retrieval — across single-repo, Team, and Enterprise deployments.

**Method:** a 6-round `synlynk decide --panel codex,grok --record` sequence, one round per investigation aspect, each grounded in a structured cross-repo evidence survey (3 parallel read-only Explore agents on rxcc/cc-videoreframing/playblazer-ng, plus direct investigation of synlynk itself). All 6 raw decision records are committed at `project-docs/decisions/2026-08-14-round-{1..6}-*.md` (+ companion `.json`) and are the primary source for this synthesis — this document does not restate their full reasoning, only the converged design and the resulting action items.

---

## 1. Investigation findings (what's actually broken)

Concrete, repo-specific evidence gathered before any decide round:

- **synlynk vs. cc-videoreframing have exactly inverted conventions** for which of two `project-docs/`-style locations is canonical — and cc-videoreframing's own CLAUDE.md / `.synlynk/config.json` still reference the wrong (stale) path. This is a live, currently-broken reference, not a historical artifact.
- **rxcc** uses a third pattern entirely: a symlink farm pointing at root-level files, plus a redundant, un-symlinked `.synlynk/project-docs/` copy, and evidence of a fully reverted `state.db`-canonical migration attempt.
- **playblazer-ng** has a live, actively-diverging duplicate `roadmap.md` at both repo root and `project-docs/`.
- Only **cc-videoreframing's `docs/archive/pre-synlynk-migration/`** represents a clean, correctly executed doc-retirement pattern across all 4 repos.
- **synlynk itself**: two forked devlogs (`project-docs/devlogs/nikhil.md`, 774 lines, vs. `nikhilsoman.md`, 418 lines) — both real, both actively updated, forked purely on a git-identity mismatch. `workspace-canon.md` is referenced in `todo.md` as generated but does not exist, because `canon.py`'s `run_canon_baseline()` is gated behind the first-time `synlynk start` flow and synlynk itself was already onboarded before that gate existed. Two undeduplicated handoff directories (`docs/handoffs/` and `docs/superpowers/handoffs/`) coexist with no clear ownership split.
- **`docs/superpowers/specs/` and `docs/superpowers/plans/`** are the *only* convention that survived independent evolution across all 4 repos — because the path is skill-injected at time-of-use, not asserted as static CLAUDE.md prose the agent must remember to consult. Every other category (RCA, blog, archive, strategy, research, brainstorm, decisions, handoffs) has a different ad hoc location and population level per repo, and the Blog Post Protocol (a global, all-projects CLAUDE.md rule) is failing 1:1 PR-to-post compliance in 3 of 4 repos.
- The rules governing doc lifecycle today live in at least 5 disconnected, non-enforcing places: CLAUDE.md prose, auto-generated-file headers ("do NOT hand-edit," unenforced), partial CLI coverage (`synlynk migrate`/`story`/`roadmap add`), inconsistent `.gitignore` usage, and skill injection (the only one that actually works).

## 2. Converged design (Rounds 1–5 — single-repo scope)

**R1 — Canonical location.** Hardcode `project-docs/` at repo root as the sole canonical namespace for hand-maintained content. Structurally separate state-derived/generated output under `project-docs/_generated/`. Eliminate `project_docs_dir` as free-form config. Forbid a second `.synlynk/project-docs/` tree. Migration is inventory-first and quarantine-preserving (`project-docs/.migration-conflicts/<timestamp>/`) — never silently picks a winner between two conflicting canonical copies.

**R2 — Evolutionary divergence / proto-docs.** Generalize cc-videoreframing's `docs/archive/pre-synlynk-migration/` pattern into a repeatable standard, backed by a new **`synlynk audit-docs`** command that runs in CI, in `synlynk pr check`, and as a required `synlynk upgrade` checkpoint. Driven by a committed, versioned **doc-lifecycle manifest** that classifies every doc path as migrated / archived / merged / redirected / generated-on-demand / intentional-exception. Auto-fix safe cases; require human confirmation for merges or identity resolution.

**R3 — Occasional-document categories.** Standardize `rca/`, `archive/`, `decisions/`, `handoffs/`, `brainstorm/`, `blog/` under fixed `docs/` paths via the same skill-injection pattern that made `docs/superpowers/` stick (not just CLAUDE.md prose). Leave `strategy/`, `research/`, `papers/`, `ux-prompts/`, and generic `reports/` repo-specific — they reflect real domain differences, not drift. Replace the failing 1:1 Blog Post Protocol with a trigger-based release-communication workflow: a post is required for externally meaningful releases or thematic PR batches, a scaffold command is provided, and a PR must carry an explicit "no blog needed" declaration otherwise.

**R4 — Unified CRUD contract.** One manifest-driven CRUD contract, extending R1/R2's manifest, covering *all* doc types (generated and hand-maintained) rather than splitting into separate systems. Each registered type declares: canonical identifier/path, authoritative backend (file / `state.db` / other), sole `create_via` command or skill trigger, mutability (`generated` / `hand-maintained` / `append-only`/`hybrid`), read/update behavior, required metadata, and archive/delete policy (archive-not-delete is automatic, not disciplinary). `.gitignore` status is **derived** from the manifest's mutability/storage flag, not set independently per repo — this directly prevents the cc-videoreframing-style stale-tracked-copy bug.

**R5 — Command-generated artifacts.** Three-tier model: durable human-facing docs under `project-docs/`; generated projections under `project-docs/_generated/`; operational state in `.synlynk/state.db` with disposable filesystem projections only where needed. `workspace-canon.md` moves to `project-docs/_generated/` and is generated idempotently. `SYNLYNK_HANDOFF.md` stays at repo root as a deliberate compatibility/visibility surface but is manifest-registered as generated. `audit-docs` gains a `--fix` mode that can backfill missing baseline artifacts (fixing the FTUE-gating problem) and is invoked from `upgrade` as well as first-run. Instruction-file duplication (CLAUDE.md/GEMINI.md/AI_INSTRUCTIONS.md/.cursorrules/SYNLYNK_GUIDE.md) gets the same source/projection treatment: one human-authored source per repo, the rest generated adapters or explicitly retired, regenerated via a new `synlynk instructions update` command that `audit-docs --fix` can invoke. `sentinel.md`'s authoritative state moves into `state.db`; any filesystem copy is a disposable, gitignored projection, not a lifecycle-managed document.

## 3. Team / Enterprise trajectory (Round 6)

The design above assumes a closed, single-operator repo. It doesn't survive team mode unmodified — and this session found the live proof: the `nikhil.md`/`nikhilsoman.md` devlog fork is the *same class of drift* this whole brainstorm targets, one dimension earlier (identity) than the location dimension R1–R5 addressed.

Converged decisions:

- The manifest's `create_via` contract must govern identity resolution, authorization, and path derivation — not just select a local function. Sharded categories (like devlogs) are keyed by a stable `member_id` via an explicit identity registry with aliases; runtime git/GitHub usernames must never directly determine a filename. Unregistered/ambiguous identities fail loudly rather than silently forking a new file.
- The lifecycle manifest stays a **committed, unsigned, non-relayed** workspace policy artifact in v0.13.x — git already distributes it clone-wide, and signing now would create competing authority against v1.0's capability ledger. But its schema should be made forward-compatible now: stable `manifest_id`, schema version, category IDs, workspace/repo identity, revision + parent-revision hash, actor/member identity, additive sharding metadata. Writes should detect stale revisions and emit conflict artifacts rather than silently overwrite.
- `audit-docs` should **not** implement org-wide rollup yet, but should emit stable, machine-readable audit snapshots (repo/workspace identity, manifest revision, category IDs, violation codes, status vocabulary, provenance) now, so a future Enterprise governance agent has a rollup seam without coupling the single-repo tool to Enterprise infra prematurely.

**Highest-leverage v0.13.x action (per the panel):** implement one end-to-end vertical slice — committed manifest identity registry + canonical member-ID devlog paths + alias/fork detection and provenance-preserving reconciliation via `audit-docs --fix` + revision-aware writes + stable machine-readable audit output enforced in CI/`pr check`. This closes the live identity fork while hardening the location, concurrency, Team, and future-Enterprise integration points simultaneously.

## 4. Action items (not yet scoped into a plan)

These require a follow-up `superpowers:writing-plans` pass before any implementation — this spec documents *what* was decided, not task-by-task *how*:

1. Define and commit the doc-lifecycle manifest schema (R1/R2/R4/R6 — schema fields listed above).
2. Build `synlynk audit-docs` (report mode first, then `--fix`), wired into CI, `pr check`, and `upgrade`.
3. Migrate `project-docs/` across all 4 repos to the canonical layout (R1), using the quarantine-preserving migration path — start with synlynk itself (devlog fork, dual handoffs dirs, missing `workspace-canon.md`) as the pilot.
4. Skill-inject the R3 fixed-path convention for `rca/archive/decisions/handoffs/brainstorm/blog`.
5. Replace the Blog Post Protocol in the global CLAUDE.md with the trigger-based workflow (R3) — this is a `~/.claude/CLAUDE.md` edit, out of band from any single repo's PR.
6. Build `synlynk instructions update` and retire/adapt the redundant instruction files.
7. Design the manifest identity registry + `member_id` sharding for devlogs, and use it to reconcile the `nikhil`/`nikhilsoman` fork as the first real test case.
8. Move `sentinel.md` authority into `state.db`.

## 5. Open items carried forward (not part of this brainstorm)

- PR #944 (issue #936-adjacent taxonomy-doc-sync fix) is still blocked — its docs-regen follow-up (job-7b032978) failed with `TASK_DELIVERY_FAILED` and has not yet been re-diagnosed. This is unrelated to the governance design above and should be resolved independently.

---

**Decision records (full panel reasoning):**
- `project-docs/decisions/2026-08-14-round-1-6-uniform-location-of-core-conte.md`
- `project-docs/decisions/2026-08-14-round-2-6-evolutionary-divergence-proto.md`
- `project-docs/decisions/2026-08-14-round-3-6-where-specs-plans-strategy-doc.md`
- `project-docs/decisions/2026-08-14-round-4-6-standardizing-crud-rules-and-t.md`
- `project-docs/decisions/2026-08-14-round-5-6-other-documents-created-by-syn.md`
- `project-docs/decisions/2026-08-14-round-6-6-impact-of-team-enterprise-vers.md`
