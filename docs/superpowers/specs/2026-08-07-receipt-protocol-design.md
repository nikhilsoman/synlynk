# Receipt Protocol for Synlynk Dispatch — Design

**Status:** Draft, pending user sign-off
**Issue:** #720 (sub-project 2 of 3 deferred items)
**Depends on:** #720 sub-project 1, shipped in PR #759 (fail-closed empty-task validation, `task_sha256`/`task_preview` job-summary fields)

## Problem

After PR #759, Synlynk can reject empty tasks up front and can compute/report a `task_sha256` digest in job summaries. But it still can't tell whether a dispatched agent actually *received and understood* the task it was given, versus silently working from inferred/misremembered scope. This session hit a near-miss of the related failure mode live: job-b88e0f92 reported `PERMISSION_DENIED (headless auto-denied)` despite having done real, correctly-scoped work — a false-positive in the opposite direction, but proof that job self-reports and actual task fidelity can diverge in either direction without an independent signal to check against.

This sub-project adds a receipt protocol: every dispatched agent is instructed to echo the task's digest as its literal first line of output. Synlynk parses the log for that marker post-hoc and classifies delivery failures as a new job status, `TASK_DELIVERY_FAILED`, while guarding against false positives using corroborating git activity.

## Constraint: detection-only, not prevention

`dispatch_agent()` shells out to each CLI via `subprocess.Popen(["sh", "-c", shell_cmd], ..., start_new_session=True, cwd=worktree_path, env=proc_env)` (`synlynk/dispatch.py`) and only reads the resulting log file after the process exits. There is no live hook or IPC into any of the four harnesses (Claude, Codex, Grok, Agy) that could intercept or block an in-progress edit. Every mechanism in this design is therefore post-hoc log inspection, mirroring the existing `_log_has_permission_denied_signature()` idiom in `synlynk/costs.py`. This is a deliberate, accepted limitation, not a gap to close later within this sub-project.

## Design

### 1. Receipt marker & prompt injection

A new helper in `synlynk/dispatch.py`:

```python
def _render_task_receipt_instruction(task_sha256: str) -> str:
    """Returns a prompt-prepend block instructing the agent to echo the
    task digest as its literal first output line."""
    return (
        "## Task Receipt (required)\n"
        "Before doing anything else, print this exact line as your very "
        "first output:\n"
        f"SYNLYNK_TASK_RECEIVED: {task_sha256}\n"
        "Then proceed with the task below.\n\n"
    )
```

`_format_prompt_for_agent()` (`synlynk/dispatch.py:774-804`) prepends this block identically across all branches (`codex`, `agy`, and the shared default covering `claude`/`grok`) — before the existing `story_ref`/task/context sections in each. No per-agent divergence: the marker format is plain text, so it works uniformly regardless of whether a given CLI natively emits structured JSON output.

`task_sha256` is computed once in `dispatch_agent()`, reusing the digest logic already introduced by `_task_sha256_and_preview()` in `synlynk/jobs.py` (PR #759, Task 5), and threaded through `format_prompt(...)` into `_format_prompt_for_agent()`.

### 2. Detection & `TASK_DELIVERY_FAILED` classification

A new function in `synlynk/jobs.py`, alongside `_log_has_permission_denied_signature()`:

```python
def _check_task_receipt(log_text: str, task_sha256: str) -> str:
    """Returns one of: 'ok', 'late', 'mismatch', 'absent'."""
```

Behavior:
- Splits `log_text` into non-empty lines; inspects the first one.
- `ok` — first non-empty line is exactly `SYNLYNK_TASK_RECEIVED: <task_sha256>`.
- `mismatch` — first non-empty line matches the `SYNLYNK_TASK_RECEIVED: ...` prefix but the digest differs from `task_sha256`.
- `late` — the correct marker appears somewhere in the log, but not as the first non-empty line.
- `absent` — no marker anywhere in the log.

Timing strictness is intentionally strict: any visible work before the marker line is itself evidence the agent didn't confirm the task first, so `late` is treated as a failure signal even when the digest is eventually correct. This is chosen specifically because a lenient "marker present anywhere" check would not have caught the original incident's actual failure mode (an agent inferring scope from issue context rather than a garbled digest).

In the reconciliation loop, at the same site as the existing `permission_denied` check (`synlynk/jobs.py:1136`), after `git_state` is computed:

```python
receipt_status = _check_task_receipt(log_text, task_sha256) if log_text and task_sha256 else None
has_corroborating_activity = bool(
    git_state and (git_state.get("has_activity") or git_state.get("remote_has_activity"))
)
if receipt_status in ("late", "mismatch", "absent") and not has_corroborating_activity:
    job["status"] = "task_delivery_failed"
```

Setting `job["status"]` away from `"completed"` reuses the exact mechanism `permission_denied` already relies on to skip the unconditional `_finalize_completed_worktree_job()` / `_apply_dispatch_gate()` block later in the same function (both are gated on `job.get("status") == "completed"`). No new gating logic is required. Summary output gains a new `status_label = "TASK_DELIVERY_FAILED"` (mirroring `"PERMISSION_DENIED (headless auto-denied)"`) plus a `note` naming which of `late`/`mismatch`/`absent` triggered it.

Per the detect-and-quarantine model: a `TASK_DELIVERY_FAILED` job's worktree and any file edits the agent already made are left in place for audit — not reverted or destroyed. Only the auto-finalize/push/merge path is skipped.

### 3. False-positive corroboration (WARN downgrade)

When `receipt_status` indicates failure but `has_corroborating_activity` is `True` (real commits or file changes exist in the worktree despite a bad/missing marker), the job's status is **not** overridden — it keeps whatever status it would otherwise have (`completed`/`failed`/etc.), and finalize/gate proceed normally. Instead:

```python
if receipt_status in ("late", "mismatch", "absent") and has_corroborating_activity:
    job["receipt_warning"] = receipt_status
```

This flows into the job summary as a non-blocking `⚠ task-receipt: <status>, but real work detected — not blocking` line, and into `_write_sentinel_alert()` at `WARN` severity (not `CRITICAL`), visible in `sentinel.md` for pattern review without blocking anything.

This corroboration guard exists specifically because of this session's own job-b88e0f92 incident (real, correctly-scoped work; misleading status label from an unrelated detector). The same shape of mistake — treating "signal absent" as "work absent" — is what this guard is designed to prevent for the new detector before it ever ships.

### 4. Data flow

```
dispatch_agent()
  → task_sha256 computed
  → format_prompt(...) → _format_prompt_for_agent() prepends receipt instruction
  → prompt_file written
  → subprocess runs, log accumulates
  → (job record already stores `task`; task_sha256 is recomputed at
     reconciliation time via the existing digest helper — no new
     persisted field needed)

reconciliation (synlynk/jobs.py, existing loop)
  → log_text read
  → git_state computed (existing)
  → receipt_status = _check_task_receipt(log_text, task_sha256)
  → combined with has_corroborating_activity
  → job["status"] set to "task_delivery_failed", or job["receipt_warning"] set, or neither
  → _write_job_summary() includes receipt_status alongside the existing
    task_sha256/task_preview fields (PR #759, Task 4)
```

### 5. Rollout scope

All 4 agents (Claude, Codex, Grok, Agy) at once, not phased. The marker mechanism is agent-agnostic — a prepended prompt instruction plus a plain-text log scan needs no per-agent adapter work — and cross-harness compliance testing is already required by #720's own acceptance criteria via `selftest --matrix`.

### 6. Testing

- Unit tests for `_render_task_receipt_instruction()` — output contains the exact marker prefix and the supplied digest.
- Unit tests for `_check_task_receipt()` — one case each for `ok` / `late` / `mismatch` / `absent`.
- Reconciliation tests, modeled on the existing `test_reconcile_jobs_marks_permission_denied_headless_auto_denial` pattern:
  - No marker + no git activity → job status becomes `task_delivery_failed`, summary contains the note.
  - Bad/missing marker + real commits present → job status unchanged, `receipt_warning` set, summary shows the WARN line, no hard failure.
- `selftest --matrix` gains one column: for each of the 4 agents, dispatch a trivial real task and assert the marker appears as the literal first non-empty log line. This satisfies #720's acceptance-test requirement for cross-harness receipt compliance.

## Non-goals

- No prevention/blocking of in-progress edits (ruled out by the detection-only constraint above).
- No change to `SCOPE_VIOLATION` classification (deferred #720 sub-project 3, separate brainstorm).
- No change to the `PERMISSION_DENIED` terminal-status misclassification logic itself (folded into #701, separate brainstorm) — this design borrows its detection *idiom*, not its code path.
- No structured JSON-based digest verification — plain-text marker only, so no agent-specific adapter work is needed and no assumption about Agy/Grok's headless JSON-line support is required.
