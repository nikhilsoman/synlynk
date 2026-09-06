---
title: "The human GitHub login is still doing autonomous work"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 182
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

#1450 taught `synlynk pr check` to find a PR from a dispatch job branch. Review dispatch can now see CI. Identity was still wrong: PRs opened as `nikhilsoman`, while qa already reviewed and merged as `synlynk-synlynk-qa[bot]`.

## Strategic Shifts in This PR

#1436 is assessment, not a patch. The #423 “shared identity cannot approve” story is **stale for App-vs-human**: this session’s qa bot approved and squash-merged PRs authored by `nikhilsoman`. The remaining hole is host `gh` in interactive sessions and in the parent auto-PR path.

## What This PR Shipped

A design spec (`docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`) with a routing audit, live evidence table, charter vs `policy.json` drift, and an implementation queue that stays blocked until Nikhil signs off.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

We know which GitHub writes already use role Apps (dispatched `--requires-gh-write` children) and which still use the human keyring (parent finalize, interactive `gh`). qa `--approve` works.

## Strategic Note: The Goal at the End of This PR

Spec signed off → implement parent-token auto-PR and interactive `synlynk gh --role`, then drop comment-checklist as the default qa review.
