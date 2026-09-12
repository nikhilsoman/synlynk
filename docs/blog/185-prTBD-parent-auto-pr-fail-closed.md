---
title: "No token, no auto-PR — not nikhilsoman"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 185
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

#1453 shipped `synlynk gh --role`. Parent auto-PR already injected a role token when one existed (#1452) but still fell through to host `gh` when it did not.

## Strategic Shifts in This PR

None. Spec #1436: fail-closed skip of host `gh` for parent auto-PR unless `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`.

## What This PR Shipped

`_maybe_open_worktree_pr` skips `gh pr list` / `gh pr create` when the role App token is missing and the host-auth override is unset.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

A job without a cached App token no longer opens a PR as `nikhilsoman`.

## Strategic Note: The Goal at the End of This PR

#1436 still open for optional qa `actions: write`, a live qa `--approve` of a bot-authored PR, and making `synlynk gh` the default instead of raw host `gh`.