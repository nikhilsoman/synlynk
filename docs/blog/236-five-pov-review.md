---
title: "Five Lenses on synlynk — A Measured Deep Review"
date: 2026-10-02
series: "Building the OS for Multi-Agent Development"
post: 236
pr: "1913"
status: published
author: "synlynk team"
version: "0.25.0"
tags: [posts, strategy, review]
type: story
---

## The Broader Goal at the End of the Previous PR

v0.25.0 "Sovereign Silicon" shipped local oMLX dispatch with $0 cost on Apple Silicon, tier-0
auto-routing, and an OpenRouter gateway preview. The goal was still fully autonomous
multi-agent dispatch across Claude, Codex, Agy, Grok, and local.

## Strategic Shifts in This PR

No code changed. This PR asks whether that goal is the right one to pursue next. The review
looks at synlynk as a developer would, as an architect, as a founder of an adjacent company
(OpenRouter, OpenClaw, Nous Research), as a VC analyst, and as an AI media creator. Its
conclusion: the next milestone should be **external users and trust**, not more surface area.

## What Shipped

- `docs/strategy/2026-10-02-five-pov-review.md`. Every metric in it was measured on the day,
  not copied from earlier docs: ~80.7K LOC, 155 commands, 3,667 tests, 831 merged PRs,
  21 LIVE incidents, 1 star.
- A ranked list of architecture changes:
  - a `HarnessAdapter` protocol
  - splitting the dispatch pipeline into stages
  - structured telemetry and a job status based on verified side effects
  - state consolidation with garbage collection
  - safe-by-default permissions
  - separating the core commands from optional packs
- Version drift recorded: `VERSION`, the README badge, and the CHANGELOG all disagree.

## Brainstorm Visuals

None.

## Progress Toward the Goal

The dispatch engine is real and heavily dogfooded. The July review's two-dispatch-paths
finding is now fixed. The product layer (onboarding, focus, trustworthy status) is still not
ready for a launch.

## The New Goalpost

Settle on one identity: a neutral control plane that routes coding tasks across vendors and
local models, and proves which choice is best. Then cut the core down to about 15 commands,
make the defaults safe, and get 10–20 external weekly users before v0.26.
