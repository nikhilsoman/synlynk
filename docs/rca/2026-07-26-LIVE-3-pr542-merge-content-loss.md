# [LIVE-3] PR #542 merge-conflict resolution deleted untracked-regeneration content from `main`

- **Severity:** Sev1 (data loss/corruption, per global Live Issues SOP)
- **Issue:** https://github.com/nikhilsoman/synlynk/issues/547
- **Detected:** 2026-07-26, during a post-merge ground-truth double-check of PR #542
- **Status:** Root cause confirmed; recovery PR in progress

## Timeline

- **2026-07-25** — PR #542 ("State Engine PR1: DB-canonicalize roadmap/memory/costs + migrate self") opened against `main` at `c34e2eb`. Task 7 of the underlying plan had already run a live `synlynk migrate` against this repo, deleting the root `project-docs/roadmap.md`/`memory.md`/`costs.md`/`todo.md` in favor of DB-backed regeneration.
- **2026-07-25/26** — While PR #542 awaited non-authoring review, PRs #537/#539/#540/#541 merged into `main`, each touching files under `project-docs/` (new decision docs, devlog entries, a cost-capability report). PR #542 drifted into `CONFLICTING`/`DIRTY` state.
- **2026-07-26** — Per the repo's #426 GitHub-write routing policy, review/merge was dispatched to Grok (after two misrouted Codex attempts that correctly refused due to no `api.github.com` network egress in Codex's sandbox — a distinct, already-understood, non-Sev1 issue). Grok resolved the conflict, reported the review, and merged. Grok's summary stated it "preserved main's newer content... under `.synlynk/project-docs/`" while keeping PR1's deletion of the root `project-docs/` tree.
- **2026-07-26 (later)** — Ground-truth double-check of the merge (`git diff --stat c34e2eb..db9a652 -- 'project-docs/'`) found the preservation claim does not hold as a git-tracked fact. This RCA and issue #547 were filed as a result.

## Root cause

PR #542's own scope (DB-canonicalization of `roadmap.md`/`memory.md`/`costs.md`/`todo.md`) only ever intended to delete files that have a corresponding regeneration path in `state.db`. But the merge-conflict resolution treated deletion of the entire `project-docs/` directory as a single unit, rather than diffing file-by-file against what PR1 actually migrates. This silently swept in files that:

1. Were added to `project-docs/` by unrelated, later-merged PRs (#537/#539/#540/#541) during PR #542's review window, and
2. Have **no database-backed regeneration mechanism anywhere in the codebase** — confirmed via `grep -n "decisions_table|repo_evaluation|CREATE TABLE.*decision" synlynk/db.py` returning zero matches.

`_migrate_import()` (`synlynk/db.py`, ~line 889) only imports `memory.md` → `memory_entries`, `roadmap.md` → `roadmap_arcs`/`roadmap_phases`, and `devlogs/*.md` → `devlog_entries`. It has never had an import path for `decisions/*.json`, `repo-evaluation-report.md`, or `reports/*.md`. These files were always meant to be plain git-tracked content, not migrate/DB-canonicalization targets — but the merge treated them as if they were in scope for deletion alongside the genuinely DB-backed files.

Contributing factor: Grok's own job sub-worktree (`worktrees/job-a9ae649d/.synlynk/`) contains no `project-docs/` directory at all, meaning the claimed local preservation step was never actually executed as described (or was executed somewhere that left no trace) — the review's self-report was not independently verified against git ground truth before merging, which is exactly the failure mode the standing "never trust job status alone" project practice exists to catch, applied here to a review/merge job's self-report rather than an implementation job's.

## Impact

17 files / 2161 lines deleted from `project-docs/` between `c34e2eb` (pre-merge `main`) and `db9a652` (the squash-merge commit). Of these:

**Intentional, safe (DB-backed, regenerates from `state.db`):**
- `roadmap.md`, `todo.md`, `costs.md`, `.synlynk_config.json`

**Unintentional, no regeneration path — the actual data loss:**
- `project-docs/decisions/2026-07-18-before-a-week-of-intensive-multi-agent-d.{json,md}`
- `project-docs/decisions/2026-07-23-should-synlynk-formally-wire-every-user.{json,md}`
- `project-docs/decisions/2026-07-25-should-synlynk-implement-per-role-github.{json,md}`
- `project-docs/devlogs/README.md`, `agy.md`, `nikhil.md`, `nikhilsoman.md`
- `project-docs/memory.md`
- `project-docs/repo-evaluation-report.md`
- `project-docs/reports/2026-07-26-cost-capability-last50.md`

None of this content was destroyed at the git object-store level — it remains fully retrievable via `git show c34e2eb:<path>` as long as `c34e2eb` stays reachable. The actual damage is loss of live tracking: the content does not exist in fresh clones of `main`, has no regeneration mechanism, and prior to this RCA existed only as a fragile, single-machine, gitignored copy left over from unrelated earlier verification work (not a deliberate backup).

## Action items

1. **Recovery (this PR/branch):** restore all 13 non-DB-backed files as tracked content on `main`, sourced directly from `c34e2eb` via `git checkout c34e2eb -- <paths>`.
2. **Prevention — scope discipline:** `decisions/`, `repo-evaluation-report.md`, and `reports/` should be explicitly documented as hand-maintained, git-tracked-only content that migrate-driven deletion logic must never touch — either give them a real DB-backed regeneration path, or exclude them by name from any future bulk `project-docs/` deletion.
3. **Prevention — review process:** for any PR whose diff includes bulk deletion of a directory tree, a non-authoring reviewer resolving a merge conflict must diff the full tree against the pre-merge base commit (not just the PR's own branch-relative changes) before reporting the conflict as resolved and merging.

## What went right

- The repo's own PR Review Discipline (non-authoring reviewer required) and the standing "verify job status via ground truth, never trust self-report" practice are what caught this — the process worked, just one step later than ideal (post-merge instead of pre-merge).
- Nothing was irrecoverably destroyed; full content was reconstructable directly from git history with no ambiguity about correctness.
