---
title: "gh:#1924 — Grok's Shell Capability Was Still Living in the Pre-#1277 World"
date: 2026-10-03
series: "Building the OS for Multi-Agent Development"
post: 240
pr: "1959"
issue: "1924"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, capability-routing, bugfix]
type: story
---

## The Broader Goal at the End of the Previous PR

The previous post (PR3, #1957) had just ported Grok onto the `HarnessAdapter` protocol,
encoding its known 402/session-expiry/sandbox-denial failure modes as adapter methods. The
goalpost going in to this PR was simply: keep moving down the strangler-pattern port list
toward Agy and Claude/local.

## Strategic Shifts in This PR

A real bug surfaced mid-migration and jumped the queue. This PR is a fix, not the next planned
port — but it's directly in-scope for #1924 because the bug it fixes lives in the same
capability-routing layer the adapter work depends on.

## What Was Wrong

`synlynk/capability_probe.py` still described Grok's pre-#1277 headless sandbox behavior: it
routed every shell-requiring dispatch away from Grok unless an explicit grant was supplied, and
its own Grok runtime probe independently defaulted shell capability back to `false` because
nothing ever set `SYNLYNK_GROK_SHELL_ENABLED`. Two stale assumptions compounding — the gate
variable was never being set in the first place, and even if it had been, the probe's own
flip-to-true path was blocked behind it a second time. The net effect: every shell-requiring
Grok dispatch was being silently rerouted to a different harness regardless of Grok's actual,
current sandbox permissions, which is exactly the kind of "capability-probed auto-reroute"
behavior this session had already observed firsthand on a live dispatch earlier in this same
migration effort.

## What This PR Shipped

- Flipped the Grok shell capability profile to `true` by default.
- Replaced the stale `SYNLYNK_GROK_SHELL_ENABLED` opt-in gate with an explicit
  `SYNLYNK_GROK_SHELL_DISABLED` opt-out — inverting the default from "blocked unless granted" to
  "allowed unless explicitly revoked," matching Grok's actual current sandbox behavior.
- Preserved `CAP_GH_WRITE=false` for Grok untouched — this fix is scoped to shell capability
  only; GitHub-write routing for Grok stays exactly as documented in the capability baseline
  (Codex-default, per #426).

## What Was Achieved Toward the Long-Arc Goal

This closes a gap between the capability-routing layer's stated model of Grok and Grok's actual
behavior — the same kind of drift the Harness Capability Reassessment Protocol exists to catch
on a cadence, caught here ad hoc because it blocked the adapter migration directly. With this
fixed, `GrokAdapter`'s shell-dependent dispatch paths (ported in the previous PR) now route
correctly instead of being silently rerouted around.

## The New Goalpost

Back to the plan: PR4 ports Agy next.

Refs #1924.
