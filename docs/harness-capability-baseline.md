# Harness Capability Baseline

Living record of what each dispatch harness (Claude, Agy, Codex, Grok) can actually
be trusted to complete headlessly, versus what it claims or appears to complete.
Dispatch routing in `.synlynk/policy.json` should track this doc, not the other way
around — when a reassessment finds drift, fix the policy and update this file in the
same PR.

**Why this exists:** capability isn't static. Harness vendors change models,
sandboxing, and tool access on their own schedule; synlynk's own verification
signal has had bugs (#1172, #1175) that produced false negatives; and a harness
that fails today may be fixed upstream next month with no changelog we'd see. A
one-time routing decision goes stale silently. See `docs/live-issue-handling-sop.md`
for how individual capability failures get investigated (LIVE-N process) — this doc
is the accumulated, standing output of that process across harnesses, reassessed on
a cadence rather than only when something breaks in production.

## How to read this table

- **Reliable** — repeatedly confirmed to complete the action end-to-end, verified
  independently (not just via the harness's own reported status).
- **Unreliable** — attempted but fails in a *specific, reproducible* way (sandboxed,
  times out, stalls, goes off-script). Not "never tried."
- **Untested** — no dispatch history to draw a conclusion from.

Each row cites the issue/PR where the finding was established, so a reassessment can
check whether that evidence is still current before trusting it.

| Harness | GitHub write (issue/PR ops) | PR review (non-authoring) | Implementation | Notes |
|---|---|---|---|---|
| **Claude** | Reliable — PM/deploy role, direct `gh` calls | Reliable — direct, this is how self-authored PRs get reviewed today (COMMENT-checklist fallback, #423/#1124) | N/A (role-locked out of implementation, see CLAUDE.md role split) | Not dispatched for gh-write; runs `gh` directly as PM/deploy |
| **Agy** | Reliable fallback for headless gh-write (PRs #589, #594, #880) | Authorized fallback (`.synlynk/policy.json` `review` task_type) | Reliable for CSS/templates/content/subpages | Prone to "timeout waiting for response" on overlapping-lane work — prefer Codex/Grok for implementation when lanes overlap (see memory `feedback_prefer_codex_grok_over_agy`) |
| **Codex** | **Reliable** — PR #1271 configuration override; verified live in job `job-836e13a4` | **Reliable** — tested live and authorized in `.synlynk/policy.json` | Reliable — primary harness for implement/test/refactor/cli-plumbing | Codex has first-class headless GitHub-write and review capability; network access is granted only for explicit gh-write dispatches |
| **Grok** | **Unreliable** headless — session-expiry or 402 billing exhaustion observed (PR #880); dispatch sandbox has also denied `bash` entirely in some cases (silent no-op, job status showed generic "OK" despite `git diff origin/main` showing zero changes) | **Unreliable, confirmed 2026-08-25** (LIVE-8, issue #1166, PR #1177) — job reported `status=done, exit 0, 0 files touched` but `gh pr view` showed zero reviews posted; Grok's own trace shows it verified the diff correctly, then went off-script into an unrelated denied `pytest` call and the session was cancelled (`stopReason: cancelled`) before reaching `gh pr review` | Reliable for canvas/JS/infra scaffold/complex data structures | Downgraded out of `review` task_type fallback in `.synlynk/policy.json` (PR #1177). Two distinct failure modes now on record for gh-write (auth/billing vs. execution-path derailment) — worth re-testing only after a specific fix lands upstream or in dispatch's execution wrapper, not on a blind retry |

## Known false-negative risks (don't over-correct on stale data)

- **Job status alone is not proof of completion.** `synlynk jobs` / job-report
  `status: done, exit 0` has been wrong in both directions — false-negative
  (`gh_write_expect` mismatch pre-#1172/#1175) and false-positive (this doc's Grok
  review row: exit 0 with zero actual write). Always independently verify the
  claimed side effect (`gh pr view --json reviews`, `git diff origin/main`, etc.)
  before updating this table, not the job wrapper's own summary.
- **"Unreliable" findings need a re-test trigger, not a blind retry.** Re-test a
  harness's capability only when something material changed — a version bump, a
  sandbox policy change, an upstream fix referenced in that harness's release notes
  — not just because time has passed. Blind retries burn budget and, per the Grok
  review case above, can even produce a *worse* false-positive if the underlying
  bug happens to not trigger that run.

## Reassessment cadence

See "Harness Capability Reassessment Protocol" in `CLAUDE.md`. Short version: at
least every ~25 dispatched jobs or monthly (whichever comes first), scan recent
job telemetry for failure patterns per harness, compare against this table, and
file findings + policy.json updates in the same PR as this doc's edits.
