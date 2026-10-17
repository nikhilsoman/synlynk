# [LIVE-25] Local pilot denial can be rerouted to host-side Aider

**Declared:** 2026-10-17  
**Severity:** Sev1 — isolation boundary violated  
**Tracking:** [#2405](https://github.com/nikhilsoman/synlynk/issues/2405), parent pilot [#2349](https://github.com/nikhilsoman/synlynk/issues/2349)

## Summary

An auto-routed dispatch rejected by Local Pilot admission was initially assigned
to the configured frontier fallback, then capability-rerouted to host-side
`local` Aider. The pilot class was denied and there was no signed isolated-runner
receipt, but the ordinary local adapter path still launched. The exact job was
stopped before model output; its worktree was unchanged. This run is excluded
from pilot evidence.

## Timeline and containment

- 2026-10-17: task text containing excluded `refactor` language was rejected
  with `task_text_excluded` by `evaluate_local_pilot`.
- Resolver selected the configured frontier fallback, but downstream capability
  routing selected `local` and started host-side Aider without a pilot receipt.
- The process was terminated before model output. No files were changed and no
  pilot receipt or exit receipt was produced for that attempt.
- `local_pilot.enabled` was set to `false` in the user workspace and disposable
  pilot worktree. `synlynk daemon status` reported the daemon not running and
  unhealthy, so there is no active daemon process to receive pilot traffic.
- #2405 tracks the fix. The Local Pilot must remain disabled until its
  acceptance criteria pass and independent QA approves the PR.

## Root cause

In `synlynk/dispatch.py::_resolve_dispatch_agent`, denied pilot admission returns
the configured frontier fallback but does not preserve a routing constraint.
The CLI then calls `dispatch_agent` without a receipt. Capability resolution
uses `force_agent=False`, allowing a later selection of `local`. The receipt
validation in `dispatch_agent` only runs when a receipt is present, so the
host-local adapter had no guard for a pilot-intended dispatch whose admission
was denied upstream.

The earlier fix in #2404 rejects an explicit `local` harness combined with
`--local-pilot-class`; it does not cover this auto-routing/fallback path.

## Impact

One excluded pilot task crossed the isolation boundary to host-side Aider. The
operator terminated it before model output; observed worktree state was clean.
The attempt is not an eligible or accepted sample and does not change the
recorded 8 accepted / 12 distinct eligible tasks baseline.

## Corrective actions

Tracked in #2405:

1. Bind pilot-intended dispatches to the resolver's selected harness so later
   capability routing cannot silently select local execution.
2. Enforce at the dispatch boundary that pilot-intended local execution requires
   a valid signed admitted receipt.
3. Cover denied admission and downstream capability-reroute behavior in tests,
   including normal non-pilot routing regression coverage.
4. Keep the pilot paused. After merge, inspect the actual runtime/config state,
   reconcile the evidence ledger, and make a separate decision whether resuming
   at 20% is warranted. No promotion is authorized.
