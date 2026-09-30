---
title: "R12 — Breaking Up the __init__.py God Module"
date: 2026-09-30
series: "Building the OS for Multi-Agent Development"
post: 233
pr: "TBD"
issue: "goal-079e2f37"
status: draft
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, refactor, architecture]
type: story
---

## The Broader Goal at the End of the Previous PR

The 2026-09-28 deep architectural review flagged `synlynk/__init__.py` as the project's
single largest correctness and readability risk: 3,937 lines, 570 function-level imports
(a workaround for circular-import boundaries), and 15 separate copies of the same `_pkg()`
helper function pasted across `synlynk/*.py` files — one per file that needed a lazy handle
back into the `synlynk` package. R9 through R11 had already been chipping away at other
god-module symptoms (instruction duplication, cost-table hardening); R12 was scoped
specifically to this file's own bloat and its most-duplicated internal pattern.

## Strategic Shifts in This PR

None — R12 stayed inside its originally brainstormed scope. The one deliberate exclusion,
called out explicitly in both the design doc and this PR, is `synlynk/db.py`'s own
circular-shim pattern (late in-body re-imports back into `synlynk`, e.g.
`detect_remote_owner_repo()`'s self-import). It looks similar to the `_pkg()` duplication
but is a distinct problem shape and needs its own investigation — tracked as a fresh
follow-up issue rather than folded into this refactor.

## What R12 Shipped

**A shared lazy-import helper.** `synlynk/_lazy.py` now holds one `pkg(name, default=None)`
function, backed by `tests/test_lazy.py`'s three cases (attribute found, attribute missing →
default, `synlynk` not yet imported → default). It replaces 15 files' worth of duplicate
`def _pkg(...)` bodies — `context.py`, `costs.py`, `daemon.py`, `dispatch.py`, `doctor.py`,
`instructions.py`, `jobs.py`, `logs.py`, `platform_status.py`, `quota.py`, `scan.py`,
`story_provisioning.py`, `support_engineer.py`, `team.py`, `wizard.py` — each now does
`from synlynk._lazy import pkg as _pkg` instead of defining its own copy. Two of those
files (`logs.py`, `platform_status.py`) previously had no explicit default; consolidating
onto `pkg()`'s `default=None` was verified behavior-preserving call-site by call-site before
merging.

**Three extractions out of `__init__.py`:**
- ~80 lines of dead wizard-TUI scaffold (`_WIZ_SYNAPTIC_BLURB`, `_WIZ_PRODUCT_BLURB`,
  `_STAGE_LABELS`, `_STAGE_COLORS`, `_ROBOT_ASCII`) — confirmed unreferenced anywhere else
  in the tree before deleting.
- `LAUNCH_TASK_TEMPLATES` (a 15-entry template list) into `synlynk/launch_templates.py`.
- `_DB_SCHEMA` and `_DB_SCORES_VIEW` (the SQL DDL strings) into `synlynk/db_schema.py`,
  re-exported through `__init__.py` so `synlynk/db.py`'s existing late-import consumer and
  both dependent test files keep working unchanged.

**Net result:** `synlynk/__init__.py` dropped from 3,937 to 3,129 lines. `grep -rln "^def _pkg" synlynk/`
now returns nothing outside `_lazy.py` itself. `time python3 bin/synlynk.py --version` still
completes in ~0.1s — the new top-of-file imports in `__init__.py` don't reintroduce any of
the eager-loading `_load_legacy_imports()` was built to avoid.

## Process

Executed task-by-task via `superpowers:subagent-driven-development`, seven tasks total, each
run through the full pipeline: a Codex/Claude implementer, then an independent spec-compliance
reviewer, then an independent code-quality reviewer, before merging up through a stack of
worktrees. Two of the seven tasks needed a small direct fix from the PM/reviewer role after
review — a docstring reformatted with dropped punctuation in `launch_templates.py`, and a
worse docstring corruption (stray markdown-list dashes injected mid-paragraph) in
`db_schema.py` — both caught by spec-compliance review, fixed directly, and re-verified before
code-quality review. A recurring job-status false-negative (`circuit_breaker_tripped`, exit
-9) showed up again on the `_DB_SCHEMA` extraction task; per standing project practice the
status label was ignored in favor of direct git/diff/test inspection, which found a fully
correct commit underneath.

A whole-implementation final review (all 11 commits, full 3,425-test suite, both halves
independently re-run) came back READY FOR PR with no code-level blockers.

## What's Next

Filed `synlynk/db.py`'s circular-shim pattern as its own follow-up issue, deliberately kept
out of this PR's scope. Also opened a new goal/story to hold a future end-to-end FTUE/
onboarding rethink (greenfield, brownfield, and multi-repo discovery; the product's own value
narrative; terminal-vs-web framing; Vizor's role) — explicitly deferred until this review-
remediation wave closes, per the Brainstorm-First Policy: no design work starts until that
future brainstorm session runs.

Refs goal-079e2f37.
