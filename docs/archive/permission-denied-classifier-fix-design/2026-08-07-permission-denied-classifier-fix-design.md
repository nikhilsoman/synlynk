# Permission-Denied Classifier Fix — Design

## Context

Issue #720 documented a false-positive terminal-status incident: job-9460f9fc performed
"extensive reads, edits, tests, and a commit" but was still classified `permission_denied`.
Two #720 sub-projects have already shipped — the fail-closed empty-task guard (PR #759) and
the task-receipt protocol (PR #768) — but neither touched the actual classifier bug. This
design covers requirement 5 of #720 (tracked standalone in issue #769): fixing
`_log_has_permission_denied_signature()` itself.

## Problem

`_log_has_permission_denied_signature()` (`synlynk/costs.py:130`) scans a job's log for a
headless permission auto-denial signature. Two detection paths exist:

1. A phrase match (`"no output produced"`, `"permission that headless mode cannot prompt
   for"`, `"auto-denied"`) in the last 80 non-indented lines.
2. A structured-event fallback: it scans the log's JSON lines in reverse, and the **first**
   event it finds with `status == "SUCCESS"`, `response == ""`, and `num_turns <= 1` causes it
   to return `True` immediately.

The structured-event fallback is the source of the bug. It only inspects the properties of a
single matching event — typically the final one — and never checks whether earlier events in
the same log show real activity (tool use, non-empty responses). A harness can legitimately do
substantial work across several turns and then emit one final empty/short-response event (e.g.
a trailing summary or benign no-op turn); the current logic treats that final event's shape as
sufficient proof of denial regardless of what came before it.

Three call sites consume this classifier, with different corroborating context available at
each:

| Call site | File:Line | Worktree/`git_state` available? |
|---|---|---|
| `jobs`-table reconciliation, waitpid-reaped branch | `synlynk/jobs.py:1151` | Yes |
| `jobs`-table reconciliation, dead-pid branch | `synlynk/jobs.py:1298` | Yes |
| `daemon_jobs`-table reconciliation | `synlynk/jobs.py:1482` | No — `daemon_jobs` has no `worktree_path` column |

## Fix

### 1. Root-cause fix — `_log_has_permission_denied_signature()` (`synlynk/costs.py`)

Change the structured-event scan from "return `True` on the first matching event" to "return
`True` only if **no earlier event** in the log shows real activity." Concretely:

- Parse every line in the log as JSON where possible (same tolerant `json.loads` skip-on-
  failure approach already used).
- Collect all successfully-parsed structured events, in log order.
- If any event **before** the final denial-shaped event has a non-empty `response` field, or
  contains a `tool_use` block (check both top-level `tool_use` and nested `content` list
  entries with `type == "tool_use"`, matching whatever shape the harnesses actually emit —
  confirm exact shape against a real log sample during implementation), treat that as evidence
  of real activity and return `False`.
- Otherwise, preserve existing behavior: return `True` when the phrase match hits, or when the
  final matching event has `response == ""` and `num_turns <= 1` with no earlier corroborating
  event.

This is a single-function change, fixes all three call sites (including `daemon_jobs`, which
has no other avenue for corroboration), and requires no signature change — callers already
just get a bool back.

### 2. Git-state corroboration — `jobs.py` call sites only

At the two `jobs`-table call sites (`jobs.py:1151`, `jobs.py:1298`), `git_state` is already
computed nearby (`_inspect_worktree_git_state()`). Add it as a second, independent
corroboration signal, reusing the existing `_job_has_real_work_landed(git_state)` helper
(`jobs.py:79`, already used by `_retry_internal_timeout_job` and `_finalize_completed_worktree_job`):

```python
permission_denied = _log_has_permission_denied_signature(log_text)
if permission_denied and _job_has_real_work_landed(git_state):
    permission_denied = False
```

This catches the case where the log's structured events are ambiguous or missing (e.g. a
harness that doesn't reliably emit `tool_use` blocks) but a real commit or remote push proves
the job worked. It is deliberately scoped to the two `jobs`-table sites only —
`daemon_jobs` has no `worktree_path`, so it has no `git_state` to check and relies solely on
the layer-1 fix.

### 3. Reclassification behavior

When either signal (log-level or git-level) corroborates real work, the job is **not** marked
`permission_denied`. The existing code paths already treat `permission_denied == False` as
"proceed with normal status derivation" — at `jobs.py:1151`/`1298` this means the job's status
falls through to whatever the exit-code/git-state logic already computes (typically
`completed`, `exit_code = 0`, when the process exited cleanly), and normal
`_finalize_completed_worktree_job()` / `_apply_dispatch_gate()` auto-finalize/push behavior
proceeds unchanged. No new status value is introduced — this fix corrects an existing
misclassification rather than adding a new terminal state.

At the `daemon_jobs` call site (`jobs.py:1482`), the existing `if log_text and
_log_has_permission_denied_signature(log_text): status = "permission_denied"` guard simply
stops firing when layer 1 correctly returns `False`; the job keeps whatever status was already
derived from its `exit_code` (`done`/`unknown`/`failed`).

## Testing

**Unit tests for `_log_has_permission_denied_signature()`** (new, in the existing
`costs.py` test file):

- A log containing only the final denial-shaped event (`response == ""`, `num_turns <= 1`) and
  no earlier activity → `True` (existing behavior preserved).
- A log with an earlier event containing a non-empty `response` before the final denial-shaped
  event → `False`.
- A log with an earlier event containing a `tool_use` block before the final denial-shaped
  event → `False`.
- A log with only the denial-shaped event and unrelated non-JSON lines before it → `True`
  (unchanged; no false corroboration from noise).
- Existing phrase-match tests (`"no output produced"`, etc.) continue to pass unmodified.

**Reconciliation-level tests** (new, in `tests/test_synlynk.py` or `tests/test_jobs.py`,
mirroring the existing `test_reconcile_*` fixture style):

- A job whose log has the denial signature **and** real git commits in its worktree
  (`has_activity: True`) reconciles to `completed`, not `permission_denied` — directly
  addresses the job-9460f9fc incident shape.
- A job whose log has the denial signature and a clean worktree (no git activity, no earlier
  log-level activity) still reconciles to `permission_denied` — confirms the fix doesn't
  over-correct into false negatives.
- A `daemon_jobs` reconciliation test confirming the log-level fix alone (no worktree
  available) prevents a false `permission_denied` when earlier tool activity is present in the
  log.

## Out of scope

- No new job status value.
- No changes to the phrase-match detection path (first branch of the classifier) — only the
  structured-event fallback changes.
- No changes to `SCOPE_VIOLATION` or safe-caller documentation — those are separate #769
  sub-projects with their own spec/plan cycles.
