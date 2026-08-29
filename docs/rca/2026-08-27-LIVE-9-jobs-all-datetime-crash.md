# [LIVE-9] `synlynk jobs --all` crashes with TypeError comparing offset-naive and offset-aware datetimes

**Date:** 2026-08-27
**Severity:** Sev1 — a core, everyday command (`synlynk jobs --all`) crashes with a raw Python traceback instead of listing jobs. A user looking at the terminal after running it would immediately question whether the product works.
**Source:** Discovered by Claude (PM/review session) while checking job status shortly after dispatching a `claude --as-agent <qa-agent-id>` review job with `--gh-write-target-kind pr --issue N`, during the v0.18.0 release-prep session.
**Status:** Resolved. Fixed same-day in PR #1187, merged into `main`, shipped in v0.18.0.

## Impact

`synlynk jobs --all` crashed outright for any invocation where at least one listed job had `gh_write_target` set and its verification path ran during status rendering — i.e. any job dispatched with `--requires-gh-write`. Since gh-write verification is a normal, frequently-exercised path (QA review dispatches, PR-authoring dispatches), this was not an edge case — it reproduced consistently right after those jobs completed, blocking a routine status check with no workaround short of avoiding `jobs --all` entirely.

## Symptom

```
  File "synlynk/jobs.py", line 2183, in _apply_gh_write_verification
    verified = gh_write_verified(
        gh_write_target, expect=expect, since=since, expect_author=expect_author,
    )
  File "synlynk/gh_verify.py", line 97, in gh_write_verified
    if entry_dt is None or entry_dt < since_dt:
                           ^^^^^^^^^^^^^^^^^^^
TypeError: can't compare offset-naive and offset-aware datetimes
```

## Root cause

`_apply_gh_write_verification()` (`synlynk/jobs.py:2183`) passed `since` straight through to `gh_write_verified()` without normalizing its timezone-awareness. `since` originates from `daemon_jobs`-stored job timestamps (`job.started_at` or similar), which are persisted **without** a UTC offset — i.e. timezone-naive.

Inside `gh_write_verified()` (`synlynk/gh_verify.py`), `since` is compared directly (`entry_dt < since_dt`) against `entry_dt`, which is parsed from a GitHub API timestamp (e.g. a review's `submittedAt`) via `_parse_iso8601()`. GitHub API timestamps are ISO 8601 with a `Z`/UTC suffix, so `_parse_iso8601()` produced a timezone-**aware** `datetime`. Comparing a naive `datetime` to an aware one raises `TypeError` in Python — this is not a logic bug in the comparison itself, but a data-contract mismatch between the two callers of the same field.

The bug had been latent since `_apply_gh_write_verification` and `gh_write_verified` were wired together for gh-write verification; it only manifested once `jobs --all` rendering actually reached a job with `gh_write_target` set and a completed verification check, which requires the `--requires-gh-write` dispatch path to have been exercised — a narrower but still common combination.

## Fix

PR #1187 (merged 2026-08-27):

1. `_parse_iso8601()` (`synlynk/gh_verify.py`) now normalizes every parsed timestamp to UTC-aware before returning it — naive inputs get `.replace(tzinfo=timezone.utc)`, aware inputs get `.astimezone(timezone.utc)`. This makes the function's output contract unambiguous: always aware, always UTC.
2. `_apply_gh_write_verification()` (`synlynk/jobs.py:2183`) now runs `since` through `_parse_iso8601()` before passing it to `gh_write_verified()`, so both sides of the comparison go through the same normalization path instead of one being normalized and the other passed through raw.
3. Added a regression test (`tests/test_agent_cli.py`) that mocks a GitHub review response with a `Z`-suffixed `submittedAt` and asserts `gh_write_verified()` no longer raises when compared against a naive `since`.

## Prevention

The root issue was two call sites relying on an implicit, undocumented assumption ("timestamps here are already comparable") rather than a shared normalization boundary. `_parse_iso8601()` is now the single place that decides timezone-awareness for any timestamp entering comparison logic in this module — future call sites should route through it rather than constructing or passing `datetime` values ad hoc. No broader systemic gap identified beyond this one function pair; the fix is scoped and the regression test covers the exact failure mode.

## Timeline

- **2026-08-27, during release-prep session:** Crash observed while running `synlynk jobs --all` after a gh-write-verified dispatch.
- **2026-08-27:** Root cause identified (timezone-naive vs. aware datetime comparison), fix implemented, regression test added, PR #1187 opened and merged same day.
- **2026-08-27:** Shipped in v0.18.0.
- **2026-08-28:** Retroactively declared as a Live Issue (LIVE-9) as part of a post-release SOP audit — the fix was correct and fast, but the issue was closed as a plain `bug` without going through the Live Issues declare/label/RCA process at the time.
