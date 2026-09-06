---
title: "Documenting the Harness Session gh Shim Environment"
date: 2026-09-06
series: "Building the OS for Multi-Agent Development"
post: 195
pr: "TBD"
---

## The Broader Goal at the End of the Previous PR

PR #1464 shipped the `synlynk exec` PATH shim to guard child dispatches against accidental host GitHub credential leakage. In parallel, issue #1436 and its sibling implementation establish the session-level `gh` shim via `synlynk gh --shim-env` (`~/.synlynk/gh-shim/gh`). While the underlying shim mechanism prevents raw `gh` calls from silently authenticating as the human operator (`nikhilsoman`), harness instruction files needed to be aligned across the fleet so interactive sessions know to activate the shim and follow the updated identity protocol.

## Strategic Shifts in This PR

None. Spec #1436 §6.3 / Hole B: document the `synlynk gh --shim-env` environment setup as the standard rule across all agent instruction files, ensuring interactive harness sessions fail closed on unauthorized raw `gh` invocations without altering the operator's personal login shell.

## What This PR Shipped

Added an identical, standardized rule across the human-maintained sections of all four primary harness directive files (`GROK.md`, `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md`):
- In a harness/session shell, prepend the synlynk gh shim: `eval "$(synlynk gh --shim-env)"` (or equivalent PATH prepend of `~/.synlynk/gh-shim`).
- Then raw `gh` is refused unless a role `GH_TOKEN` is already injected, `SYNLYNK_GH_ROLE` is set, or `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1`.
- Prefer `synlynk gh --role <role> -- …` for session GitHub writes.
- Nikhil at a normal login shell (no harness env) is unchanged.

## Brainstorm Visuals Used

None. Spec: `docs/superpowers/specs/2026-09-06-workspace-agent-identity-routing-design.md`.

## What This Achieved on the Path to Autonomy

Unifies harness guidance across Claude, Codex, Grok, and Agy around the new session shim environment. With the shim prepended, agents operating in harness shells cannot accidentally fall through to host credentials on unauthenticated `gh` calls, establishing fail-closed safety while preserving seamless role-scoped operations via `synlynk gh --role`.

## Strategic Note: The Goal at the End of This PR

With both child dispatch (`synlynk exec`) and interactive harness session shells documented to use the `gh` shim, Hole B in #1436 identity routing is fully closed at the documentation and harness guidance level.
