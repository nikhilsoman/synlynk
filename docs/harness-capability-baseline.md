# Harness Capability Baseline

> ⚠️ **SUSPENDED as the source of truth for routing, 2026-10-04.** This doc's
> hand-written Reliable/Unreliable/Untested findings were a reasonable interim
> signal, but Nikhil's 2026-10-04 reassessment moves routing to empirical
> measurement from `capability_ratings`/`cost_entries` (median `pr_review_cycles`
> + `total_cost_usd` per merged PR, min n≥5 samples) instead — see the Empirical
> Capability Assessment Policy in `CLAUDE.md`. The qualitative findings below
> (e.g. Grok's sandbox/billing issues, Codex's gh-write egress config) remain
> useful *evidence* to corroborate or explain an empirical result, but no finding
> here should drive routing on its own going forward. Blocked on `state.db`
> consolidation (#1926) before aggregate measurement is reliably queryable.

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
| **Claude** | Reliable — PM/deploy role, direct `gh` calls | Reliable — direct, this is how self-authored PRs get reviewed today (COMMENT-checklist fallback, #423/#1124) | N/A (role-locked out of implementation, see CLAUDE.md role split) | Not dispatched for gh-write; runs `gh` directly as PM/deploy. Baseline `roles` aligned to `["architect", "pm"]` (was `["architect", "builder"]`) — `builder`/implementation was never actually reliable or in-scope for Claude per the locked role split |
| **Agy** | Reliable fallback for headless gh-write (PRs #589, #594, #880) | Authorized fallback (`.synlynk/policy.json` `review` task_type) | Reliable for CSS/templates/content/subpages | Prone to "timeout waiting for response" on overlapping-lane work — prefer Codex/Grok for implementation when lanes overlap (see memory `feedback_prefer_codex_grok_over_agy`) |
| **Codex** | **Reliable** — PR #1271 configuration override; verified live in job `job-836e13a4` | **Reliable** — review dispatches use `workspace-write` with `sandbox_workspace_write.network_access=true` and `sandbox_workspace_write.writable_roots=[]`; this preserves network egress while denying working-tree writes (RCA for #1274) | Reliable — primary harness for implement/test/refactor/cli-plumbing | Codex `read-only` unconditionally blocks DNS and TCP egress; never pair it with gh-write review dispatches. Network access is granted only for explicit gh-write dispatches, with review filesystem isolation enforced by the empty writable-roots override |
| **Grok** | **Unreliable** headless — session-expiry or 402 billing exhaustion observed (PR #880); GitHub-write reliability remains unresolved | **Unreliable, confirmed 2026-08-25** (LIVE-8, issue #1166, PR #1177) — gh-write/review reliability remains unchanged | Reliable for canvas/JS/infra scaffold/complex data structures | As of 2026-10-03, shell dispatch works via `--always-approve` + `--permission-mode bypassPermissions` since #1277. `synlynk/capability_probe.py` had a separately stale shell deny until this fix; GitHub-write remains unreliable and is unchanged. |
| **Meta Muse** | **Reliable** — PR #1508; first-class CLI adapter in `synlynk/dispatch.py` with `can_gh_write: True` | Reliable — verifier/builder role | Reliable — surgical refactoring, algorithmic synthesis, automated tests | Meta Muse CLI (`muse run --non-interactive -C <worktree> --prompt ...`) integrated in Milestone v0.20.0 Cluster D (#1508) as next-gen commercial model adapter |

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

## Test execution baseline (2026-09-09)

Issue #1496 evaluated pytest-xdist after the #1494/#1495 CI changes. The current
CI baseline is serial: the comparable post-#1495 run took 231s on Python 3.10
and 165s on Python 3.12. A local Python 3.12 run took 426.78s serial, 180.40s
with four workers, and 162.07s with `-n auto` (16 workers), but all three runs
shared the same pre-existing live-selftest mutation failure. Keep CI serial;
see `docs/testing/pytest-xdist-evaluation-1496.md` for the classification and
scoped experiment command.
