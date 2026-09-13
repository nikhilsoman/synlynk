<!-- generated - source of truth is state.db -->
---
decision_id: dec-fcff261a
topic: "Synlynk v0.21.0 FTUE & Onboarding Journey: Fast Install, 3D Discovery, Context Validation, Unified 3-View Vizor Canvas, and GOVERNS First-Win SOP (see docs/superpowers/specs/2026-09-13-ftue-onboarding-journey-brainstorm-agenda.md)"
date: 2026-09-13
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Synlynk v0.21.0 FTUE & Onboarding Journey: Fast Install, 3D Discovery, Context Validation, Unified 3-View Vizor Canvas, and GOVERNS First-Win SOP (see docs/superpowers/specs/2026-09-13-ftue-onboarding-journey-brainstorm-agenda.md)

## Panel Inputs

### claude
Reviewing FTUE plans against synlynk's actual bottleneck: onboarding a new user/repo into a multi-harness workflow without them drowning in concepts (agents vs. harnesses, dispatch, worktrees, policy.json) before they see value.

**Fast Install** — table stakes; low risk, do it, but don't let it become the demo. If install still ends at a blank terminal, it hasn't moved the needle. Pair it with a `synlynk init --quickstart` that gets someone to a first dispatched task in under 5 minutes.

**3D Discovery** — this is the one I'd push back on hardest. A 3D visualization for first-time users adds novelty but not comprehension; new users need a mental model of "role → harness → task," not a spatial graph to navigate cold. This reads like a Vizor feature that got pulled forward into FTUE scope rather than an onboarding need. Recommend scoping it out of v0.21.0 and shipping it as a Vizor enhancement once someone already has context to interpret it.

**Context Validation** — high value, low glamour. Most FTUE failure modes in this codebase (see the daemon-persistence-gap, worktree GH App gap, stray state.db memories) are exactly "the environment silently isn't what the user assumes." A preflight check that surfaces those before the first real task is worth more than any visual feature here.

**Unified 3-View Vizor Canvas** — reasonable, but again this is a power-user consolidation, not a day-1 need. Sequence it after context validation, not before.

**GOVERNS First-Win SOP** — good instinct: define what a "first win" concretely is (first successful dispatch + merged PR) and design backward from it. This should be the spine the other four hang off of, not a parallel workstream.

My recommendation: split this into two releases. v0.21.0 ships Fast Install + Context Validation + First-Win SOP — the parts that reduce real friction and are cheap to verify. Defer 3D Discovery and the unified canvas to a follow-on Vizor-focused release once there's a validated first-win funnel to instrument against. Don't brainstorm 3D Discovery until the simpler pieces are shipped and you can see if users even ask for more visualization — bolting big UI investment onto an unvalidated funnel is the kind of scope-widening this project has flagged before (agent-design-principles memory: "opt-in, nothing breaks without it, measurable ROI required").

### codex
The agenda has a strong product thesis: onboarding should transmit intent, establish trust, and produce a tangible first win—not merely generate a repository report. The six pillars connect well, especially the progression from discovery to context correction, visualization, goal selection, and autonomous execution. Reusing existing `scan.py`, Vizor, readiness checks, and worktree protections also makes the proposal strategically coherent.

The main concern is scope and sequencing. A full domain/entity/flow reconstruction, rendered application catalog, cloud topology, GOVERNS synthesis, and verified PR within five minutes is ambitious and risks optimizing for spectacle over reliability. Semantic inference can misclassify business context; application and infrastructure views may imply facts that static configuration cannot prove. Automatically creating goals or dispatching changes could undermine trust if confidence, provenance, and safety boundaries are unclear. The distribution proposal also needs a security and maintenance plan, particularly for `curl | sh`, package publishing, binaries, updates, and rollback.

I recommend a staged, offline-first architecture. Use deterministic static analysis as the onboarding-critical path, with provenance and confidence labels on every discovery. Offer asynchronous LLM enrichment only as an optional enhancement. Adopt the hybrid terminal-plus-local-Vizor flow: terminal summary and defaults for speed, browser canvas for exploration, and a complete non-browser fallback. Make dirty-tree detection, isolated worktrees, explicit user confirmation, cancellation, and idempotent recovery hard gates. For GOVERNS, show one recommended first-win goal plus two alternatives, but require approval before writing state or dispatching work. Treat “PR created and verified” as the initial success metric; merging should remain outside the five-minute promise.

My position: approve the direction and authorize the multi-harness debate, but do not approve the six-day implementation plan as written. The panel should first lock a narrower v0.21.0 MVP centered on fast install, trustworthy static discovery, context validation, the existing three-view Vizor canvas, and one safe first-win workflow. Expand semantic inference and deeper application/cloud modeling only after instrumentation demonstrates that the core journey is accurate, comprehensible, and safe.

### grok
I'll read the FTUE agenda and current project context first so the panel recommendation is grounded in the spec, not a generic take.**Recommendation:** ship the 5-minute First-Win journey, but treat Vizor as the high-bandwidth canvas—not the control plane—and keep the first path fully offline, deterministic, and non-destructive.

Past FTUE specs failed in predictable ways: BS-17 interrogated in a TUI, cold-start dumped `workspace-canon.md` and stopped, zero-risk onboarding never reached domain discovery, and BS-6 left the three views as a dashboard instead of the onboarding surface. The six-pillar arc is the right correction. The risk is packing Stitch-quality screen catalogs, full cloud topology, LLM domain synthesis, and a real dispatched PR into one 5-minute path. That will miss the clock.

**Debate 1 — Hybrid, CLI-first.** Tubemaps, screen catalogs, and infra graphs do not fit an 80×24 terminal; that is why Grok’s canvas work exists. Developers still bounce if a CLI steals focus before any value. Fast TTY summary with chips, Enter to accept defaults, Space to open `localhost:27472/onboarding`. Headless/`--no-input` stays JSON-only and never waits on a browser.

**Debate 2 — Tiered scan.** Physical layout and entities must come from AST/manifests in under 10s, offline, idempotent, and `--json`. Domain labels (“Healthcare AI”) are the only place an LLM earns a call, and only as a non-blocking Tier 2 overlay. If the model is missing or the quota is gone, chips still confirm from heuristics. First Win must not depend on tokens.

**Debate 3 — Zero footprint plus scoped rollback.** Do not write outside `.synlynk/` without an explicit continue. Dirty trees fail closed or force a dedicated worktree—never a surprise stash of the user’s working copy. Snapshot `.synlynk/` so `synlynk rollback` is real. Repo-wide tarballs are surprising and slow.

**Debate 4 — One north-star, then a menu.** Three tracks before the first PR is interrogation fatigue again. Surface one high-confidence, additive candidate (tests or CI), dispatch it, celebrate the PR. Only then offer hygiene / architecture / deploy as optional next goals.

Cut v0.21.0 application-view depth: route cards and existing SVG infra, not live Stitch renders. Physical + logical canvases plus a green first PR are the release.

**Position:** Adopt Hybrid CLI→Vizor, tiered static-then-async-LLM discovery, fail-closed dirty-tree with `.synlynk/`-only writes and rollback snapshots, and a single First-Win GOVERNS goal. Defer rich screen/infra catalog depth and the three-tier goal menu until after that PR lands.

## Synthesis
Decision: v0.21.0 ships **Fast Install + Context Validation + a single GOVERNS First-Win goal + the existing three-view Vizor canvas** (routed CLI-first: terminal summary/defaults, `Space` opens the browser canvas, `--no-input` stays fully non-browser). Discovery is tiered and offline-first — deterministic AST/manifest scan is the onboarding-critical path (<10s, idempotent, `--json`), with any LLM-based domain/semantic labeling shipped only as a non-blocking, clearly-provenanced Tier 2 overlay that a token outage can never block. All writes stay fail-closed and scoped to `.synlynk/` with a real rollback snapshot; dirty trees force an isolated worktree rather than touching the user's working copy. GOVERNS presents one recommended, high-confidence, additive first-win goal (not a three-track menu) and requires explicit user approval before dispatching; success is defined as a verified, PR-created-and-checked outcome — merging is explicitly out of the 5-minute promise. **3D Discovery and deeper application/cloud-topology rendering are cut from v0.21.0 entirely** and deferred to a follow-on Vizor-focused release, gated on instrumentation from this release showing users actually want more visualization beyond the two-view canvas — consistent with the project's standing "opt-in, nothing breaks without it, measurable ROI required" bar for new surface area. Distribution (curl|sh, binaries, update/rollback path) needs its own security/maintenance plan before Fast Install ships and should be scoped as a fourth explicit workstream alongside the three above, not assumed as a detail of "Fast Install."

## Decision
Decision: v0.21.0 ships **Fast Install + Context Validation + a single GOVERNS First-Win goal + the existing three-view Vizor canvas** (routed CLI-first: terminal summary/defaults, `Space` opens the browser canvas, `--no-input` stays fully non-browser). Discovery is tiered and offline-first — deterministic AST/manifest scan is the onboarding-critical path (<10s, idempotent, `--json`), with any LLM-based domain/semantic labeling shipped only as a non-blocking, clearly-provenanced Tier 2 overlay that a token outage can never block. All writes stay fail-closed and scoped to `.synlynk/` with a real rollback snapshot; dirty trees force an isolated worktree rather than touching the user's working copy. GOVERNS presents one recommended, high-confidence, additive first-win goal (not a three-track menu) and requires explicit user approval before dispatching; success is defined as a verified, PR-created-and-checked outcome — merging is explicitly out of the 5-minute promise. **3D Discovery and deeper application/cloud-topology rendering are cut from v0.21.0 entirely** and deferred to a follow-on Vizor-focused release, gated on instrumentation from this release showing users actually want more visualization beyond the two-view canvas — consistent with the project's standing "opt-in, nothing breaks without it, measurable ROI required" bar for new surface area. Distribution (curl|sh, binaries, update/rollback path) needs its own security/maintenance plan before Fast Install ships and should be scoped as a fourth explicit workstream alongside the three above, not assumed as a detail of "Fast Install."

> Signatures: see 2026-09-13-synlynk-v0-21-0-ftue-onboarding-journey.json
