# Scope Violation Enforcement — Design

## Context

Issue #720 ("Fail closed on empty dispatch tasks and enforce task/scope integrity") specified
6 required behaviors, tracked via #769 after two sub-projects shipped: the fail-closed
empty-task guard (PR #759) and the task-receipt protocol (PR #768). A third sub-project —
the permission-denied classifier fix — shipped as PR #770/#771. This design covers the
remaining requirement 4 of #720: enforcing declared scope on design-only/docs-only dispatches,
not merely prompting for it.

## Problem

Today, a dispatch's `--task` text can *ask* an agent to only touch documentation, but nothing
enforces that request. A design-only job can drift into editing source files, and nothing stops
it from opening a PR or otherwise writing to GitHub even when the intent was "write a spec, no
side effects." Issue #720's acceptance tests require: a design-only fixture that attempts a
source edit and a `gh pr create` must have both blocked, with the job recorded as
`SCOPE_VIOLATION` — while a correct design-only task must still commit its declared file and be
reported completed.

## Fix

### 1. Scope declaration (`synlynk/cli.py`, `synlynk/dispatch.py`, `synlynk/jobs.py`)

A new repeatable CLI flag on `synlynk dispatch`, parallel to the existing `--requires`/`--grant`:

```
dispatch_parser.add_argument(
    "--scope-paths", action="append", default=[],
    dest="scope_paths",
    help="Restrict this dispatch to only touching files matching this glob (repeatable, "
         "e.g. --scope-paths 'docs/superpowers/specs/**'). Declaring this denies automatic "
         "PR creation by default unless --requires-gh-write is also set. See #769.",
)
```

Jobs are not stored in a SQL table — `_load_jobs()`/`_save_jobs()` (`synlynk/jobs.py:43-59`)
persist the full job list as a plain JSON array in `.synlynk/jobs.json`, and job dicts already
carry ad-hoc fields (`base_branch`, `base_sha`, etc.) with no schema migration needed. `task_sha256`/
`task_preview` are *not* stored columns either — they're computed on the fly from `job.get("task")`
at each reconciliation call site (`_task_sha256_and_preview()`, `jobs.py:574`). `scope_paths`
follows the same pattern: `dispatch_agent()` (`synlynk/dispatch.py:1610`) gains a `scope_paths: list
= None` parameter, stores it as `job["scope_paths"] = scope_paths or []` in the job dict it builds,
and `_save_jobs()` persists it for free as part of the existing job dict.

There is also no `"gh-write"` permission string anywhere in the codebase.
`_resolve_dispatch_permissions()` (`dispatch.py:132`) resolves agent-side tool permissions like
`"write:src/"`/`"run:tests"` for the *dispatched agent's own* CLI flags — it has nothing to do with
synlynk's own post-hoc PR creation. That PR creation happens in `_maybe_open_worktree_pr()`
(`jobs.py:280`), called from `_finalize_completed_worktree_job()` (`jobs.py:404`), and today it
runs **unconditionally** whenever a completed job has real work. GitHub-write capability for the
*agent itself* is a separate, pre-existing mechanism: `dispatch_agent()`'s `requires_gh_write: bool`
param reroutes to an agent with `can_gh_write: True` in `AGENT_CAPABILITY_BASELINES`
(`dispatch.py:1637-1660`); it does not gate synlynk's own PR-creation call either.

So the correct, minimal enforcement point is `_finalize_completed_worktree_job()` itself: before
calling `_maybe_open_worktree_pr()`, skip the call when `job.get("scope_paths")` is truthy and
`job.get("requires_gh_write")` is falsy (the job's dispatch-time `--requires-gh-write` flag,
already stored on the job dict by existing code). This reuses the existing `--requires-gh-write`
flag as the override — no new `--grant gh-write` flag is introduced. A job dispatched without
`--scope-paths` is entirely unaffected: `scope_paths` is empty/absent, the guard never fires, and
`_maybe_open_worktree_pr()` runs exactly as it does today.

`git push` of the job's own branch is deliberately **not** gated by this — it stays on the
unconditional auto-finalize path in `_finalize_completed_worktree_job()`. Only the PR-creation
call is skipped by default for scope-declared jobs.

### 2. Post-completion enforcement (`synlynk/jobs.py`)

At the two existing `jobs`-table reconciliation call sites (waitpid-reaped ~line 1200, dead-pid
~line 1385 — same locations the permission-denied and task-receipt checks already run), after
`git_state` is computed and before `_finalize_completed_worktree_job`/`_apply_dispatch_gate` are
called:

**`_inspect_worktree_git_state()` gains a `changed_files` field.** Currently it only returns a
`dirty` boolean. Extend it to also collect the file list:

```python
changed_files = []
if base_commit:
    diff_result = subprocess.run(
        ["git", "-C", worktree_path, "diff", "--name-only", f"{base_commit}..HEAD"],
        capture_output=True, text=True, check=False,
    )
    if diff_result.returncode == 0:
        changed_files.extend(p for p in (diff_result.stdout or "").splitlines() if p)
if dirty:
    changed_files.extend(_collect_worktree_status_paths(worktree_path))
git_state["changed_files"] = sorted(set(changed_files))
```

(`_collect_worktree_status_paths` already exists and is reused as-is from
`_finalize_completed_worktree_job`.)

**New helper `_check_scope_compliance()` (`synlynk/jobs.py`):**

```python
import fnmatch

def _check_scope_compliance(changed_files, scope_paths) -> bool:
    """True if every changed file matches at least one declared scope glob.

    An empty scope_paths list means no scope was declared — always compliant (no-op).
    """
    if not scope_paths:
        return True
    for path in changed_files:
        if not any(fnmatch.fnmatch(path, pattern) for pattern in scope_paths):
            return False
    return True
```

**Wired into both reconciliation branches**, immediately before the existing
`_finalize_completed_worktree_job(job, git_state)` / `_apply_dispatch_gate(job)` calls:

```python
scope_paths = job.get("scope_paths") or []
if scope_paths and git_state and not _check_scope_compliance(
    git_state.get("changed_files", []), scope_paths
):
    job["status"] = "SCOPE_VIOLATION"
    job["scope_violation_files"] = [
        p for p in git_state.get("changed_files", [])
        if not any(fnmatch.fnmatch(p, pat) for pat in scope_paths)
    ]
else:
    _finalize_completed_worktree_job(job, git_state)
    _apply_dispatch_gate(job)
```

(`job["status"]`/`job["scope_violation_files"]` are plain dict assignments — persisted the same
way every other in-place job mutation in this loop already is, via the single `_save_jobs(jobs)`
call at the end of the reconciliation function, e.g. `jobs.py:1414`. No database write is
involved.)

A `SCOPE_VIOLATION` job skips `_finalize_completed_worktree_job` entirely — no git add, no
commit, no push, no PR. `_maybe_open_worktree_pr` is never reached. The worktree is left intact
(not reverted or cleaned) for human inspection, consistent with the repo's flag-don't-destroy
posture for anything not yet confirmed safe to discard.

**`daemon_jobs` reconciliation is unaffected.** It has no `worktree_path` column and therefore no
`git_state` to check changed files against — same reasoning the permission-denied classifier fix
used to scope its Layer 2 (git-state corroboration) to the `jobs` table only.

A compliant scope-declared job proceeds through `_finalize_completed_worktree_job` normally:
commit and push happen unconditionally (git push isn't gated). Inside that function, immediately
before its existing call to `_maybe_open_worktree_pr(job, worktree_path, worktree_branch)`, add:

```python
if job.get("scope_paths") and not job.get("requires_gh_write"):
    print(
        f"  ⚠ scope-declared job {job.get('id', '')}: skipping automatic PR creation "
        f"(pass --requires-gh-write to allow)"
    )
else:
    pr_number = _maybe_open_worktree_pr(job, worktree_path, worktree_branch)
    ...  # existing capability_ratings.pr_number update, unchanged
```

So a compliant design-only job is pushed and reported `completed`, but no PR is opened unless
`--requires-gh-write` was passed at dispatch time.

### 3. Status value

`SCOPE_VIOLATION` is a new terminal job status, following the same convention as
`permission_denied` and `TASK_DELIVERY_FAILED`. It is surfaced in `jobs --all`,
`jobs --summary <id>` (showing `scope_violation_files`), and `synlynk status`.

## Testing

**Unit tests for `_check_scope_compliance()`** (new, in `tests/test_jobs.py`):

- Changed files all matching a single declared glob → `True`.
- Changed files all matching at least one of several declared globs → `True`.
- A changed file matching none of the declared globs → `False`.
- Empty `scope_paths` (no declaration) → `True` regardless of changed files (backward
  compatible no-op).

**Reconciliation-level tests** (new, in `tests/test_jobs.py`, mirroring the existing
`test_reconcile_*` fixture style used by the permission-denied and receipt-protocol fixes):

- A job with `scope_paths=["docs/superpowers/specs/**"]` whose worktree also has a change to
  `synlynk/jobs.py` reconciles to `SCOPE_VIOLATION`; `_maybe_open_worktree_pr` is never called
  (assert via monkeypatched spy); no push occurs (assert `_push_worktree_branch_if_needed` spy
  not called).
- A job with the same `scope_paths` whose worktree only touched a file under
  `docs/superpowers/specs/` reconciles to `completed`; the branch is pushed; no PR is opened
  (`requires_gh_write` not set).
- A job with `scope_paths` declared, `requires_gh_write=True` also set, and only in-scope changes
  → `completed`, pushed, and `_maybe_open_worktree_pr` is called (confirms the skip guard isn't
  permanently blocking PR creation when `--requires-gh-write` is explicitly passed).
- A job with no `scope_paths` declared behaves identically to current behavior (regression
  guard — this is the most important test given how much of the reconciliation path is shared).

**`selftest --matrix` cell** (`synlynk/fleet.py`, same location PR #768 added its
receipt-compliance cell): dispatches a minimal fixture task declaring `--scope-paths` that
attempts an out-of-scope edit, and asserts the resulting job status is `SCOPE_VIOLATION` and no
PR was created.

## Documentation

- README dispatch section: document `--scope-paths` alongside the existing `--grant`,
  `--revoke`, `--requires-gh-write` flags, including the default gh-write-denial behavior and
  how to override it.
- `jobs --summary` output format: document the new `scope_violation_files` field.

## Out of scope

- No retroactive scope-checking for jobs dispatched before this change or without
  `--scope-paths` — opt-in only.
- No UI/Vizor surfacing of `SCOPE_VIOLATION` in this pass (existing generic job-status rendering
  already shows arbitrary status strings; a dedicated visual treatment can follow as a separate
  small PR if it turns out to be needed).
- No interaction logic between `SCOPE_VIOLATION` and `TASK_DELIVERY_FAILED`/`permission_denied`
  — these are independent checks against independent evidence (task-receipt marker,
  denial-signature, changed-file scope) that can each fire on their own. No new precedence rule
  is introduced; the existing check ordering in the reconciliation branches is preserved, with
  the scope check added as an additional gate before finalize.
- No sandboxing or physical prevention of an agent's file writes inside its own worktree — "block"
  means synlynk withholds finalize/push/PR and reports `SCOPE_VIOLATION`, not that the write
  itself is intercepted at the OS/filesystem level.
- No changes to the third #769 sub-project (safe-caller-construction docs) — separate spec/plan
  cycle.
