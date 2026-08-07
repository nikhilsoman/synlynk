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

### 1. Scope declaration (`synlynk/cli.py`, `synlynk/dispatch.py`)

A new repeatable CLI flag on `synlynk dispatch`, parallel to the existing `--requires`/`--grant`:

```
dispatch_parser.add_argument(
    "--scope-paths", action="append", default=[],
    dest="scope_paths",
    help="Restrict this dispatch to only touching files matching this glob (repeatable, "
         "e.g. --scope-paths 'docs/superpowers/specs/**'). Declaring this denies gh-write "
         "capability by default unless --grant gh-write or --requires-gh-write is also set. "
         "See #769.",
)
```

`scope_paths` (a JSON array, empty by default) is threaded through `dispatch_agent()` into the
job record (new `scope_paths` column on the `jobs` table, same pattern as the existing
`task_sha256`/`task_preview` columns from #720 sub-project 1) and into `_resolve_dispatch_permissions()`:

```python
def _resolve_dispatch_permissions(agent, role, grants, revokes, requires_gh_write, scope_paths):
    effective = set(_ROLE_PERMISSION_DEFAULTS.get(role, []))
    if scope_paths and not requires_gh_write and "gh-write" not in grants:
        effective.discard("gh-write")
    effective.update(grants)
    effective.difference_update(revokes)
    return sorted(effective)
```

This reuses the existing permission → CLI-tool-flag plumbing (`_permissions_to_flags`,
`_grok_permission_flags`) that already gates `gh` CLI/MCP tool availability per agent — no new
enforcement mechanism, just a new default input to an existing one. A job dispatched without
`--scope-paths` is entirely unaffected: `scope_paths` is empty, the `if scope_paths and ...`
guard never fires, and permission resolution behaves exactly as it does today.

`git push` of the job's own branch is deliberately **not** gated by this permission — it stays
on the unconditional auto-finalize path described below. Only GitHub API writes (PR creation,
review, merge) are denied by default for scope-declared jobs.

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
    _pkg("_get_db")().execute(
        "UPDATE jobs SET status=?, scope_violation_files=? WHERE id=?",
        (job["status"], json.dumps(job["scope_violation_files"]), job["id"]),
    ).connection.commit()
else:
    _finalize_completed_worktree_job(job, git_state)
    _apply_dispatch_gate(job)
```

A `SCOPE_VIOLATION` job skips `_finalize_completed_worktree_job` entirely — no git add, no
commit, no push, no PR. `_maybe_open_worktree_pr` is never reached. The worktree is left intact
(not reverted or cleaned) for human inspection, consistent with the repo's flag-don't-destroy
posture for anything not yet confirmed safe to discard.

**`daemon_jobs` reconciliation is unaffected.** It has no `worktree_path` column and therefore no
`git_state` to check changed files against — same reasoning the permission-denied classifier fix
used to scope its Layer 2 (git-state corroboration) to the `jobs` table only.

A compliant scope-declared job proceeds through `_finalize_completed_worktree_job` normally:
commit and push happen unconditionally (git push isn't gated), but `_maybe_open_worktree_pr`
still respects whatever gh-write permission was resolved in Section 1 — so a compliant
design-only job is pushed and reported `completed`, but no PR is opened unless gh-write was
explicitly granted.

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
  (gh-write not granted).
- A job with `scope_paths` declared, `--grant gh-write` also passed, and only in-scope changes
  → `completed`, pushed, and `_maybe_open_worktree_pr` is called (permission resolution
  confirmed not permanently blocking gh-write when explicitly granted).
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
