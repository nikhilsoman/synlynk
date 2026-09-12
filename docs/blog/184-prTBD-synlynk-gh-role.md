---
title: "synlynk gh --role so interactive writes are not the human"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 184
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

#1452 closed Hole A: parent auto-PR uses the job App token. Interactive Grok/Claude shells still ran raw `gh` as `nikhilsoman`.

## Strategic Shifts in This PR

None. Spec #1436 Hole B: `synlynk gh --role <role> -- …`.

## What This PR Shipped

`synlynk gh --role qa -- pr view 1452` (and `pr create`, `pr merge`, …) injects the role App token and an isolated `GH_CONFIG_DIR`. Unknown roles and missing tokens fail closed unless `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`. This does not wrap every accidental raw `gh` in the shell; sessions must call `synlynk gh` instead of `gh`.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Interactive GitHub writes have a role-token path. Remaining: make it the default (deny raw host `gh` in agent sessions), optional qa `actions: write`, live qa `--approve` of a bot-authored PR.

## Strategic Note: The Goal at the End of This PR

Use `synlynk gh --role` for all agent GitHub writes. #1436 stays open until that discipline is default, not optional.