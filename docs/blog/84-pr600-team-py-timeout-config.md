---
title: "PR #600 — Team Panel Queries Get Per-Agent Timeout Overrides"
date: 2026-07-30
series: "Building the OS for Multi-Agent Development"
post: 84
pr: "600"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 left the project with a sharper understanding of harness behavior and a canonical capability matrix, but one practical gap remained in the team workflow: `synlynk decide` still treated every panel query as if 120 seconds were enough for every agent and every prompt. That assumption is fine for short prompts, but it is not fine for Codex on the longer self-review prompts this repo now uses.

## Strategic Shifts in This PR

There was no broad strategy change here. This was a fast-follow cleanup on the team workflow itself: keep the existing default for short-running agents, but let the timeout vary by agent where the harness needs more headroom. The change stays intentionally narrow so it does not alter the behavior of unrelated dispatch paths.

## What This PR Shipped

`synlynk/team.py` now computes panel-query timeouts through a small helper instead of relying on a single hardcoded default. The new flow is:

1. Check whether the caller passed an explicit timeout.
2. If not, look up a per-agent override in `AGENT_PANEL_QUERY_TIMEOUT_SECONDS`.
3. Fall back to the existing 120-second default for agents without an override.

The constants live in `synlynk/_constants.py`, where Codex is currently assigned 300 seconds. That keeps the policy centralized and makes the override easy to extend later if another harness needs special handling.

The regression test in `tests/test_agent_quota_tracking.py` stubs `subprocess.run`, calls `_run_agent_sync()` for both Codex and Claude, and asserts that:

1. Codex receives the longer 300-second timeout.
2. Claude still uses the default 120-second timeout.

That test is deliberately narrow: it verifies the actual argument passed to the subprocess layer, not just an inferred helper return value.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

This removes a small but real brittleness in the panel-query path. The team consensus flow can now tolerate a slower, more demanding Codex prompt without turning an expected long think into a false failure. That matters because the harness only becomes reliable if its own internal coordination channels do not misclassify normal latency as an error.

## Strategic Note: The Goal at the End of This PR

The team workflow now has a per-agent timeout policy instead of a flat 120-second ceiling. Codex has more headroom for the longer prompts it actually needs, while other agents keep the original behavior unless the config explicitly changes. The next likely step, if needed, is to make the override table data-driven from config rather than code, but this PR keeps the implementation dependency-free and focused.
