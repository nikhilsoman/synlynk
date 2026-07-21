---
title: "Docs — GitHub write routing (Grok only) + PR Review Discipline identity caveat"
date: 2026-07-21
series: "Building the OS for Multi-Agent Development"
post: 68
pr: "#432"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

synlynk's multi-agent workgroup rests on two process rules that were already written into every agent's harness fence: **capability-based task allocation** (route by skill) and **PR Review Discipline** (non-authoring agent reviews and merges). Those rules assumed that any dispatched agent could run the same `gh` surface, and that GitHub would treat different agents as different reviewers.

## Strategic Shifts in This PR (if any)

No product or code path change. This PR accepts two operational facts discovered while shipping PR #416 / #417 and codifies them as sanctioned policy (issues #423 option 3, #426 first bullet):

1. **Only Grok can complete headless GitHub write actions** today. Agy auto-denies the headless `command` permission class for external-mutating `gh` writes even with `--dangerously-skip-permissions`. Codex's `workspace-write` sandbox blocks egress to `api.github.com` by design.
2. **GitHub cannot enforce "non-authoring reviewer"** under the current auth model. Every dispatch-authored PR and every dispatched review run as the same GitHub user, so `gh pr review --approve` always fails with "Can not approve your own pull request."

The near-term resolution is document-the-reality, not separate bot identities or sandbox redesign.

## What This PR Shipped

Updated the canonical SOP strings in `synlynk/probe.py` (`_PR_REVIEW_SOP`, `_CAPABILITY_ALLOCATION_SOP`) and the live harness fences in `CLAUDE.md` and `GROK.md` (the project-root files that currently carry those sections):

| Change | Effect |
|---|---|
| New routing row: **GitHub write actions → Grok only** | Covers `gh pr review`, `gh pr merge`, `gh pr create`, `gh issue comment` |
| `#426` note under Capability-Based Task Allocation | Explains why Agy/Codex fail headless on mutating `gh` |
| `#423` note under PR Review Discipline | Non-authoring reviewer is dispatch process control, not GitHub enforcement |
| Sanctioned fallback | Formal COMMENT review + explicit approve checklist (PR #417 pattern), not `gh pr review --approve` |

`synlynk sync --repair-sops` / init will re-inject the updated blocks from `probe.py` for agents whose fences are missing those headers. GEMINI.md's current harness fence is contract/flags-only (no SOP table body yet); AGENTS.md is absent in this tree — both will pick up the new text when SOPs are next repaired or generated.

## Empirical proof of #426

This PR itself is part of the evidence trail: an earlier attempt to dispatch this exact docs-only task to Agy failed with the headless `command` permission auto-deny — even though the task needed no review/merge, only `gh pr create` at the end. Opening the PR from Grok is the working path the new policy describes.

## Brainstorm Visuals

None.

## Progress Toward Full Autonomous Multi-Agent Dispatch

Autonomy requires honest capability maps. Dispatch that routes PR review/merge/create to agents that structurally cannot complete those steps wastes jobs and erodes trust in the workgroup protocol. Codifying Grok-only GitHub writes and the COMMENT-review fallback closes two silent failure modes without pretending GitHub branch protection can see multi-agent identity.

## New Goalpost

Until separate GitHub identities (or Codex network-scoped sandbox / Agy command allowlisting) land, **any dispatch task that must mutate GitHub via `gh` goes to Grok**, and **every dispatch-authored PR review ends as COMMENT + approve checklist**, never formal `--approve`.
