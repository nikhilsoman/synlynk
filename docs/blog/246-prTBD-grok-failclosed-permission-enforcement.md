---
title: "gh:#1925 Part 1 — Making Grok's Permission Bypass Explicit, Not Implicit"
date: 2026-10-04
series: "Building the OS for Multi-Agent Development"
post: 246
pr: "2002"
issue: "1925"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, harness-adapters, security]
type: story
---

## The Broader Goal at the End of the Previous PR

The gh:#1924 strangler-pattern migration had just finished porting all four core harnesses
(Codex, Grok, Agy, Claude/local) onto the typed `HarnessAdapter` Protocol, with `LegacyAdapter`
kept as fallback. That work made each harness's permission-translation logic a single,
independently-testable method instead of a branch buried in `dispatch_agent()`'s shared
conditionals. The goalpost at that point was architectural: get every harness onto the same
interface so quirks stop leaking across harness boundaries.

gh:#1925 ("Safe-by-default execution") is a different kind of goalpost — not architecture, but
a security posture audit of what that newly-explicit interface was actually doing. Row 6 of
the roadmap's decide-panel review flagged `--dangerously-skip-permissions`-equivalent bypasses
as an implicit default across the fleet, with a credible launch-blocking trust objection from
the five-POV review's Founder/VC/Influencer sections. Part 1 of that issue is scoped to exactly
one finding: Grok's bypass wasn't opt-in like every other harness's — it was unconditional.

## Strategic Shifts in This PR

None within part 1's own scope. The spec explicitly carves containerized/sandboxed execution
for untrusted harnesses out as gh:#1925 part 2, future work. The one piece of nuance the design
had to hold onto: Grok's bypass isn't simply a bug to delete. LIVE-13
(`docs/rca/2026-09-22-LIVE-13-grok-headless-dispatch-permission-bypass.md`) already root-caused
*why* it became unconditional — Grok's CLI has no working non-bypass headless mode, and under
`--permission-mode dontAsk` it silently cancels compound tool calls while reporting a false
success. The fix had to preserve that escape hatch while making it an explicit, gated choice
instead of a baked-in default.

## What This PR Shipped

Six tasks, each a small commit on `docs/claude/grok-failclosed-permission-design`:

1. **Baseline cleanup** — `synlynk/_constants.py`'s Grok entry dropped `required_flags:
   ["--always-approve"]` down to `[]`, matching Claude/Agy's already-correct opt-in baselines.
2. **Gate the flag-translation function** — `_grok_permission_flags(permissions,
   skip_permissions=False)` now raises `PermissionEnforcementError` (the same class `local`'s
   adapter already uses) when permissions are requested and the caller hasn't opted in, instead
   of silently returning the bypass flags.
3. **Gate the dispatch-flags helper** — `_dispatch_flags_for_agent` only appends
   `--always-approve` for Grok when `skip_permissions=True`, mirroring the existing
   `--dangerously-skip-permissions` gating for Claude/Agy.
4. **Auto-opt-in at the call site** — `dispatch_agent()` sets `skip_permissions = True`
   specifically for Grok when the caller didn't pass it explicitly. This is the piece that keeps
   LIVE-13 closed: every existing Grok dispatch workflow keeps behaving exactly as before, with
   the bypass now a named, commented, auditable decision instead of an implicit baseline.
5. **Consolidate the error class** — `PermissionEnforcementError` existed as two independently
   defined, same-named classes in `dispatch.py` and `harness_adapters/local.py`. Both now import
   a single canonical definition from `harness_adapters/base.py`, and `GrokAdapter`/
   `LegacyAdapter` both raise and can be caught via either module's imported name — verified with
   a dedicated identity test (`test_harness_adapter_permission_error_identity.py`).
6. **Full regression pass** — verification only, no code changes: all 9 touched test files
   (908 tests) plus the full suite (3,771 tests) pass clean, and a grep confirms no stray
   unconditional `--always-approve` baseline remains anywhere in `_constants.py`.

Every task followed TDD — failing test written and confirmed failing against the pre-change
code first, then the minimal implementation, then confirmed passing — dispatched one at a time
to Codex per the project's Capability-Based Task Allocation (cli-plumbing/refactor work routes
to Codex by default), with each commit independently verified against `git diff`/`git show` and
a direct `pytest` run rather than trusting the dispatch job's self-reported status label. Two of
the five implementation jobs self-reported `FAILED` despite being fully correct, and a plan
sequencing inconsistency surfaced mid-execution — Task 3's own sanity-check step assumed a test
would still pass at a point in the sequence where Task 2's already-landed enforcement made it
fail until Task 4 landed. That was resolved by narrowing the retry's verification scope rather
than treating it as an implementer error, consistent with the project's standing discipline of
distrusting job-status labels symmetrically in both directions.

## What Was Achieved Toward the Long-Arc Goal

gh:#1925's first finding is closed: every core-fleet harness's permission bypass is now
opt-in and explicit in code, with Grok's necessary exception documented at the exact point it's
exercised rather than living silently in a baseline table. The `PermissionEnforcementError`
consolidation is a small but genuine step toward the kind of single-source-of-truth adapter
layer the gh:#1924 migration was building toward — one error class, one identity, catchable from
either import path, instead of two classes that happened to share a name.

## The New Goalpost

gh:#1925 part 2 — containerized execution for untrusted/third-party harnesses, building on the
not-yet-wired-in `Dockerfile.sovereign` work — is the next piece of the safe-by-default posture
audit, and gets its own spec once this part merges.

Refs #1925.
