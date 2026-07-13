---
title: "PR #204/#205/#207 — Local Agent: oMLX Driver, Capability Seeding, and Real-Hardware Tests"
date: 2026-07-13
series: "Building the OS for Multi-Agent Development"
post: 53
pr: "#204/#205/#207"
merged: 2026-07-13
---

## The Broader Goal at the End of the Previous PR

BS-8 had already shipped the Business Goal hierarchy, and GOVERNS was in the middle of
rolling out the seven-stage vocabulary that sits above it. The next open thread was not
another abstraction layer; it was practical dogfooding: prove that synlynk could route
real implementation work to a zero-cost local agent without breaking the existing
capability-to-quota-to-cost pipeline.

## Strategic Shifts in This PR

The main pivot happened before code was written. Ornith was initially assumed to be
GGUF-only, which would have pointed the local-agent dispatch story toward `llama.cpp`.
During the brainstorm and spec pass, that assumption turned out to be wrong: the model
has MLX conversions, so the recommendation changed mid-brainstorm from `llama.cpp` to
oMLX. That mattered because it kept the feature inside the existing OpenAI-compatible
agent-subprocess model instead of inventing a new driver path.

## What This PR Shipped

### Task Group 1: driver wiring

PR #204 wired `local` as an Aider subprocess over oMLX. The implementation keeps the
existing dispatch architecture intact: `_preflight_local()` checks the oMLX endpoint,
`AGENT_CAPABILITY_BASELINES["local"]` uses the same shape as the other agents, and the
job still runs as a normal CLI subprocess inside the worktree.

### Task Group 2: capability seeding and concurrency guard

PR #205 added the narrow starter envelope. `synlynk local doctor` seeds moderate
capability scores for the granular coordinates the spec called out first, so the local
agent shows up for docs/testing execute-stage work before it has earned broader trust.
The same PR also introduced the `local_concurrency` guard so in-flight local jobs are
bounded by hardware, not by a spend cap.

### Task Group 3: two-tier tests

PR #207 added the test split the spec called for. The standard CI path stays mocked and
portable, while the opt-in `@pytest.mark.local_hardware` tier exercises a real
`omlx serve` instance with a live roster. That keeps the PR gate deterministic while
still leaving room for real inference validation on Apple Silicon or a later hosted
runner.

The design and implementation were tracked against
`docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md`. No separate
brainstorm visuals were used for this feature; the decision trail lived in the spec and
plan text.

## What This Achieved on the Path to Autonomy

This is the first route in synlynk that can route low-risk implementation work to a
zero-marginal-cost local model while still preserving the same dispatch, capability, and
verification contract used for paid agents. The important part is not just that `local`
exists, but that it was added without a parallel taxon or a bespoke driver stack.

## Strategic Note: The Goal at the End of This PR

The next thing to watch is real local-agent job completions. Once those arrive, we can
decide whether the starter whitelist should widen, and whether a second Linux/Windows
driver path should be added for non-Apple-Silicon environments. Until then, `local`
should stay narrow, cheap, and observable.
