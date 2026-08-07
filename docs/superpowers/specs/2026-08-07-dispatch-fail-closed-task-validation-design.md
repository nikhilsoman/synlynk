# Fail-closed empty-task validation and dispatch inspectability

**Status:** Approved for planning
**Parent issue:** [#720](https://github.com/nikhilsoman/synlynk/issues/720) — "Fail closed on empty dispatch tasks and enforce task/scope integrity"

## Problem

On 2026-08-05, a Codex home harness dispatched Synlynk jobs where `--task` was constructed from an orchestration-language variable that never made it into the shell environment. Shell expansion passed an empty string. `dispatch_agent()` had no check for this — it went ahead and created a story, a job record, a worktree, and (in one case) let the agent infer scope from issue context and open an unrelated PR that had to be closed.

There is currently no mechanical guard against an empty or whitespace-only task reaching `dispatch_agent()`, and no way to inspect what a dispatch would actually send before committing to the side effects (worktree creation, cost entry, job record).

## Scope

Issue #720 describes six required behaviors. Three of them — a cross-CLI receipt protocol between Synlynk and each headless harness (Claude/Codex/Grok/Agy), first-class scope enforcement (`SCOPE_VIOLATION`, design-only/docs-only as a capability), and the `PERMISSION_DENIED` terminal-status misclassification — are independent subsystems, each substantial enough to need its own brainstorm and spec. This spec covers only:

1. Reject empty/whitespace `--task` before any side effect (job, worktree, story, cost entry).
2. Make the effective dispatch inspectable before it happens (`dispatch --dry-run`).
3. Make the effective dispatch inspectable after it happens (extend the existing `jobs --summary <id>`).
4. Document safe caller construction.

**Explicitly deferred**, to be filed as follow-on issues once this ships:
- Receipt protocol (`task_received` event, digest matching, `TASK_DELIVERY_FAILED` as a job status)
- Scope enforcement (`SCOPE_VIOLATION`, design-only/docs-only capability)
- Terminal-status classification fix for false-positive `PERMISSION_DENIED` — this belongs with #701's job-status-truthfulness work, not here, since it's about interpreting agent output, not about task validity.

### Scope correction vs. the parent issue

Issue #720's acceptance tests ask for a simulated unset shell variable to produce a `TASK_DELIVERY_FAILED` job. Under this spec's scope, an empty task is rejected *before* a job is created — there is no job to label. `TASK_DELIVERY_FAILED` as a status therefore belongs to the deferred receipt-protocol work (where a job legitimately exists and the harness fails to confirm it received the task). This spec's empty-task case surfaces as a CLI error (`Error: ...`, exit 1) with no job, worktree, or cost entry ever created — a stronger guarantee than a labelled failed job, just not literally the status name the issue used.

## Design

### 1. Where the check lives

`dispatch_agent()` in `synlynk/dispatch.py`, not just the CLI argparse layer — so every caller (CLI, internal code, a future SDK) is protected, not only `synlynk dispatch`. Placed as the first statement in the function, before story resolution, worktree creation, or any DB write:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None, ...) -> dict:
    if not task or not task.strip():
        raise ValueError(
            "--task is empty or whitespace-only; refusing to dispatch (see #720)"
        )
    ...
```

This follows the existing error convention in the function (e.g. `Unknown agent: '{agent}'`), which `cmd_dispatch` already catches:

```python
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)
```

No new exception type or status label needed — this reuses an existing, tested path.

### 2. `dispatch --dry-run`

New flag on the `dispatch` subcommand. When set, computes and prints the same data a real dispatch would use, then exits without creating a job, worktree, or cost entry.

```
$ synlynk dispatch claude --task "" --dry-run
Error: --task is empty or whitespace-only; refusing to dispatch (see #720)

$ synlynk dispatch claude --task "Fix issue #720..." --dry-run

agent:        claude
task (142 chars):
  Fix issue #720 fail-closed on empty tasks...
task_sha256:  a3f9c2e1b8d4...
context_mode: task
context.md:   sha256=8b1e40...  (4,213 bytes)
capabilities: requires_gh_write=false

(dry run — no job, worktree, or cost entry created)
```

Implementation: a new pure function `_render_dispatch_preview(agent, task, context_mode, ...)` in `synlynk/dispatch.py`, called by both `--dry-run` and (for the digest/preview fields specifically) the real dispatch path when it later writes the job summary. Sharing the computation means the preview and the eventual job record are provably the same data, not two hand-maintained copies that can drift apart.

The empty-task check runs *before* the dry-run branch, so `--dry-run --task ""` still fails closed rather than printing a preview of nothing.

### 3. `jobs --summary <id>` extension

This command already exists (`synlynk/dispatch.py:_job_summary_path`, writes to `.synlynk/logs/<job_id>.summary`) and already has a `synlynk jobs --summary <id>` CLI path. No schema change — this only adds two fields to the existing text format, populated at job-completion time from data already available (the task text stored in `daemon_jobs.task`):

- `task_sha256`: sha256 of the exact task text used for this job
- `task_preview`: first ~200 chars of the task text, newlines collapsed to spaces, for a quick eyeball check without opening the full log

`_format_job_summary()` and `_write_job_summary()` gain two new optional kwargs (`task_sha256`, `task_preview`); the `jobs.py` call sites that already invoke `_write_job_summary` pass them through using the task text they already have in scope.

### 4. Digest computation

`task_sha256` is `sha256(task).hexdigest()` on the exact string passed to `--task` — no stripping or normalization before hashing, so what's hashed is exactly what would be sent. (The emptiness *check* uses `.strip()` to catch whitespace-only tasks; the *digest*, computed only after that check passes, hashes the raw value.)

### 5. Documentation

Short addition to the README's dispatch section: don't interpolate unchecked shell variables into `--task` (the exact failure mode from the 2026-08-05 incident); prefer `synlynk dispatch ... --dry-run` as a sanity check in automation before a real dispatch.

## Testing

- Empty string and whitespace-only `--task` both raise `ValueError` from `dispatch_agent()` before any job/worktree/story/cost-entry side effect — assert via monkeypatching the worktree-creation and DB-insert functions and confirming they're never called.
- `dispatch --dry-run` with a valid task prints task text, `task_sha256`, `context_mode`, and (when `context_mode != "none"` and `.synlynk/context.md` exists) its digest and size — and creates no job.
- `dispatch --dry-run --task ""` still fails closed with the same error, before any preview is printed.
- `jobs --summary <id>` on a completed job includes `task_sha256` matching a locally computed `sha256(task_text)`, and a truncated `task_preview`.
- `_render_dispatch_preview()` is unit-testable in isolation (pure function, no I/O side effects beyond reading `context.md` if present).

## Non-goals (see Scope)

No `task_received` receipt protocol, no `SCOPE_VIOLATION` enforcement, no change to terminal-status classification for `PERMISSION_DENIED`. No new `daemon_jobs` schema column — deliberately avoided given the schema-drift regression in #740/PR #744 two days prior; digest/preview live in the job summary file, not the DB.
