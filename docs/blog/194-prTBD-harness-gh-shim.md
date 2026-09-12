---
title: "Harness-session gh shim (shared with synlynk exec)"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 194
pr: "TBD"
author: "synlynk team"
version: "0.19.0"
tags: [posts]
type: pr
---
## The Broader Goal at the End of the Previous PR

#1464 guarded `synlynk exec` with a temp PATH `gh` shim. Interactive harness shells still called host `gh` as nikhilsoman.

## Strategic Shifts in This PR

None. Spec #1436 §6.3: harness sessions fail closed on raw `gh`; humans at a login shell are unchanged.

## What This PR Shipped

- `synlynk/gh_shim.py`: shared guard. Harness markers (`SYNLYNK_HARNESS`, `CLAUDECODE`, `CURSOR_AGENT`, `CODEX_SANDBOX`, `GROK_BUILD`, `ANTIGRAVITY`, `GEMINI_CLI`). Not `CI` / `GITHUB_ACTIONS`.
- Durable install: `~/.synlynk/gh-shim/gh`. `synlynk gh --shim-env` / `--shim-install`.
- `synlynk exec` uses the same module and sets `SYNLYNK_HARNESS=1`.
- Tests in `tests/test_gh_shim.py`.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Raw `gh` in a detected harness session cannot silently use Nikhil's keyring.

## Strategic Note: The Goal at the End of This PR

Sessions must `eval "$(synlynk gh --shim-env)"`. Login-shell `gh` for Nikhil still pass-through.