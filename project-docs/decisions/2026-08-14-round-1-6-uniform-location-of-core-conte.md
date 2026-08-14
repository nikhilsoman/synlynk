---
decision_id: dec-3f3a58fe
topic: "ROUND 1/6 — Uniform location of core context docs across synlynk-managed repos.

EVIDENCE across 4 repos (synlynk, rxcc, playblazer-ng, cc-videoreframing), all using the same synlynk CLI:
- synlynk: TWO project-docs trees exist simultaneously — top-level project-docs/ (git-tracked, hand-maintained: decisions/, devlogs/, memory.md, todo.md, reports/) AND .synlynk/project-docs/ (gitignored, auto-generated from state.db, stale placeholder content like "Story one [backend]").
- cc-videoreframing: the EXACT INVERSE — root project-docs/ is gitignored and stale, .synlynk/project-docs/ is git-tracked and actively updated. Worse: CLAUDE.md and .synlynk/config.json's project_docs_dir setting still point at the stale gitignored root path — a live broken reference in production docs.
- rxcc: neither pattern — project-docs/ contains five FILES THAT ARE SYMLINKS to root-level files (roadmap.md, todo.md, devlog.md, rxcc_memory.md, rxcc_costs.md), and there's ALSO a separate, un-symlinked .synlynk/project-docs/ copy of the same doc set.
- playblazer-ng: project-docs/roadmap.md AND root roadmap.md both exist, byte-identical at init but now diverged (root has 9 uncommitted local edits not in project-docs/ copy).
- .synlynk/config.json's project_docs_dir key exists and is configurable per-repo, meaning the tool itself permits arbitrary divergence rather than enforcing one location.

QUESTION: What should be the single canonical, tool-enforced location and directory structure for core context docs (roadmap/todo/memory/costs/devlogs/decisions), across a fleet of independently-evolved repos, such that a developer or agent landing in ANY of the 4 repos can predict the path without checking config first? Consider: should project_docs_dir remain configurable at all, or should synlynk collapse to one hardcoded convention repo-wide? Should the generated (state.db-derived) markdown and the hand-maintained markdown live in the same directory or be structurally separated so they can never be confused? Recommend a specific target layout and a migration mechanism that doesn't silently orphan any repo's existing content."
date: 2026-08-14
panel: [codex, grok]
status: approved
---

## Topic
ROUND 1/6 — Uniform location of core context docs across synlynk-managed repos.

EVIDENCE across 4 repos (synlynk, rxcc, playblazer-ng, cc-videoreframing), all using the same synlynk CLI:
- synlynk: TWO project-docs trees exist simultaneously — top-level project-docs/ (git-tracked, hand-maintained: decisions/, devlogs/, memory.md, todo.md, reports/) AND .synlynk/project-docs/ (gitignored, auto-generated from state.db, stale placeholder content like "Story one [backend]").
- cc-videoreframing: the EXACT INVERSE — root project-docs/ is gitignored and stale, .synlynk/project-docs/ is git-tracked and actively updated. Worse: CLAUDE.md and .synlynk/config.json's project_docs_dir setting still point at the stale gitignored root path — a live broken reference in production docs.
- rxcc: neither pattern — project-docs/ contains five FILES THAT ARE SYMLINKS to root-level files (roadmap.md, todo.md, devlog.md, rxcc_memory.md, rxcc_costs.md), and there's ALSO a separate, un-symlinked .synlynk/project-docs/ copy of the same doc set.
- playblazer-ng: project-docs/roadmap.md AND root roadmap.md both exist, byte-identical at init but now diverged (root has 9 uncommitted local edits not in project-docs/ copy).
- .synlynk/config.json's project_docs_dir key exists and is configurable per-repo, meaning the tool itself permits arbitrary divergence rather than enforcing one location.

QUESTION: What should be the single canonical, tool-enforced location and directory structure for core context docs (roadmap/todo/memory/costs/devlogs/decisions), across a fleet of independently-evolved repos, such that a developer or agent landing in ANY of the 4 repos can predict the path without checking config first? Consider: should project_docs_dir remain configurable at all, or should synlynk collapse to one hardcoded convention repo-wide? Should the generated (state.db-derived) markdown and the hand-maintained markdown live in the same directory or be structurally separated so they can never be confused? Recommend a specific target layout and a migration mechanism that doesn't silently orphan any repo's existing content.

## Panel Inputs

### codex
The fleet’s failure is not merely inconsistent naming; it is competing ownership models. A configurable `project_docs_dir` lets each repository drift, while symlinks and duplicated snapshots create ambiguity about which file an agent should trust. Hidden `.synlynk/project-docs/` is also a poor human-facing canonical location because it is easy to overlook and, in some repos, gitignored.

The canonical convention should be a fixed, repository-root `project-docs/` directory. `project_docs_dir` should no longer be freely configurable; the CLI should resolve it deterministically to `./project-docs`, optionally accepting the setting only when it exactly matches that value. The directory should have explicit ownership boundaries:

```text
project-docs/
  roadmap.md
  todo.md
  memory.md
  costs.md
  devlogs/
  decisions/
  _generated/
    ...
```

The files and subdirectories at the top level are hand-maintained, reviewable context. `project-docs/_generated/` contains state.db-derived markdown, is clearly marked as generated, and should normally be gitignored or committed only under an explicit repository policy. Generated content must never share filenames with hand-maintained documents. The CLI should read hand-maintained files as authoritative and treat generated output as supporting/derived material.

Migration must be inventory-first and lossless. For each repository, the CLI should enumerate root files, nested files, symlinks (resolving their targets), `.synlynk/project-docs/` content, configured paths, git state, and byte/content differences. It should write a migration report and copy—not delete—each source into a deterministic destination, preserving conflicting versions under `_migration-conflicts/<timestamp>/` with provenance metadata. Symlinks should become canonical regular files unless the target is already the canonical file. Activation should require an explicit confirmation or clean, automatically verifiable merge; only afterward may obsolete paths be removed.

My position: hardcode `project-docs/` as the sole canonical namespace, structurally separate manual and generated content beneath it, and make migration conservative, auditable, and non-destructive.

### grok
I'll inspect how the four repos actually store context docs and how synlynk resolves `project_docs_dir`, then give a concrete layout recommendation.The four-repo split is not a docs-taste problem. It is two code paths writing two trees: `_docs_dir()` honors `project_docs_dir` (default `project-docs/`), while `_synlynk_project_docs_dir()` hardcodes `.synlynk/project-docs` after migrate. Configurability plus a second implicit tree is why every repo invented a different “truth.”

**Canonical location:** repo-root `project-docs/`, always. No `project_docs_dir`. An agent landing in any fleet repo should open `project-docs/roadmap.md` (and siblings) without reading config, CLAUDE.md, or `.gitignore`. Root-level `roadmap.md` / `todo.md` become aliases only via one-way pointers or a doctor error, never a second live copy.

**Directory (tool-enforced):**

```
project-docs/
  roadmap.md      # DB-backed view, banner: generated
  todo.md
  memory.md
  costs.md
  devlogs/        # hand-maintained
  decisions/      # hand-maintained
  reports/        # hand-maintained
.synlynk/         # tool state only: config, state.db, telemetry, jobs
                  # NO project-docs/ here
```

Generated markdown and hand-maintained markdown can share `project-docs/` **only** if regenerate never touches `devlogs/`, `decisions/`, or `reports/`, and every DB view carries a machine-readable `<!-- synlynk:generated -->` header. Do **not** keep a second generated tree under `.synlynk/`. That is the confusion the fleet already has. `state.db` is the write-canonical store; `project-docs/*.md` is the only read surface.

Drop `project_docs_dir`. A per-repo knob that exists to paper over layout disagreement is how cc-videoreframing ended up with CLAUDE.md pointing at a gitignored stale root.

**Migration (`synlynk docs unify`, fail-closed):**

1. Inventory `project-docs/`, `.synlynk/project-docs/`, root twins, and symlink targets.
2. Per logical file, pick the newest non-placeholder content (reject “Story one [backend]”).
3. Write the winner into `project-docs/`; copy every loser into `project-docs/.migration-quarantine/<source>/` (git-tracked until reviewed). Never delete silently.
4. Materialize rxcc-style symlinks into real files in `project-docs/`; leave originals as stubs that say “moved.”
5. For playblazer-ng divergence, quarantine both sides if hashes differ; do not auto-merge.
6. Rewrite config / CLAUDE.md / agent instruction files to `project-docs/`.
7. Remove `.synlynk/project-docs`. `init`/`exec`/`status` error if both trees still exist.

**Position:** Hardcode `project-docs/` as the single fleet-wide read location; keep `state.db` as the write store for roadmap/todo/memory/costs; structurally forbid `.synlynk/project-docs`; delete `project_docs_dir`; migrate with quarantine, never overwrite. Predictability beats per-repo taste.

## Synthesis
The panel agrees on the core remedy: the fleet needs one predictable namespace and one ownership model. The conflicting trees are caused by both configurable paths and an implicit `.synlynk/project-docs/` path, so configuration cannot remain an unrestricted escape hatch.

Recommended target layout:

```text
project-docs/
  roadmap.md
  todo.md
  memory.md
  costs.md
  devlogs/
  decisions/
  reports/
  _generated/
    ...
.synlynk/
  config.json
  state.db
  ...
```

`project-docs/` is always relative to the repository root and is the only human-facing documentation namespace. The top-level files and directories are hand-maintained, reviewable context. State-derived markdown belongs exclusively under `project-docs/_generated/`, with generated markers and distinct filenames. It must never overwrite or share a filename with hand-maintained content. `.synlynk/` contains tool state only and must not contain a second docs tree.

`project_docs_dir` should be removed as a free-form setting. During a compatibility period, the CLI may accept it only if its value is exactly `project-docs`; any other value should produce a migration error. All commands, templates, generated instructions, and documentation should resolve the canonical path internally.

Migration should be an explicit, lossless operation:

1. Inventory root documents, `project-docs/`, `.synlynk/project-docs/`, configured paths, symlinks and their targets, Git status, and content hashes.
2. Produce a migration report before changing files.
3. Copy content into the canonical layout; materialize symlinks as regular files.
4. Preserve every conflicting version under a tracked quarantine such as `project-docs/.migration-conflicts/<timestamp>/`, with source path, hash, and provenance metadata.
5. Never choose a winner solely by modification time or placeholder detection. Automatic merging is allowed only when equivalence is mechanically verifiable.
6. Rewrite references such as `CLAUDE.md` and configuration.
7. Fail closed until conflicts are reviewed and explicitly acknowledged; only then remove obsolete trees or stubs.

This preserves divergent playblazer content, rxcc symlink targets, and cc-videoreframing’s tracked hidden-tree documents without silently orphaning anything.

Decision: hardcode repository-root `project-docs/` as the sole canonical documentation namespace, structurally separate hand-maintained documents from state-derived output under `_generated/`, eliminate arbitrary `project_docs_dir` configurability, forbid `.synlynk/project-docs/`, and migrate existing repositories through an inventory-first, quarantine-preserving, fail-closed process.

## Decision
Decision: hardcode repository-root `project-docs/` as the sole canonical documentation namespace, structurally separate hand-maintained documents from state-derived output under `_generated/`, eliminate arbitrary `project_docs_dir` configurability, forbid `.synlynk/project-docs/`, and migrate existing repositories through an inventory-first, quarantine-preserving, fail-closed process.

> Signatures: see 2026-08-14-round-1-6-uniform-location-of-core-conte.json
