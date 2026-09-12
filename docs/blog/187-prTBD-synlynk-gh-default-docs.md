---
title: "Documenting synlynk gh --role as the Default for GitHub Writes"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 187
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

PR #1453 implemented `synlynk gh --role <role> -- <gh-args>` to route interactive GitHub operations through role-scoped GitHub Apps, and PR #1454 ensured parent auto-PR creation fails closed rather than falling back to host `nikhilsoman` credentials. However, interactive agent sessions had not yet been formally instructed across harness files to make `synlynk gh --role` their mandatory default.

## Strategic Shifts in This PR

None. Spec #1436 §6.3 / Hole B: document `synlynk gh --role` as the required standard for all autonomous and interactive session GitHub writes, reserving `nikhilsoman` exclusively for Nikhil at the keyboard.

## What This PR Shipped

Added an identical, authoritative rule across all primary harness instruction files (`CLAUDE.md`, `AGENTS.md`, `GROK.md`, `GEMINI.md`):
- Autonomous and session GitHub writes (`gh pr create`, `gh pr merge`, `gh issue close`, `gh run rerun`, `gh pr review`) MUST use `synlynk gh --role <role> -- …` to authenticate as the role App rather than `nikhilsoman`.
- `nikhilsoman` is strictly reserved for Nikhil at the keyboard.
- Host `gh` keyring access is allowed only when `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`.
- qa APPROVE is the default when reviewer login ≠ PR author login, retaining the #423 comment-checklist fallback only for same-identity collisions.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Closes Hole B by establishing explicit harness discipline across all supported agent backends (Claude, Codex, Grok, Agy), preventing inadvertent persona leakage into the human operator's personal GitHub identity during interactive operations.

## Strategic Note: The Goal at the End of This PR

Harness instruction files now mandate role-scoped App authentication via `synlynk gh --role`. Remaining #1436 tasks include optional qa `actions: write` permission for workflow reruns and live verification of an App-authored PR approved by the qa bot.