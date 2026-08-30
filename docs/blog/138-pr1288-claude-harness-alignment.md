---
title: "PR #1288 — Aligning Claude Baseline Roles with PM/Deploy Governance and Resolving Fleet Contradictions"
date: 2026-08-30
series: "Building the OS for Multi-Agent Development"
post: 138
pr: "#1288"
merged: 2026-08-30
---

## The Broader Goal at the End of the Previous PR

With Agy headless parity landed in PR #1286, the final standing fleet contradiction was Anthropic Claude's programmatic classification as a "builder" in `synlynk/_constants.py` despite project governance strictly locking Claude into a PM/deployer role.

## Strategic Shifts in This PR

Having Claude listed as a "builder" caused automated capability scoring to consider Claude an implementation candidate, conflicting directly with `CLAUDE.md` and `docs/harness-capability-baseline.md`. Aligning `_constants.py` with governance guarantees that autonomous routing respects the PM/implementer division of labor.

## What This PR Shipped

1. **Updated Baseline Roles:**
   - In `synlynk/_constants.py`, updated `HARNESS_CAPABILITY_BASELINES["claude"]["roles"]` from `["architect", "builder"]` to `["architect", "pm"]`.
   - Preserved `can_gh_write: True` so Claude can execute PM, deploy, and PR review workflows.
2. **Capability Baseline Documentation:**
   - Updated `docs/harness-capability-baseline.md` to formally document Claude's role alignment.
3. **Verification Tests:**
   - Added `test_claude_harness_alignment_update_baseline` in `tests/test_agent_cli.py`.

## What This Achieved on the Path to Autonomy

All four core harnesses (Codex, Grok, Agy, Claude) now possess fully aligned, verified baseline contracts and execution models.
