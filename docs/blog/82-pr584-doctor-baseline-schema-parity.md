---
title: "PR #584 — #339: When 'Green Across the Board' Meant the Checks Weren't Running"
date: 2026-07-29
series: "Building the OS for Multi-Agent Development"
post: 82
pr: "#584"
merged: 2026-07-29
---

## The Broader Goal at the End of the Previous PR

Coming out of the LIVE-3 recovery (PR #549) and the state-engine work, the standing priority was a pre-launch headless-capability audit across the agent fleet — confirming `synlynk doctor` could actually be trusted to say which agents support which dispatch flags, headless contracts, and network dependencies before that audit started trusting its output.

## Strategic Shifts in This PR

None planned as a pivot, but the PR itself exists because of one: issue #339 found that `doctor`'s TC-1/TC-2/TC-3/TC-5 checks were silently vacuous-passing for most agents. `AGENT_CAPABILITY_BASELINES` in `synlynk/_constants.py` had inconsistent per-agent schema — `claude` and `local` had `dispatch_flags` as a bare list, `codex` was missing it entirely, only `agy`/`grok` were dict-shaped with `valid_flags`/`invalid_flags`/`required_flags`. Checks silently skipped agents that didn't match the shape they expected instead of failing loudly.

## What This PR Shipped

Five fixes, all from the issue's own suggested plan:
1. A TC-0 schema-completeness meta-check that asserts every agent has the required keys in the required shape, failing loudly per-agent instead of silently skipping.
2. Normalized `dispatch_flags` to one dict shape across all five agents, backfilled with real values (e.g. `claude`: `--dangerously-skip-permissions` as a required flag, sourced from this project's own harness fence rather than guessed).
3. Added `headless_contract` and `network_deps` baselines for every agent.
4. Added `local` to `doctor.py`'s TC-5 file map with an explicit "no directive file, intentionally skipped" report line instead of silent omission.
5. Confirmed `synlynk doctor` output now genuinely differs per agent instead of being uniformly green.

Two rounds of correction followed non-authoring review from Grok. The first: normalizing `claude`/`local` to dict-shaped flags accidentally turned on a live `subprocess.run([agent, "--help"])` call inside `_preflight_dispatch`'s hot path for those two agents (previously it never fired for them, since their `valid_flags`/`required_flags` were always empty). That broke 5 tests mocking `Popen` but not probe.py's separate `subprocess.run`, and added real dispatch-time latency. The fix: read `compliance_status`/`active_flags` from the already-populated `harness_records` table instead of calling the CLI live — exactly the persisted-probe-then-consume-at-dispatch architecture #339 was arguing for in the first place, just not yet applied to this one path.

## Brainstorm Visuals Used

None — this was root-cause-driven from the issue text and existing test failures, not a design decision.

## What This Achieved on the Path to Autonomy

`synlynk doctor` output is now something the fleet-parity audit can actually trust. But merging this PR immediately introduced a new regression of its own (see PR #589) — a reminder that schema-normalization work touching every agent's baseline entry is exactly the kind of change that needs a full isolated-clone test run before merge, not a spot check on the agents that were the original focus.

## Strategic Note: The Goal at the End of This PR

Doctor/probe output is trustworthy again, but the fleet-parity audit itself (#332, #338, #340, #342, #347, #348, #419, #461) is still not started — it should proceed carefully now, given #339's own fix needed two follow-up corrections before it was actually clean.
