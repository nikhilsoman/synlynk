---
title: "gh:#1924 PR5 — Claude, Local, and the End of the Strangler Pattern"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 243
pr: "1967"
issue: "1924"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, harness-adapters]
type: story
---

## The Broader Goal at the End of the Previous PR

PR4 (#1965) had just put Agy on the `HarnessAdapter` protocol, leaving one port outstanding. The
goalpost coming into PR5 was explicit from #1965's own closing line: port Claude and local, then
delete `LegacyAdapter` once nothing in the registry still depends on it — closing out gh:#1924
entirely.

## Strategic Shifts in This PR

The plan said "delete `LegacyAdapter`." The PR that shipped does not. That's not scope creep —
it's a correction the first version of this PR got wrong and CI caught immediately.

`dispatch_agent()`'s original fallback was:

```python
try:
    adapter = get_adapter(request.agent)
except KeyError:
    from synlynk.harness_adapters.legacy import LegacyAdapter
    adapter = LegacyAdapter(agent=request.agent)
```

PR5's first commit replaced this with a bare `get_adapter(request.agent)` call, on the
assumption that once all five core harnesses had adapters, nothing could still hit the
`KeyError` branch. That assumption was wrong: `muse` (Meta Muse, Milestone v0.20.0 Cluster D,
#1508) is a sixth harness that was never in scope for this five-harness migration, and it was
never going to get its own adapter here. All four CI matrix jobs failed identically —
`tests/test_muse_harness.py::test_muse_dispatch_flags_and_command_construction` raising
`KeyError: 'muse'` straight out of `registry.py`.

The fix restored the fallback exactly as it was, and un-deleted `legacy.py` and
`test_legacy_adapter.py`, which the same first commit had also removed. `LegacyAdapter` is now
explicitly permanent infrastructure — the generic landing spot for any harness name outside this
migration's five-harness scope, not a placeholder scheduled for deletion once the migration
finished. The strangler pattern strangled the *conditionals*, not the *concept* of a fallback.

## What This PR Shipped

- **`ClaudeAdapter`** and **`LocalAdapter`** implementing the `HarnessAdapter` protocol, matching
  the `translate_permissions()` / `build_cmd()` / `parse_output()` / `classify_failure()` /
  `resolve_model()` shape already established by `CodexAdapter`, `GrokAdapter`, and `AgyAdapter`.
- **`LocalAdapter` fails closed.** aider (the local/oMLX harness) has no mechanism to enforce a
  read-only or file-scope restriction, so `translate_permissions()` raises
  `PermissionEnforcementError` the moment any permission is requested, rather than silently
  granting full read/write access it can't actually bound. Architect review specifically verified
  this is enforced, not just asserted in a test.
- **`registry.py`** now registers exactly five harnesses — `codex`, `grok`, `agy`, `claude`,
  `local` — and nothing else. `muse` (and any future sixth harness) stays on the `LegacyAdapter`
  fallback by design.

## Caught in Review

Two things surfaced after the muse regression was fixed, both before merge:

1. **A real merge conflict**, not a stale GitHub cache artifact. PR #1962 landed on `main`
   mid-flight, also touching README's test-count badge/hero line — the same CI gate that had
   already bitten PR4 and PR4's predecessor. `gh pr update-branch` correctly refused (it only
   handles non-conflicting fast-forwards), so the fix was a manual merge, re-running
   `pytest --collect-only -q` on the merged branch to get the *true* count (3764) rather than
   taking either side's stale number, and patching both the badge and the hero line to match.
2. **Branch protection caught a second gap after merge, on the next PR in the queue.** #1966
   (this same session's blog-batch PR) merged to `main` just ahead of #1967, which put #1967's
   branch `BEHIND` again. One `gh pr update-branch` cycle, a CI re-run (all six checks green),
   and the merge went through clean — exactly the "at most 2 update-branch → CI-wait cycles"
   discipline this repo's PR Review Discipline calls for.

Architect review (non-author, routed here rather than qa because this PR is
architecture-impacting — it closes a cross-cutting migration) verified the restored fallback,
confirmed `legacy.py`/`test_legacy_adapter.py` exist, confirmed the registry's exact five-harness
membership, and ran the full suite: 3,759 passed, 4 skipped, 1 sandbox-only logger failure that
passes with an isolated writable `HOME`. Approved.

## What Was Achieved Toward the Long-Arc Goal

All five harnesses — Codex, Grok, Agy, Claude, local — now route through dedicated
`HarnessAdapter` implementations instead of the scattered if/elif branching that used to live
directly in `dispatch_agent()`. Each of the four ports in this series caught something real
before it shipped: Grok's port surfaced a stale capability-routing bug; Agy's port caught a
missing lifecycle-telemetry population; Claude/local's port caught its own regression against a
harness explicitly outside the migration's scope. The pattern did exactly what it was brought in
to do — turn harness-specific quirks into isolated, testable, single-adapter concerns instead of
silent gaps in a shared conditional.

gh:#1924 is closed.

## The New Goalpost

The adapter migration itself is done; what it leaves behind is a cost-anomaly thread worth
watching. Three of the four dispatch jobs that reviewed and fixed this PR cluster (#1966 and
#1967 together) ran 6x–130x over their own preflight cost estimates, two of them tripping
critical cost-inflation sentinels ($14.69 and $21.34 on jobs whose estimates were under a
dollar). Filed as #1969 rather than folded into the five prior cost-inflation issues that closed
without a hard cap — this one has harder evidence (same session, same PR cluster, consecutive
jobs) and a specific suspected mechanism (conflict-resolution retries inside a dispatch possibly
not respecting `--context-mode`'s intent to minimize injected context). That's the next thread to
pull, not another adapter port.

Refs #1924, #1969.
