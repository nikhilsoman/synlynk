---
title: "PR #589 — When #339's Own Fix Broke Every Codex Dispatch"
date: 2026-07-29
series: "Building the OS for Multi-Agent Development"
post: 84
pr: "#589"
merged: 2026-07-29
---

## The Broader Goal at the End of the Previous PR

PR #584 (#339) had just merged, and PR #588 (#583) was in its review cycle. The plan was to move straight from there into the CLAUDE.md regeneration.

## Strategic Shifts in This PR

Two consecutive dispatch attempts to Codex failed fast with `"a value is required for '--sandbox <SANDBOX_MODE>' but none was supplied"` — a brand-new regression, not a pre-existing issue, and the irony was immediate: it was introduced by #339's own baseline-normalization fix, the PR whose entire point was making the fleet's capability schema more correct.

Root cause, found by reading `synlynk/_constants.py` and `synlynk/dispatch.py` directly (Codex couldn't be dispatched to diagnose itself, since it was the thing that was broken): `AGENT_CAPABILITY_BASELINES["codex"]["dispatch_flags"]["required_flags"]` had been set to `["--sandbox"]`. `_dispatch_flags_for_agent()` appends every entry in `required_flags` as a bare CLI flag with no value-attachment mechanism — that's fine for boolean-style flags like `--dangerously-skip-permissions`, but `--sandbox` requires a value, and codex's actual sandbox mode was already being supplied correctly via `non_interactive_flags` (`-s workspace-write`). The bare, valueless `--sandbox` collided with that and broke the CLI invocation outright.

## What This PR Shipped

`required_flags` for `codex` set back to `[]`, with a comment explaining the constraint discovered here: `required_flags` may only ever contain flags that take no value, since there's no mechanism in `_dispatch_flags_for_agent()` to attach one. Anything requiring a value belongs in `non_interactive_flags` as adjacent tokens instead.

The fix itself had to be dispatched to Grok rather than Codex, for the obvious reason. Review then had its own wrinkle: Codex (the natural reviewer, having authored the underlying #339 work) was still non-functional, and Grok had authored this fix, so neither could serve as non-authoring reviewer. Agy took the review instead — and completed both the COMMENT review and the merge successfully, despite this project's own dispatch-time warning that Agy "cannot reliably complete GitHub-write actions headless" (#426). That warning is now demonstrably not universally true and is one of the things the eventual CLAUDE.md regeneration needed to reflect accurately rather than repeat unchanged.

Fix confirmed by successfully re-dispatching to Codex afterward.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Codex dispatch is unblocked again, and the `required_flags`-must-be-valueless constraint is now documented in the code itself rather than only discoverable by tracing a live failure. It's a second data point (after Agy's #589 review success) that the fleet's actual headless-write capability matrix has drifted from what's documented — reinforcing that the pending CLAUDE.md regeneration needs to describe current reality, not the last time someone tested it.

## Strategic Note: The Goal at the End of This PR

Both #339 and #583 are now fully landed and stable. The path is clear to attempt the CLAUDE.md regeneration again — except the #583 stale-refresh fix used to unblock it turned out to have its own formatting bug, discovered on this next attempt (see PR #591).
