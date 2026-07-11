# Harness-Internal-Timeout Detection & Stall-Check Generalization — Design

**Tracks:** [#162](https://github.com/nikhilsoman/synlynk/issues/162) — Agy dispatch: no heartbeat/progress signal to distinguish stall from harness-internal timeout

## Problem

Three independent Agy dispatch attempts in the rxcc project (job-48c8a6db, job-0bb76dbe, job-44ed2b8a — see issue #162 and its comment thread) all died with the identical generic `Error: timeout waiting for response` from inside the `agy` CLI itself, at three structurally unrelated points in their respective tasks (607s during a package install, 549s mid-investigation, 518s during local verification). Landing in a tight ~500–600s band across three unrelated stages points to a fixed-duration idle/response timeout inside the `agy` binary's own response-wait logic — not anything task-, network-, or install-specific.

This is **not** synlynk's own stall detector. `_check_job_stall` (`synlynk/dispatch.py:190`) only fires after `stall_timeout_minutes` (default 30) of *zero* log output, and all three failures happened at ~9–10 minutes with active output already on the log — the function's very first content check (`if os.path.getsize(log_file) > 0: return False`) bails out immediately once any output exists, regardless of how stale that output later becomes.

Two distinct gaps result:

1. **No distinguishing signal.** When the `agy` process dies from its own internal timeout, `_reconcile_jobs()` (`synlynk/__init__.py:3144`) marks the job `"failed"` exactly the same way it would for a genuine task failure or crash. There's nothing in job history, `sentinel list`, or `doctor` output that says "this died because the harness gave up on itself," as opposed to "the agent failed the task."
2. **`_check_job_stall`'s all-or-nothing check.** A job that produces output early and then goes genuinely silent (a real hang, as opposed to the observed self-terminating timeout) is never caught by the stall detector today, because the detector's first branch exits the moment the log is non-empty — it never re-checks whether that non-empty log has gone stale.

## Design

### Part 1 — Detect and tag the known timeout signature

Add a new pattern list to `synlynk/_constants.py`, alongside the existing `QUOTA_PATTERNS` (`synlynk/_constants.py:9-13`):

```python
HARNESS_TIMEOUT_PATTERNS = [
    "timeout waiting for response",
]
```

Following the same convention `QUOTA_PATTERNS` already uses in `check_sentinel_patterns()` (`synlynk/sentinel.py:355-362`) — a list, not a single hardcoded string, so a second harness surfacing its own distinctly-worded internal timeout later is a one-line addition, not a repeat of the #160 anti-pattern (a hand-maintained literal nobody remembers to update).

In `_reconcile_jobs()` (`synlynk/__init__.py`), in the `except ProcessLookupError:` branch (~line 3198-3236) — the path taken when a dispatched job's PID is found to be dead — `log_text` is already read at line 3230-3232 for `_extract_micro_rework`/`_write_capability_rating`. Immediately after that read, and only when `job["status"] != "completed"` (i.e. the job did not exit cleanly), scan `log_text.lower()` against `HARNESS_TIMEOUT_PATTERNS`. On a match, call:

```python
_write_sentinel_alert(
    "CRITICAL", "HARNESS_INTERNAL_TIMEOUT",
    f"Job {job.get('id')} on agent '{job.get('agent')}' died from an internal "
    f"harness timeout (matched \"{matched_phrase}\"), not a task failure. "
    "Consider retrying.",
    sentinel_path,
)
```

This mirrors the existing `QUOTA_EXHAUSTED` detection in `check_sentinel_patterns()` exactly (same `_write_sentinel_alert` call shape, same "scan text for known phrase, alert with the matched phrase in the message" pattern) — just relocated to the job-reconciliation path, since this failure mode is specific to dispatched background jobs, not the foreground `exec` command that `check_sentinel_patterns()` already covers.

### Part 2 — Generalize `_check_job_stall` from "log is empty" to "log stopped advancing"

Current code (`synlynk/dispatch.py:190-198`):

```python
def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False
    if os.path.getsize(log_file) > 0:
        return False
```

The `if os.path.getsize(log_file) > 0: return False` line means the entire stall-kill logic that follows (elapsed-time check, git-activity extension guard, `SIGKILL`, sentinel alerts) is unreachable for any job that has ever written a single byte of output — which describes essentially every real dispatched job within the first few seconds.

Replace the size check with an mtime-staleness check, reusing the *same* `stall_timeout_minutes` config value already computed later in the function (no new config knob) — the elapsed-time computation moves earlier so it can gate both the old "genuinely empty" case and the new "gone stale" case with one check:

```python
def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)

    stale_minutes = (time.time() - os.path.getmtime(log_file)) / 60
    if stale_minutes < timeout:
        return False
```

(The `agent`/`global_timeout`/`timeout` computation is moved up from its current position later in the function — see full diff in the implementation plan — and the old `started_val`/`started_ts`/`elapsed_minutes` block, which gated on job *start* time rather than log *modification* time, is removed since `stale_minutes` now serves the equivalent gating purpose using the more precise signal.)

Everything below this point in the existing function — the git-activity extension guard (`_inspect_worktree_git_state`, "Stall check extended..." message), the `SIGKILL`, marking the job `"failed"`, and the existing `STALL_NO_OUTPUT`/`HANDOFF_PENDING` sentinel alerts — is unchanged. This is a detection-condition swap, not a rewrite of the kill/alert logic.

**Why reuse `stall_timeout_minutes` rather than add a new config knob:** the issue's own scope note frames this as "log output stopped advancing for N minutes," using the same duration semantics the existing knob already expresses — introducing a second, separately-configured timeout for what is conceptually the same "is this job still alive" question would be a YAGNI violation with no requirement backing it.

**Why this doesn't double-alert for the 3 reported attempts:** in all 3 reported cases, the `agy` process died on its own (self-terminated from its internal timeout) well before 30 minutes elapsed — `_check_job_stall` never fires for those cases either before or after this change, since the job's PID is already dead and `_reconcile_jobs()` handles it via the `ProcessLookupError` branch (Part 1), not the stall-check branch. Part 2 addresses the *complementary* failure mode — a process that hangs without dying — which the issue's point 2 flags as a related but distinct gap, not something the 3 reported attempts themselves exhibited.

### What does NOT change

- The root ~500–600s timeout inside the `agy` binary itself — external to synlynk, not fixable from this codebase.
- No new background heartbeat-writer thread/process (considered and declined — see "Out of scope" below).
- No new CLI flags or config knobs — Part 2 reuses `stall_timeout_minutes` exactly as it exists today.
- The git-activity extension guard, kill logic, and existing `STALL_NO_OUTPUT`/`HANDOFF_PENDING` alerts in `_check_job_stall` are unchanged.

## Testing

Two tests, covering Part 1 and Part 2 independently:

1. **Harness-timeout tagging:** simulate `_reconcile_jobs()` encountering a dead job (`os.kill` raising `ProcessLookupError`) whose log file contains `"Error: timeout waiting for response"` and no `.exit` file (so `exit_code` stays `None`, `job["status"]` becomes `"failed"`). Assert a `CRITICAL` `HARNESS_INTERNAL_TIMEOUT` alert is written to the sentinel file, containing the job id and the matched phrase.
2. **Stall-check catches a gone-stale (non-empty) log:** call `_check_job_stall()` directly with a job whose `status` is `"running"`, whose log file has non-empty content, and whose mtime is set (via `os.utime`) to more than `stall_timeout_minutes` in the past. Assert it returns `True` and the job is killed/marked `"failed"` — behavior that the current all-or-nothing size check would never produce for a non-empty log, regardless of staleness.

A third test should confirm no regression: `_check_job_stall()` with a *fresh* non-empty log (mtime within the timeout window) still returns `False` — i.e. the common "job is actively running and writing recent output" case is unaffected.

## Out of scope

- Full heartbeat instrumentation (a background thread/process periodically writing liveness markers into the job log, independent of the agent's own output cadence) — considered as a third approach during design. Declined: requires a background writer that must be reliably cleaned up alongside the main dispatched process, meaningfully more implementation and failure-mode surface than this issue's priority (explicitly lower than #161 in the issue's own recommendation) justifies.
- Any change to the `agy` CLI's own timeout duration or behavior — not synlynk's code to change.
- Partial-progress/diff capture on failure (mentioned in the original rxcc handoff's "suggested general improvement," not in scope for this issue specifically).
- Issues #160 and #161 — both already shipped (PR #164 and PR #163 respectively).
