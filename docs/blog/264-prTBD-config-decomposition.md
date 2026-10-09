---
title: "gh:#2101 — Splitting config.json Into Workspace, Billing, and Policy Files"
date: 2026-10-09
series: "Building the OS for Multi-Agent Development"
post: 264
pr: "#TBD"
status: open
author: "synlynk team"
version: "unreleased"
tags: [posts]
type: pr
---

# gh:#2101 — Splitting config.json Into Workspace, Billing, and Policy Files

## The Broader Goal at the End of the Previous PR

A single `.synlynk/config.json` had been accreting unrelated concerns for
months: workspace identity, harness billing rates, and policy/enforcement
settings all lived in one flat dict. Nothing enforced a boundary between
"who is this repo" and "how is cost calculated" and "what does the merge
gate require" — any module could read or write any of it, and a malformed
billing edit could corrupt workspace identity in the same file. gh:#2101
scoped the fix: split the legacy file into `workspace.json`, `billing.json`,
and `policy.json`, migrate existing repos automatically and idempotently,
and keep `load_config()` as a facade so most call sites don't need to
change at all.

## Strategic Shifts in This PR (if any)

No strategy change from the committed design
(`docs/superpowers/specs/2026-10-09-config-decomposition-design.md`) and plan
(`docs/superpowers/plans/2026-10-09-config-decomposition-plan.md`). One
scope correction did surface during final review, documented below.

## What This PR Shipped

- `config_schema.py` split into `WORKSPACE_SCHEMA` and `BILLING_SCHEMA`,
  and extended the existing policy schema with `qa_gate_mode`, `roles`,
  `story_classification`, and `sentinel`.
- `load_workspace()` / `load_billing()` in `synlynk/__init__.py`, plus a
  rewritten `load_config()` that splits-then-remerges them as a facade —
  existing callers reading `load_config()` see the same merged dict as
  before.
- One-time migration: `migrate_legacy_config_if_needed()` splits a legacy
  `config.json` into the three new files, renames the original to
  `config.json.bak`, and no-ops on a second call (idempotent).
- `.gitignore` entries for `.synlynk/workspace.json` and
  `.synlynk/billing.json`.
- This repo's own dogfooded migration: `.synlynk/config.json` split locally,
  `config.json` removed from git tracking, the three new files added.
- All 15 plan tasks landed with a clean full-suite run at each checkpoint
  (baseline: 4029 passed / 3 skipped / 5 xfailed).

### The bug found in final review

A dispatched final-review pass (per subagent-driven-development's
mandatory end-of-plan code-quality review) surfaced a real data-loss bug
that none of the 15 planned tasks had covered: `add_repo()` in
`synlynk/workspace.py` read `workspace.json` directly, defaulting to `{}`
when the file didn't exist, and wrote back only `repo_id`. Because
`migrate_legacy_config_if_needed()` treats the mere *existence* of
`workspace.json` as "already migrated," calling `add_repo()` on a
not-yet-migrated repo created a stub `workspace.json` that permanently
blocked proper migration — every other field in the legacy `config.json`
(budget, harness_billing, roles, qa_gate_mode) became silently unreachable.

This was fixed as a scoped fix-forward, dispatched to Codex
(`dispatch/codex/job-2b7777cf`) with an explicit spec limiting the change
to `synlynk/workspace.py` and its test file: before touching
`workspace.json`, `add_repo()` now reuses the existing pure
`_split_legacy_config()` helper to perform the full split, writes
`billing.json`/`policy.json`, and renames the legacy file to
`config.json.bak` — mirroring what `migrate_legacy_config_if_needed()`
already does elsewhere. A new regression test
(`test_add_repo_splits_legacy_config_before_writing_workspace`) covers both
the full split and idempotency on a second call.

### The scope gap, tracked rather than silently expanded

The same review found that 8 modules (`autonomy.py`, `agent_store.py`,
`handover.py`, `github_app_auth.py`, `governs_engine.py`,
`state_registry.py`, `team.py`, `version_policy.py`) still read
`.synlynk/config.json` directly with no split-file fallback — the plan's
implicit claim of exhaustive call-site coverage was inaccurate. Rather than
expand this PR's scope to cover them, that gap is filed as
[gh:#2147](https://github.com/nikhilsoman/synlynk/issues/2147), a tracked
follow-up.

## Brainstorm Visuals Used

None — this followed the committed design and plan directly.

## What This Achieved on the Path to Autonomy

Config state now has enforceable boundaries: billing can be edited without
risking workspace identity corruption, and policy enforcement settings live
separately from both. The facade means most of the ~138-module codebase
didn't need to change at all, and the one real gap this created (`add_repo`)
was caught by the review discipline the plan already required, not by a
production incident.

## Strategic Note: The Goal at the End of This PR

gh:#2147's 8 remaining call-sites are the next piece of this decomposition
— they should gain the same split-file fallback `add_repo()` now has, most
likely via a direct `load_config()`/`load_workspace()` facade swap rather
than new split logic, since the facade already exists.
