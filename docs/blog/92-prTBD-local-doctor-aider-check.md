---
title: "The Doctor That Didn't Check Its Own Patient — Closing a Gap in Local Agent Onboarding"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 92
pr: "TBD"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #641 (post #91) closed the fleet-parity security cluster, and with it the last of the eight fleet-parity audit issues that had a dedicated spec. Attention moved to a new goal — "Local Agents with Synlynk" — combining two threads: finishing the already-shipped aider+oMLX "Local" 5th agent rollout (design spec 2026-07-12, shipped as PR #204/205/207 per `docs/blog/55`), and evaluating herdr (a terminal multiplexer with agent-lifecycle awareness) as a possible new supervision layer. The user chose to sequence these: finish the rollout first, then brainstorm herdr.

## Strategic Shifts in This PR

Verifying "finish the rollout" turned out to require less architecture and more auditing than expected. All four originally-planned PRs for the Local agent had, in fact, already shipped — agent registration, capability-score seeding, tests, and docs all exist in the current codebase. Running `synlynk local doctor` live on this machine (oMLX installed but not running, Aider not installed at all) surfaced a real gap: the doctor command only ever checked oMLX reachability and the model roster, never whether `aider` — the agentic editor the entire design depends on — was even on `PATH`. On a machine with oMLX up and Aider absent, doctor would report fully healthy, and dispatching a `local` job would fail with a raw "command not found" instead of the actionable guidance every other doctor failure path already gives. No existing test covered `cmd_local_doctor()` at all, so the gap had no regression net either.

This reframed the rollout sub-project from "design something new" to "fix a narrow gap in an already-approved design's own onboarding surface." Rather than writing a fresh spec, the fix was backfilled directly into the original 2026-07-12 design spec (as an Addendum) and its implementation plan (as Task Group 6) — keeping the design history in one place instead of forking a parallel doc for a five-line function change.

## What This PR Shipped

One task, dispatched to Codex per the locked role split, verified via direct worktree diff and a full local test-suite run before merge — not from job-status summary alone (the dispatch's own "targeted command" verification step reported "no matching tests present," a display quirk worth flagging for anyone reading job summaries: the substantive regression-suite check it also ran separately passed cleanly, and re-running everything directly confirmed it).

- **`cmd_local_doctor()`** (`synlynk/local_agent.py`): added a `shutil.which("aider")` check, reported alongside the existing oMLX-reachability and model-roster checks rather than short-circuiting before them — one doctor run now surfaces every onboarding gap in a single pass. Return code is `1` if either the model roster or Aider itself is missing.
- **Two new tests** (`tests/test_local_agent.py`): the first test covering `cmd_local_doctor()` at all — one asserting a missing-Aider machine reports unhealthy even with oMLX fully up, one asserting a fully-healthy machine (both present) reports clean.

Full local-agent suite: 18 passed, 2 skipped (the real-hardware tier, correctly gated). Full project suite: 1538 passed, 2 skipped.

## Brainstorm Visuals Used

None — this was a text-only scope/sizing question ("spec it, patch it, or skip it"), not a visual one.

## What This Achieved on the Path to Autonomy

The Local agent's onboarding surface (`synlynk local doctor`) now tells the truth about whether a dispatch to it will actually work, closing the last known gap between "doctor says healthy" and "dispatch actually succeeds" for the 5th agent. This also demonstrates a lighter-weight version of the Design → Plan → Build discipline for genuinely small, already-scoped fixes: backfill into the existing spec/plan rather than spinning up parallel documents, while still keeping every change traceable to an approved design.

## Strategic Note: The Goal at the End of This PR

The "finish the rollout" sub-project is now complete — the only remaining items are operational (installing Aider, starting `omlx serve` on dev machines), not code. Next up: the herdr-integration sub-project's brainstorm, using the 7-item agenda already outlined (relationship to Vizor's "only web HUD" policy, whether `dispatch_agent()` should ever spawn inside herdr panes, permission-gating pattern mirroring the reliability cluster's `run:install`, ordering versus that still-pending reliability cluster spec, cost/telemetry implications, and the opt-in/no-breakage/ROI discipline every synlynk agent feature must clear).
