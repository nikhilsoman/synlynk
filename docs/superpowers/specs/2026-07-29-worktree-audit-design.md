# Worktree Audit — Design Spec

**Date:** 2026-07-29
**Status:** Approved (pending commit + user sign-off)
**Author:** Claude (brainstorm), for dispatch to Codex

## Problem

A manual audit on 2026-07-29 found 30 stale git worktrees/branches accumulated in this repo,
because worktree cleanup only ever happened reactively, in large batches, long after the
underlying PRs had merged. The manual process — cross-referencing every worktree's branch
against `origin/main` via ancestor checks, `gh pr list`, and diff-stat heuristics — is exactly
the kind of repetitive, mechanical classification work that should be a CLI command instead of
something re-derived by hand each time.

The CLAUDE.md **Worktree Hygiene Protocol** (added in PR #575) codifies the discipline of
cleaning up on merge and running periodic audits, but currently relies entirely on a human (or
Claude) doing the checks manually. This spec designs the tooling to automate that classification
and, optionally, the cleanup action itself.

## Goals

- Automate the safe/unsafe/needs-review classification performed manually in the 2026-07-29 audit.
- Provide a dry-run-by-default cleanup action so a routine sweep is a single confirmed command,
  not a hand-rolled script.
- Never destroy uncommitted work, active (open-PR) branches, or the worktree the tool is
  currently being run from.
- Surface staleness proactively via `synlynk status`, without slowing `status` down with
  network/`gh` calls.

## Non-goals (out of scope for v1)

- Auto-archiving genuinely-unmerged, no-PR worktrees with real content (e.g. abandoned design
  specs). These are flagged `needs-review`; archiving remains a manual decision per the existing
  archive-before-branch-removal policy.
- Any action beyond worktree removal + branch deletion (local and remote) — no rebasing,
  no PR creation, no content migration.
- Cross-repo or cross-machine worktree tracking — this operates only on `git worktree list` in
  the current repo.

## Command shape

Two new subcommands under a `worktree` command group, wired into `synlynk/cli.py` alongside the
existing `doctor`, `probe`, `status`, and `jobs` subparsers:

- `synlynk worktree audit [--json]` — read-only report only. Never mutates anything.
- `synlynk worktree clean [--apply] [--json]` — same classification and report; without
  `--apply` it's a dry-run ("would remove N"); with `--apply` it actually deletes every `SAFE`
  item's worktree, local branch, and remote branch (best-effort).

Both commands exclude two things unconditionally, before any classification runs:

1. The main repo checkout itself (never a "worktree" to classify).
2. Whichever worktree contains the current working directory — resolved via
   `git rev-parse --show-toplevel` compared against each `git worktree list --porcelain` entry.
   This guarantees the tool can never remove the workspace it's being invoked from.

## Data source

`git worktree list --porcelain`, parsed into `(path, branch)` pairs (mirrors the parsing done
manually today via `awk`). For each remaining pair, gather:

- `git status --short` in that worktree path (dirty check).
- `git merge-base --is-ancestor <branch> origin/main` (ancestor check).
- If not an ancestor and `gh` is available/authenticated: `gh pr list --state all --search
  "head:<branch>" --json number,state,mergedAt`.
- If not an ancestor and the PR is `CLOSED`: `git diff origin/main..<branch> --stat` to compute
  net insertions/deletions.
- Nesting: any worktree path that is itself inside another worktree's path is a "nested"
  worktree; its parent is whichever other entry's path is the longest matching prefix.

`gh` availability is checked once per invocation (`gh auth status`), not per-branch, to avoid
N repeated auth failures.

## Classification algorithm

Applied per worktree, in this order — first matching rule wins:

1. **Dirty override.** If `git status --short` produces any output, verdict is `needs-review`
   with reason `"dirty: <first line of status output>"`, regardless of any other signal. No
   further checks run for this worktree.
2. **Ancestor check.** If `git merge-base --is-ancestor <branch> origin/main` succeeds, verdict
   is `safe`, reason `"merged, direct ancestor"`.
3. **PR state (requires `gh`).** If `gh` is unavailable/unauthenticated, verdict is
   `needs-review`, reason `"could not verify PR state — gh unavailable"`. Otherwise:
   - PR `MERGED` → `safe`, reason `"PR #<n> merged"`.
   - PR `CLOSED` (not merged) → compute `git diff origin/main..<branch> --stat`'s net line count
     (insertions minus deletions across all files). Net `<= 0` → `safe`, reason `"PR #<n>
     closed, stale — no unique content vs main"`. Net `> 0` → `needs-review`, reason `"PR #<n>
     closed, <net> net lines of unmerged content"`.
   - PR `OPEN` → `unsafe`, reason `"PR #<n> open — active work"`.
   - No PR found for this branch → `needs-review`, reason `"no PR found, <n> commits ahead of
     main"` (commit count via `git log origin/main..<branch> --oneline | wc -l`).
4. **Nesting floor.** After every worktree has an initial verdict, a second pass applies: any
   nested worktree whose parent's verdict is `needs-review` or `unsafe` is raised to at least
   that verdict (`needs-review` is the floor unless the parent is `unsafe`, in which case the
   child is also `unsafe`), reason appended: `"parent worktree not yet safe"`. A nested
   worktree's own `safe` verdict is preserved only when its parent is also `safe`.

## Report format

`synlynk worktree audit`, grouped by verdict, most actionable first:

```
SYNLYNK WORKTREE AUDIT   <n> worktrees checked (excluding main + current session)

SAFE (4) — merged/stale, no action needed but removable
  chore/blog-pr542-pr549          PR #552 merged
  dispatch/grok/job-4de33412      PR #516 closed, stale — no unique content vs main
  ...

NEEDS-REVIEW (2) — a human should look
  chore/hn-idea-finder-discovery-design   no PR found, 1 commit ahead of main
  worktrees/job-33859a65                  dirty: M GEMINI.md

UNSAFE (2) — active, do not touch
  worktrees/job-cc6b2f4a          PR #566 open
  worktrees/job-d0d24273          PR #565 open

Run `synlynk worktree clean --apply` to remove the 4 SAFE items.
```

`--json` emits the same data as a structured payload (list of `{path, branch, verdict, reason,
nested_under}`), following the convention already used by `status --json`.

If zero worktrees exist to audit (a freshly cloned repo, or everything already clean), print a
one-line `No stale worktrees — nothing to audit.` instead of empty section headers.

## `clean` behavior

- No `--apply`: identical table to `audit`, with the summary line reframed as
  `"[dry-run] would remove N worktrees + branches (use --apply)"`.
- `--apply`: for each `SAFE`-verdict item only, in an order that always removes nested worktrees
  before their parents (so a parent removal never orphans a still-registered child):
  1. `git worktree remove --force <path>` (from the main repo root, never from inside the
     worktree being removed).
  2. `git branch -D <branch>`.
  3. `git push origin --delete <branch>` — best-effort; a "remote ref does not exist" failure is
     swallowed and reported as `remote-none/skip`, not treated as an error.
  4. Print a per-item result line as each step completes: `<branch>   wt=removed
     branch=deleted   remote-deleted|remote-none/skip`, or `wt=FAILED(<reason>)` /
     `branch=FAILED(<reason>)` on failure.
  5. `git worktree prune` once at the end of the batch.
- A failure on any individual item (e.g. `git branch -D` refuses because something still
  references it) is reported inline and does **not** abort the rest of the batch — matches the
  behavior of the manual cleanup script used in the 2026-07-29 audit.
- `NEEDS-REVIEW` and `UNSAFE` items are never touched by `--apply`, under any flag. There is no
  "force" escalation path in v1 — those always require a human to resolve manually (delete by
  hand, or archive first per the existing archive-before-branch-removal policy).

## Error handling

- **`gh` missing or unauthenticated:** detected once via `gh auth status` at the start of the
  run. All branches that would otherwise need step 3 of classification fall through to
  `needs-review: could not verify PR state — gh unavailable`. This is not a hard failure — the
  audit still completes and reports fully on every ancestor-checkable branch.
- **Worktree directory listed by `git worktree list` but missing on disk** (already manually
  `rm -rf`'d without `git worktree remove`): reported with its own reason,
  `"worktree directory missing — stale registration"`, classified `safe` (nothing to lose), and
  `clean --apply` handles it via `git worktree prune` rather than attempting
  `git worktree remove` on a nonexistent path.
- **Any git/gh subprocess failure mid-check** for a single worktree (timeout, permissions, etc.):
  that worktree's verdict becomes `needs-review` with the raw error as the reason; other
  worktrees' checks are unaffected.

## `synlynk status` integration

`status` gains a `WORKTREES` line, computed by a cheap local-only pre-pass — dirty check +
ancestor check only, **no `gh` calls** — so it doesn't slow down `status`'s existing latency
budget:

```
FLEET   4/5 attached   mode: daily-grind
WORKTREES  6 local, 2 look stale — run `synlynk worktree audit`
BUDGET  limit tracked via .synlynk/config.json
```

"Looks stale" here means: not dirty, and either an ancestor of `origin/main`, or simply not
verifiable without `gh` (i.e. anything that isn't confidently `unsafe`-equivalent — no PR-state
lookup is performed at this stage, so this count is a conservative upper bound, not the precise
`audit` classification). The line is omitted entirely when the stale count is 0. `status --json`
gains a matching `"worktrees": {"local": N, "stale_hint": M}` field.

## Module & code structure

New module `synlynk/worktree.py`, following the existing pattern of `doctor.py` / `probe.py` /
`status.py` (each a self-contained module wired into `synlynk/cli.py`'s subparsers).

Structure:
- `_parse_worktree_list() -> list[WorktreeEntry]` — wraps `git worktree list --porcelain`,
  excludes main repo + cwd's own worktree, computes nesting relationships.
- `_classify_worktree(entry, gh_available) -> WorktreeVerdict` — pure-ish function implementing
  the classification algorithm above; takes pre-fetched git/gh command outputs as inputs so it's
  independently testable without shelling out for every branch/rule combination.
- `_apply_nesting_floor(verdicts) -> list[WorktreeVerdict]` — second pass implementing the
  nesting rule.
- `cmd_worktree_audit(json_output=False) -> str` — orchestrates parse → classify → floor →
  format, mirrors `cmd_status`'s signature/return convention.
- `cmd_worktree_clean(apply=False, json_output=False) -> str` — reuses the audit path, then
  performs the remove/delete sequence when `apply=True`.
- `_worktree_status_hint() -> Optional[str]` — the cheap local-only pre-pass used by `status`'s
  integration; imported by `synlynk/status.py`.

`WorktreeEntry` and `WorktreeVerdict` are small dataclasses (`path`, `branch`, `verdict`,
`reason`, `nested_under: Optional[str]`).

## Testing

New `tests/test_worktree.py`, following the stub-script convention already used in
`tests/test_probe.py` (writing an executable stub script to `tmp_path` and pointing `PATH` or a
direct subprocess call at it) for anything that would otherwise shell out to `git`/`gh`.

Required cases, one test each:
- Ancestor-true → `safe`.
- PR merged (not ancestor) → `safe`.
- PR closed, net-zero-or-negative diff → `safe`.
- PR closed, net-positive diff → `needs-review`.
- PR open → `unsafe`.
- No PR found → `needs-review`.
- Dirty worktree (any branch state) → `needs-review`, dirty overrides everything else.
- `gh` unavailable → `needs-review` fallback, without crashing.
- Nested worktree under a `safe` parent, itself independently `safe` → stays `safe`.
- Nested worktree under a `needs-review`/`unsafe` parent → floored to at least that verdict.
- Missing worktree directory (stale registration) → `safe`, handled via prune in `--apply`.
- `clean --apply` dry-run vs. actual: verify no git mutation occurs without `--apply`.
- `clean --apply` partial failure: one item's `git branch -D` fails (simulate via stub exit
  code) → batch continues, failure reported, other items still processed.
- `status`'s `WORKTREES` hint line: appears when stale count > 0, omitted when 0, and does not
  invoke `gh` (assert via a stub that fails/errors if invoked, since the pre-pass must not call
  it at all).

## Open questions

None — all design decisions were resolved during brainstorming (command shape, classification
heuristic, dirty-handling, nesting behavior, clean's dry-run default, remote-branch deletion
scope, archive-suggestion scope, and status integration were each explicitly chosen over an
alternative).
