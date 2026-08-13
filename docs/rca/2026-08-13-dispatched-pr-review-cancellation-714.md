# RCA: Dispatched PR-review failures in #714

Date: 2026-08-13
Issue: #714

## Conclusion

The `stopReason: "cancelled"` values in the Grok jobs are not produced by
synlynk's stall killer. Synlynk launches the harness as a child process and
does not impose a total wall-clock limit, a turn limit, or a review-specific
limit. The `stopReason` is harness/session output. With the evidence available
in #714, the exact upstream issuer (Grok session policy, an upstream model
session cancellation, or an external cancellation) cannot be distinguished;
the dispatch-side stall path is ruled out.

## Code path

`dispatch_agent()` builds the harness command and starts it with
`subprocess.Popen()` (`synlynk/dispatch.py:2268-2300`). The process writes its
own output to the job log. There is no `timeout=` or `max-turns` argument in
that launch path.

On a later synlynk invocation, `_reconcile_jobs()` calls
`_check_job_stall()` (`synlynk/jobs.py:1100-1115`). The stall check:

1. only considers jobs still marked `running`;
2. reads the configured per-agent timeout, defaulting to 30 minutes;
3. compares the current time with the log file mtime;
4. preserves jobs with local or remote git activity; and
5. only then sends `SIGKILL`, marks the job `failed`, and writes
   `STALL_NO_OUTPUT` (`synlynk/dispatch.py:498-570`).

Therefore it cannot explain a Grok JSON response containing
`stopReason: "cancelled"` after six active review turns. It also does not
kill a process after six turns or after a fixed total duration.

## `job-9441105d`

`timeout waiting for response` is a distinct harness-internal failure mode,
not the stall killer. Synlynk recognizes that phrase through
`HARNESS_TIMEOUT_PATTERNS` (`synlynk/_constants.py:15-17`) while reconciling a
dead child (`synlynk/jobs.py:1217-1260`). It classifies the job as an internal
harness timeout and may retry a clean job, otherwise it writes
`HARNESS_INTERNAL_TIMEOUT`.

This is consistent with the earlier #162 RCA: Agy emitted the error after
roughly 500-600 seconds while output was still advancing, so synlynk's
30-minute idle-log stall check did not fire. The error is therefore not the
same mechanism as Grok's `stopReason: "cancelled"`, even though both prevent
task delivery.

## Review versus implementation budgets

No evidence justifies changing the 30-minute stall threshold or adding a
review-specific turn budget. The current threshold is an idle-output safety
valve, not an implementation-task budget. A review that keeps emitting log
output can run longer than 30 minutes; a silent implementation or review can
be killed after the same idle interval. The code has no task-type branch in
this decision.

A future change could add explicit harness/session telemetry (including the
agent version, stop reason, turn count, and cancellation source) before tuning
thresholds. Without that evidence, increasing the threshold would only make
true silent hangs take longer to recover and would not address the observed
Grok cancellation.

## Separate fresh evidence

The Agy scratch-worktree-missing failure and the Grok job that reviewed the
wrong branch are worktree/orchestration failures, not stall or timeout
failures. The corrupted review template is already covered by open issue #411;
the Grok CWD/worktree relocation risk is covered by open issue #342. They are
not duplicates of #714.
