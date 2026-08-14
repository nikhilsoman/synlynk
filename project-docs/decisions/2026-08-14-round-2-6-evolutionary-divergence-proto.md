---
decision_id: dec-cd322966
topic: "ROUND 2/6 — Evolutionary divergence: proto-docs superseded by canonical docs under different names.

EVIDENCE across 4 repos:
- rxcc: `docs/proposals/DOCUMENTATION_FRAMEWORK.md` is a meta-doc that explicitly describes "the five primary tracking documents" (roadmap/todo/rxcc_memory/devlog/rxcc_costs) but never mentions .synlynk/ or project-docs/ at all — it documents a scheme the repo has since partially moved away from, and nothing marks it as superseded.
- rxcc: two RCA conventions coexist — docs/rca/ (2 files, canonical per synlynk's own repo convention) and ~17 loose docs/claude-rca-*.md files at docs/ root that predate the docs/rca/ folder and were never migrated in.
- rxcc: ~90 loose agent-name-prefixed docs directly in docs/ root (claude-spec-*, claude-plan-*, gemini-*, agy-*, grok-*, codex-plan-*) — an older flat/prefixed naming scheme that predates and never migrated to the docs/superpowers/specs/ + docs/superpowers/plans/ convention synlynk itself and other repos now use.
- synlynk itself: TWO handoff directories exist — docs/handoffs/ (2 files, older) and docs/superpowers/handoffs/ (2 files, newer, superpowers-namespaced) — same content type, two locations, no migration or archive marker linking them.
- synlynk: top-level todo.md references "workspace-canon.md baseline generation (#874, merged 2026-08-09)" as a completed task, but workspace-canon.md does not exist anywhere in the repo (it's gated behind the synlynk start FTUE flow, which this already-onboarded repo never re-triggers) — the todo.md claim is now misleading/unverifiable without deep code archaeology.
- synlynk: devlogs/nikhil.md (774 lines) and devlogs/devlogs/nikhilsoman.md (418 lines) are BOTH actively updated with real, recent, non-overlapping content — an unrecognized username split that forked one person's devlog history into two files.
- cc-videoreframing: docs/archive/pre-synlynk-migration/{Backlog.md, Roadmap.md, devlog.md} are correctly frozen/archived legacy names from before synlynk adoption — this is the ONE clean example across all 4 repos of proto-docs being properly retired.

QUESTION: What causes docs to accumulate under old names/locations instead of being migrated or archived when a canonical replacement is introduced (naming convention changes, folder restructures, feature launches like workspace-canon.md, username/identity drift)? What tool-level mechanism (a `synlynk audit-docs` command? required migration step in synlynk upgrade? a doc-lifecycle manifest?) would have caught the todo.md/workspace-canon.md gap, the devlog username fork, and the docs/handoffs duplication automatically instead of requiring a manual investigation to surface them? Use cc-videoreframing's pre-synlynk-migration/ archive as the one working example of "done right" and generalize it into a repeatable pattern."
date: 2026-08-14
panel: [codex, grok]
status: approved
---

## Topic
ROUND 2/6 — Evolutionary divergence: proto-docs superseded by canonical docs under different names.

EVIDENCE across 4 repos:
- rxcc: `docs/proposals/DOCUMENTATION_FRAMEWORK.md` is a meta-doc that explicitly describes "the five primary tracking documents" (roadmap/todo/rxcc_memory/devlog/rxcc_costs) but never mentions .synlynk/ or project-docs/ at all — it documents a scheme the repo has since partially moved away from, and nothing marks it as superseded.
- rxcc: two RCA conventions coexist — docs/rca/ (2 files, canonical per synlynk's own repo convention) and ~17 loose docs/claude-rca-*.md files at docs/ root that predate the docs/rca/ folder and were never migrated in.
- rxcc: ~90 loose agent-name-prefixed docs directly in docs/ root (claude-spec-*, claude-plan-*, gemini-*, agy-*, grok-*, codex-plan-*) — an older flat/prefixed naming scheme that predates and never migrated to the docs/superpowers/specs/ + docs/superpowers/plans/ convention synlynk itself and other repos now use.
- synlynk itself: TWO handoff directories exist — docs/handoffs/ (2 files, older) and docs/superpowers/handoffs/ (2 files, newer, superpowers-namespaced) — same content type, two locations, no migration or archive marker linking them.
- synlynk: top-level todo.md references "workspace-canon.md baseline generation (#874, merged 2026-08-09)" as a completed task, but workspace-canon.md does not exist anywhere in the repo (it's gated behind the synlynk start FTUE flow, which this already-onboarded repo never re-triggers) — the todo.md claim is now misleading/unverifiable without deep code archaeology.
- synlynk: devlogs/nikhil.md (774 lines) and devlogs/devlogs/nikhilsoman.md (418 lines) are BOTH actively updated with real, recent, non-overlapping content — an unrecognized username split that forked one person's devlog history into two files.
- cc-videoreframing: docs/archive/pre-synlynk-migration/{Backlog.md, Roadmap.md, devlog.md} are correctly frozen/archived legacy names from before synlynk adoption — this is the ONE clean example across all 4 repos of proto-docs being properly retired.

QUESTION: What causes docs to accumulate under old names/locations instead of being migrated or archived when a canonical replacement is introduced (naming convention changes, folder restructures, feature launches like workspace-canon.md, username/identity drift)? What tool-level mechanism (a `synlynk audit-docs` command? required migration step in synlynk upgrade? a doc-lifecycle manifest?) would have caught the todo.md/workspace-canon.md gap, the devlog username fork, and the docs/handoffs duplication automatically instead of requiring a manual investigation to surface them? Use cc-videoreframing's pre-synlynk-migration/ archive as the one working example of "done right" and generalize it into a repeatable pattern.

## Panel Inputs

### codex
Docs accumulate under old names because introducing a canonical replacement usually changes creation behavior, not historical state. New tooling writes to the new path, while old files remain valid-looking, unowned, and discoverable. Without explicit migration ownership, authors do not know whether to move, archive, redirect, or preserve them. Folder restructures create parallel conventions; identity drift forks per-user logs; feature launches can leave references to generated or gated artifacts that are not present in the checked-out repository. The absence of lifecycle metadata turns these into silent inconsistencies rather than actionable failures.

The strongest pattern is cc-videoreframing’s `docs/archive/pre-synlynk-migration/`: legacy names remain available for history, but are clearly frozen, grouped, and semantically separated from active documentation. That pattern should become mandatory whenever a canonical document supersedes an older one: record the replacement, migration status, owner, and archive location, and add a redirect or explanatory marker where practical.

I recommend a versioned doc-lifecycle manifest, validated by a new `synlynk audit-docs` command and run during `synlynk upgrade` and CI. The manifest should declare canonical patterns, aliases/superseded paths, archive policy, identity mappings, and expected generated artifacts. The audit should detect:

- references to missing canonical files, such as `todo.md` → `workspace-canon.md`;
- duplicate semantic locations, such as both handoff directories;
- legacy naming patterns outside declared archives;
- divergent identity variants, such as `nikhil.md` and `nikhilsoman.md`;
- active files that lack ownership or lifecycle status.

Each finding should be classified as migrate, archive, merge, redirect, or intentional exception, with a machine-readable baseline committed to the repo. `audit-docs --fix` could create archive markers and migration stubs, but merges should require human review.

My position: adopt the manifest plus audit as the default control, and make upgrade validation require lifecycle decisions for detected legacy docs. The archive convention is the proven foundation; automation should make “done right” repeatable rather than dependent on archaeology.

### grok
I'll inspect the cited proto-docs, archive pattern, and current naming so the recommendation is grounded in what the four repos actually contain.**Cause.** New conventions replace old ones only in *instructions for future writes*. Agents follow the newest path (`docs/rca/`, `docs/superpowers/{specs,plans,handoffs}/`, `project-docs/`). They do not get a job to move, stub, or stamp what already exists. So proto-docs stay live and discoverable: `DOCUMENTATION_FRAMEWORK.md` still reads as current; `docs/handoffs/` and `docs/superpowers/handoffs/` both look valid; `claude-spec-*` sits next to the superpowers tree with no successor pointer.

Two other failure modes sit beside that. **Claimed artifacts are not existence-checked.** Completing the PR that *implements* `workspace-canon.md` is marked `[x]` in `todo.md`, but the file is produced only by `synlynk start` on a cold-start path this repo never re-runs. **Identity is a filename string, not a person.** Devlog paths are `project-docs/devlogs/<git user.name>.md`. `nikhil` and `nikhilsoman` are two keys for one human, so history forks and both files stay hot.

cc-videoreframing is the exception because migration was a discrete event: old names were *moved* into `docs/archive/pre-synlynk-migration/` and left frozen. No new writes land there. That is not how convention changes usually ship.

**Mechanism.** A standalone `synlynk audit-docs` would only find drift if someone runs it. The missing primitive is a committed **doc-lifecycle manifest** (role → canonical path → superseded globs → status: `canonical` | `archived` | `generated-on-demand`). Generalize the videoreframing pattern:

1. New convention lands with a manifest delta.
2. `synlynk upgrade` *must* migrate: move matches under `docs/archive/<reason>/`, leave a stub or INDEX pointer, stamp `superseded-by:` on the archive, refuse new writes to the old path.
3. `synlynk audit-docs` (also on `pr check` / `status`) fails on: files matching superseded globs still outside archive; two live dirs for one role; todo/roadmap claims of files that are neither present nor `generated-on-demand`; multiple devlog stems that alias one identity.

That would have caught `todo.md` vs missing `workspace-canon.md`, the `nikhil`/`nikhilsoman` fork, and the dual handoff trees without a manual census.

**Position.** Do not treat archive as folklore. Ship a lifecycle manifest as the source of truth, make `upgrade` the migrator, and make `audit-docs` the continuous gate. Detection without a required move-and-stamp step will just grow another unread report.

## Synthesis
Documentation accumulates under old names because convention changes update future writes without reconciling historical files. Migrations lack an explicit owner, status, replacement pointer, and enforcement boundary; generated or gated artifacts are treated as completed merely because implementation work shipped; and identity is often encoded as a filename, allowing aliases such as `nikhil` and `nikhilsoman` to fork history. Parallel locations therefore remain equally plausible, active, and undiscoverable without manual archaeology.

The repeatable pattern is the one used by `cc-videoreframing`: move superseded documents into a clearly named, frozen archive such as `docs/archive/pre-synlynk-migration/`, preserve their history, and record what replaced them. Every new canonical convention should ship with a lifecycle update that classifies old paths as migrated, archived, merged, redirected, generated-on-demand, or intentional exceptions.

The control mechanism should be a committed, versioned doc-lifecycle manifest backed by `synlynk audit-docs`. The audit should run in CI, `synlynk pr check`, and as part of `synlynk upgrade`; upgrades should require lifecycle decisions and perform safe archive/redirect scaffolding where possible. It should detect missing referenced artifacts such as `todo.md` → `workspace-canon.md`, duplicate live locations such as the two handoff directories, legacy files outside declared archives, identity aliases producing multiple active devlogs, and active documents lacking ownership or lifecycle status. Automatic fixes may move files or create markers, but merges and identity resolution should require human confirmation.

**Decision: Adopt the lifecycle manifest as the source of truth, make `synlynk upgrade` the required migration checkpoint, and make `synlynk audit-docs` the continuous enforcement tool. The `cc-videoreframing` archive pattern becomes the standard completion state for superseded documentation.**

## Decision
**Decision: Adopt the lifecycle manifest as the source of truth, make `synlynk upgrade` the required migration checkpoint, and make `synlynk audit-docs` the continuous enforcement tool. The `cc-videoreframing` archive pattern becomes the standard completion state for superseded documentation.**

> Signatures: see 2026-08-14-round-2-6-evolutionary-divergence-proto.json
