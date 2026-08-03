---
decision_id: dec-fleet-operability-brainstorm
topic: "Fleet operability brainstorm — Supported/Proven tiers, Core 4, matrix gate, sequencing"
date: 2026-08-02
panel: [nikhil, grok]
status: approved
---

## Decision

Lock product tiers **Supported** (fail-closed doctor + dry matrix) and **Proven** (Supported + live matrix within 7 days); **Core 4** fleet (claude/agy/codex/grok) with local experimental until green; codex builder-only until relevant cells Proven; hard freeze on fleet-parity features until `synlynk selftest --matrix` Phase 1 lands; live budget $10/week; doctor FAIL on missing instruction, nested state.db, TC-2, TC-3; ban UNKNOWN as terminal job status; refuse nested product state.db; sequence matrix → Core 4 GH-write + grants epic → native harness go/no-go after first Proven week. Design: `docs/superpowers/specs/2026-08-02-fleet-operability-design.md`.

## Rationale

Decide panel (dec-2f979483) was unanimous that full-fleet operability is not supported today due to false-greens. Brainstorm chose tiered claims, a hard truth gate, and deferred side-effect invest until matrix can accept them.

## Spec

`docs/superpowers/specs/2026-08-02-fleet-operability-design.md`
