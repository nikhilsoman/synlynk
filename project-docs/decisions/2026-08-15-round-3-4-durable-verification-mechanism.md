---
decision_id: dec-r3-701consolidation
topic: "ROUND 3/4 — What durable verification mechanism would have caught #935 (and would catch #659-class failures) before they became user-visible, without relying on human-remembered flags?"
date: 2026-08-15
panel: [claude-direct-evidence]
status: approved
---

## Topic
Round 1 found the #939 point-fix depends on a human passing `--task-type review`
every time. Round 2 found Problem 2b (MCP delivery) has zero verification today —
a job can self-report `OK, exit 0` while the actual GitHub write silently
cancelled. What single, durable mechanism would close both gaps rather than
adding more hardcoded special cases?

## Evidence for why "add another timeout/flag" doesn't generalize

- `_check_job_stall`'s only evidence source is `_inspect_worktree_git_state`
  (local commits/dirty, remote pushes). It has no concept of "did the declared
  goal of this task (a GitHub write, a merge) actually happen." A task that is
  purely read/verify/report (increasingly common as dispatch scope grows —
  triage jobs, audit jobs, this very brainstorm job) will always look "stalled"
  by this metric even when working correctly, regardless of timeout length.
- `--task-type review` is opt-in and unenforced. `--requires-gh-write` (already a
  first-class dispatch flag, per `dispatch.py:1892`) is a *stronger* and
  already-present signal for "this job's success is defined by an external
  GitHub-state change, not local git activity" — but the stall-killer does not
  currently look at it at all.
- Problem 2b (#659) has literally no check today beyond the dispatched job's own
  exit code. The fix that closed #569 (env/identity fail-closed) does not help
  here, because the MCP connector authenticates independently of the `gh` CLI env
  vars `_build_subprocess_env` controls (Round 2 evidence).
- The one place in the codebase that already does this correctly end-to-end today
  is the human workaround described in #701's own summary line: "verify against
  actual git state... open PRs by hand... review, and only come back once all
  three are ready" — i.e., Nikhil manually running `gh api`/`gh pr view` checks
  after the fact. This is exactly the check that should be automated, not
  performed by a human every session.

## Proposed mechanism: delivery-of-effect verification, checked at every lifecycle gate

Extend ground-truth verification beyond git-worktree state to **GitHub API state**,
and check it at both checkpoints where it's currently missing:

1. **At the stall-kill decision (`_check_job_stall`):** before killing a job whose
   log has gone stale, if the job was dispatched with `--requires-gh-write` or
   declares a target PR/issue, run one cheap authenticated `gh api` /
   `gh pr view --json ...` call (using the orchestrator's own identity, not the
   sandboxed job's) checking whether the declared target has already received the
   expected write (review/comment/merge) since job start. If yes, the job
   *finished* and just failed to exit cleanly — do not kill, mark terminal from
   the API evidence directly. If no and evidence of git/API activity is absent,
   *and* the job type has no declared external-effect check, only then fall back
   to the existing timeout. This replaces the brittle `task_type == "review"`
   string match with a signal already present on every gh-write dispatch
   (`--requires-gh-write`), and extends "evidence beats timeout" from local git
   state to the actual external effect the job exists to produce.
2. **At job-terminal reconciliation, for `--requires-gh-write` jobs specifically:**
   after a job reaches any terminal state (done, failed, stalled), run the same
   `gh api` check and record a `gh_write_verified: true/false/unknown` field
   alongside `status`. A job that exits 0 but the check comes back `false` becomes
   the first-class `succeeded_gh_write_failed` status #701 already proposed for
   Problem 2 — this is the missing verification step that status was designed
   for but never got wired to an actual check. This is what would have caught
   #659's 4/4 MCP-cancellation failures automatically, the same session they
   happened, instead of requiring a manual log grep.
3. **Surface both checks the same way GTV already surfaces git evidence** — in
   `synlynk jobs`/`synlynk logs` summary lines, not buried in a raw log — so "did
   the effect actually happen" is answerable without a human re-deriving it.
4. **CI guard, generalizing #701's Problem-1 recommendation (B):** a shared test
   fixture asserts that any code path making a terminal-status decision for a
   `--requires-gh-write` job (stall-kill, reconciliation, or future paths) is
   required to consult (or explicitly, auditably skip with a documented reason)
   the delivery-of-effect check — so this class of gap can't reopen a fifth time
   in a not-yet-written code path the way it opened in `_check_job_stall`
   un-noticed by the Job Truth epic.

## Why this is durable rather than another point patch
It keys off `--requires-gh-write` — a flag that already exists, is already
load-bearing for routing (#426/#569), and is attached to the job at dispatch time
rather than requiring a second, easy-to-forget flag. It does not require guessing
task shape from a string. It generalizes to any future dispatch task whose
success is defined by an external state change (not just "review"), including
merges, cherry-picks, and issue comments. And it directly implements the
mechanism the user's own workaround already performs by hand every session —
automating exactly that, rather than adding a new manual step.

## Decision
Adopt delivery-of-effect verification via `--requires-gh-write`-gated `gh api`
checks as the durable mechanism, wired into both the stall-kill escape hatch and
terminal reconciliation, surfaced in job status, and enforced by a shared CI
fixture. Superset PR #939's task_type carve-out (keep it as a secondary signal,
don't remove it, since not every stalled-but-working job is a gh-write job) but
this becomes the primary defense.
