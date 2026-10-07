---
title: "PR #2081 — A Conformance Suite That Names Adapter Drift Instead of Discovering It Live"
date: 2026-10-06
series: "Building the OS for Multi-Agent Development"
post: 260
pr: "#2081"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# PR #2081 — A Conformance Suite That Names Adapter Drift Instead of Discovering It Live

## The Broader Goal at the End of the Previous PR

v0.24.0 still needs dispatch to be trustworthy across every registered
harness. The GOVERNS preflight now names a missing `--issue`/`--pr`/`--story`
before #1990 can hard-fail. The remaining gap called out in the three-lens
review was adapter quality: receipt markers, cost attribution, and failure
classification were only checked live, after a regression had already
shipped.

## Strategic Shifts in This PR (if any)

No strategy change. #2062 still owns the incomplete strangler retirement.
This PR only ships the narrowed Task D from the 2026-10-06 three-lens
follow-ups plan: a parametrized conformance suite over the five registered
adapters. Adapter implementation drift is tracked, not patched here.

## What This PR Shipped

- `tests/test_adapter_conformance.py` parametrizes `claude`, `codex`, `agy`,
  `grok`, and `local` for Protocol method presence, `translate_permissions`
  signature match against `HarnessAdapter`, receipt-marker parsing through
  `jobs._check_task_receipt`, `classify_failure` returning `FailureKind` or
  `None`, and one `extract_tokens` fixture per harness.
- Claude/Codex/Agy `translate_permissions` is missing the Protocol's
  `skip_permissions` parameter. Those three cases are `xfail` against
  [#2078](https://github.com/nikhilsoman/synlynk/issues/2078).
- `LocalAdapter.parse_output` leaves `compatibility_evidence` unset. Those
  two receipt cases are `xfail` against
  [#2079](https://github.com/nikhilsoman/synlynk/issues/2079).
- No adapter source files were changed.

Plan: `docs/superpowers/plans/2026-10-06-three-lens-followups-plan.md` Task D.
Design: `docs/superpowers/specs/2026-10-06-three-lens-followups-design.md`.

## Brainstorm Visuals Used

None. This follows the committed design and plan.

## What This Achieved on the Path to Autonomy

A new adapter, or a signature change on an existing one, now fails in
pytest instead of in a live dispatch. The suite is green because the known
drift is named and ticketed, not because it was papered over.

## Strategic Note: The Goal at the End of This PR

#2078 and #2079 are the next adapter-side fixes. The strangler-path
retirement still listed on #2062 stays a separate implementation task.
