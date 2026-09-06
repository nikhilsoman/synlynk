---
title: "Auto-PRs were still the human, even when the child was the bot"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 183
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

#1436's spec recorded that dispatched `--requires-gh-write` children already use role Apps, while the parent process that runs `gh pr create` after the job still used host `nikhilsoman`. That is how merge/review jobs opened noise PRs as the human.

## Strategic Shifts in This PR

Nikhil signed off on the spec in session. This PR implements Hole A only: parent auto-PR identity. Interactive `synlynk gh --role` (Hole B) is not in this PR.

## What This PR Shipped

`_role_gh_env_for_job` injects the role App installation token and an isolated `GH_CONFIG_DIR` into parent-process `gh pr list` / `gh pr create`. If no role/token is available, behavior is unchanged (host `gh`) with a later fail-closed follow-up.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md` (#1451).

## What This Achieved on the Path to Autonomy

Auto-finalized PRs from a qa/dev/pm job should show the role bot as author, not `nikhilsoman`.

## Strategic Note: The Goal at the End of This PR

Hole B (interactive host `gh`) and a live qa `--approve` of a bot-authored PR remain.
