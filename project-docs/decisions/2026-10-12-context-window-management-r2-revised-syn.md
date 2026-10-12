<!-- generated - source of truth is state.db -->
---
decision_id: dec-0d7e75e0
topic: "Context-window management R2 (revised): synthesize R1's findings, now FULLY consolidated (project-docs/decisions/2026-10-12-context-window-management-r1-audit-your.md plus project-docs/decisions/2026-10-12-context-window-management-r1-addendum-grok-codex.md), into one cohesive modification to synlynk's instruction-writer for each harness (CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md templates init() generates), plus a shared task-boundary compaction-trigger and context-pack design. CONSOLIDATED STATE (supersedes the original R2 round's treatment of Codex/Grok as symmetric open gaps): budget signals belong in the dispatch-wrapper layer not model-side (confirmed all harnesses); Agy resends its full instruction file every turn (confirmed, highest-ROI restructuring target); Claude is per-session (confirmed, lower urgency); Grok is NOW CONFIRMED per-turn resend (direct prompt_tokens growth evidence in its own session logs) -- treat as Agy-tier for cost-model purposes, same urgency; Grok's GROK.md is not even a recognized project-rule filename for Grok's harness (it loads AGENTS.md/Claude.md instead) -- the instruction-writer must account for actual per-harness filename discovery, not assumed filenames; Codex was probed via deliberate mid-session AGENTS.md mutation and found NO EVIDENCE of per-turn resend (sentinel never resurfaced across 4+ later tool actions) -- treat as session-tier for cost-model purposes pending a stronger confirmation, not worst-case Agy-tier by default. Design the instruction-writer modification to reflect these now-closed gaps rather than defaulting every unconfirmed harness to worst-case. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8)."
date: 2026-10-12
panel: [claude, agy, codex]
status: approved
---

## Topic
Context-window management R2 (revised): synthesize R1's findings, now FULLY consolidated (project-docs/decisions/2026-10-12-context-window-management-r1-audit-your.md plus project-docs/decisions/2026-10-12-context-window-management-r1-addendum-grok-codex.md), into one cohesive modification to synlynk's instruction-writer for each harness (CLAUDE.md/GEMINI.md/AGENTS.md/AI_INSTRUCTIONS.md templates init() generates), plus a shared task-boundary compaction-trigger and context-pack design. CONSOLIDATED STATE (supersedes the original R2 round's treatment of Codex/Grok as symmetric open gaps): budget signals belong in the dispatch-wrapper layer not model-side (confirmed all harnesses); Agy resends its full instruction file every turn (confirmed, highest-ROI restructuring target); Claude is per-session (confirmed, lower urgency); Grok is NOW CONFIRMED per-turn resend (direct prompt_tokens growth evidence in its own session logs) -- treat as Agy-tier for cost-model purposes, same urgency; Grok's GROK.md is not even a recognized project-rule filename for Grok's harness (it loads AGENTS.md/Claude.md instead) -- the instruction-writer must account for actual per-harness filename discovery, not assumed filenames; Codex was probed via deliberate mid-session AGENTS.md mutation and found NO EVIDENCE of per-turn resend (sentinel never resurfaced across 4+ later tool actions) -- treat as session-tier for cost-model purposes pending a stronger confirmation, not worst-case Agy-tier by default. Design the instruction-writer modification to reflect these now-closed gaps rather than defaulting every unconfirmed harness to worst-case. Full spec at docs/superpowers/specs/2026-10-12-context-window-optimization-design.md (GOVERNS story-c04f64b1 / goal-e79062e8).

## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

**Position: Approve — three-tier instruction-writer, generated per-harness filename discovery, dispatch-wrapper budget signals, task-boundary compaction hook.**

The consolidated R1 findings resolve what was genuinely ambiguous in the original R2 scope, so the design should stop treating Codex/Grok symmetrically:

1. **Tiered restructuring priority.** Agy and Grok both confirmed per-turn full-instruction resend — they're the actual cost driver and belong in the same "highest-ROI" bucket: the instruction-writer should generate a short, stable preamble + separate on-demand reference doc for these two, since every turn pays for every line. Claude (per-session) and Codex (no resend evidence across 4+ tool actions) are session-tier — a single richer file costs them once, not N times, so splitting their content buys less and risks losing context continuity for no real savings. Don't force one template shape across all four; the generator should branch on confirmed resend behavior.

2. **Filename discovery must be harness-real, not harness-assumed.** The Grok/GROK.md finding is the sharpest correction here — Grok doesn't even read a file by that name, it falls through to AGENTS.md/CLAUDE.md. `init()`'s template dispatch needs an explicit per-harness filename table (verified against actual harness docs/behavior, not naming convention), and should fail loudly or warn if asked to write a file the target harness won't load — otherwise we ship instructions nobody reads, silently.

3. **Budget signals stay in the dispatch wrapper.** All harnesses confirmed this — don't duplicate budget/compaction logic into model-side instruction text at all. One shared context-pack/compaction-trigger mechanism at the wrapper layer, referenced identically from every template, rather than four divergent copies.

4. **Don't over-engineer Codex's tier on a single probe.** One mid-session mutation test is suggestive, not proof; keep Codex at session-tier as the current default but flag it for a second independent confirmation method before fully closing the gap, per the spec's own evidentiary standard for the Empirical Capability Assessment Policy.

This keeps the modification scoped to what R1 actually closed, avoids worst-casing Codex, and fixes a real correctness bug (Grok's filename) that a symmetric-gap treatment would have missed entirely.

### agy
[model=default; version=1.3.3]

Row 1: docs: consolidate Codex mid-session AGENTS.md mutation probe (job-3cad6bd5)
Row 2: BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform] <!-- id:story-bs7-interop -->

### Analysis: R2 Consolidated Synthesis & Instruction-Writer Redesign

The closed empirical gaps establish an asymmetrical, tier-based architecture across the fleet:
1. **Per-Turn Tier (Agy, Grok):** Both resend their active rule file on every single model turn. Grok does not load `GROK.md` at all; it parses `AGENTS.md` (or `CLAUDE.md`). Bloat here incurs a quadratic token penalty over multi-turn jobs ($O(\text{turns} \times \text{size})$).
2. **Per-Session Tier (Claude, Codex):** Loaded once at initialization (validated by Codex’s mutation probe and Claude’s native design). Subordinate files incur negligible per-turn overhead ($O(1)$).
3. **Control-Plane Decoupling:** Context budget signals belong strictly in `synlynk`’s dispatch wrapper (`cost_entries` and output telemetry), not via fragile prompt injection.

#### 1. Per-Harness Instruction-Writer Architecture
`synlynk init` must stop emitting monolithic duplications and switch to an **index-plus-pointer** pattern optimized by harness tier and filename discovery:
- **Agy (`GEMINI.md`):** Radically minify to `< 35` lines. Strip inline protocols (SOPs, tables, cost rubrics). Retain identity, core role, and explicit file pointers (`docs/sop/`) fetched only on demand.
- **Grok & Codex (`AGENTS.md`):** Grok and Codex share `AGENTS.md`. Maintain a ultra-lean core root `< 40` lines covering identity, attribution, and pointers. Remove all harness-agnostic prose. Do not emit a phantom `GROK.md`.
- **Claude (`CLAUDE.md`):** Keep a lean index file referencing sub-rules and nested directory configs, leveraging Claude Code’s native directory scoping.
- **Shared (`AI_INSTRUCTIONS.md`):** Maintain as the canonical, lazy-loaded reference document rather than inlining it into `.synlynk/context.md`.

#### 2. Task-Boundary Compaction Trigger & Context Packs
- **Wrapper Compaction:** The dispatch wrapper evaluates accumulated tokens at task boundaries (job completion, story close, PR check). When exceeding a threshold (e.g., 60% context window), the wrapper executes `/compact` or `/clear` before the next handoff.
- **Task-Specific Context Packs:** Replace the monotonic dumping of `todo.md`/`memory.md`/`roadmap.md` in `generate_context()` with `.synlynk/context-packs/<job-id>.md`. The pack injects only the targeted story, active acceptance criteria, and relevant file paths.

### Position
I strongly recommend **Approach C (Asymmetric Hybrid)**: update the instruction-writer to generate ultra-compact, stub-indexed directive files tailored strictly to each harness's discovered filenames (`GEMINI.md` for Agy, `AGENTS.md` for Grok/Codex, `CLAUDE.md` for Claude), enforce dispatch-wrapper context tracking to trigger preemptive task-boundary `/clear` operations, and replace full-stack context generation with scoped per-job context packs.

### codex
[model=default; version=codex-cli 0.162.1]

The consolidated findings point to two distinct design concerns: how much instruction text each harness resends, and where runtime budget signals belong. Keep budget signals in the dispatch wrapper; do not add them to model-side instruction files.

Restructure the instruction writer around the filenames each harness actually discovers. The templates generated by `init()` should produce a concise, stable shared core in `AI_INSTRUCTIONS.md`, with harness-specific files containing only what discovery requires and what genuinely differs. Prioritize reducing repeated instruction payload for Agy and Grok, both confirmed to resend their full instruction file each turn. Claude and Codex are session-tier based on current evidence, so their templates can retain more detail without imposing the same per-turn cost. Preserve uncertainty explicitly: Codex’s probe found no resend across four later tool actions, but that is not definitive proof of session-only behavior.

Do not assume a `GROK.md` file is loaded. The writer should target Grok’s observed discovery behavior (`AGENTS.md`/`Claude.md`) and verify generated files against each harness’s real lookup rules. Otherwise, a well-designed template could be silently ignored.

Add a shared task-boundary compaction trigger and context-pack design. At a task boundary, detect whether accumulated context warrants compaction, then preserve a compact, reusable pack: current objective and decisions, relevant findings with evidence, changed files and verification state, unresolved work, and constraints that must survive. This gives each harness a consistent handoff while avoiding repeated setup prose. The trigger should be boundary-based and evidence-driven, not an instruction asking the model to monitor a token budget that belongs to the wrapper.

**Position: adopt the consolidated, harness-aware design. Treat Agy and Grok as the urgent per-turn cost targets, Claude and Codex as session-tier pending stronger evidence, and make filename discovery plus shared task-boundary context packing explicit requirements of the instruction-writer change.**

## Synthesis
Decision: Adopt the consolidated asymmetric design. The instruction-writer's per-harness template generation branches on confirmed resend-tier, not role: Agy and Grok are per-turn-resend tier (highest-ROI target — minify each to a lean, stable core of identity/attribution/pointers, push all SOP/protocol detail into lazily-referenced docs so it isn't paid on every turn), while Claude and Codex stay session-tier (richer inline content is acceptable since it's paid once, not N times) — Codex's session-tier status is provisional pending a second, independent confirmation method, explicitly flagged as such in the generator's own output/comments rather than silently treated as settled. Filename discovery becomes an explicit, verified-per-harness table rather than a naming convention: no `GROK.md` is emitted since Grok doesn't load it — Grok targets `AGENTS.md` (shared with Codex), and the writer should warn/fail loudly if it's ever asked to emit a file a harness's discovery won't pick up. Budget/compaction logic is removed from all model-side instruction text and lives solely in the dispatch-wrapper layer (`cost_entries`/telemetry), with one shared task-boundary compaction trigger and context-pack mechanism (replacing monolithic `todo.md`/`memory.md`/`roadmap.md` concatenation with scoped per-job packs: objective, decisions, evidence, changed files/verification state, open work, must-survive constraints) referenced identically from every harness template rather than duplicated four ways. This scope change — and Codex's still-open second-confirmation item — should be written into the design spec and filed as a follow-up tracked under story-c04f64b1/goal-e79062e8 before implementation proceeds.

## Decision
Decision: Adopt the consolidated asymmetric design. The instruction-writer's per-harness template generation branches on confirmed resend-tier, not role: Agy and Grok are per-turn-resend tier (highest-ROI target — minify each to a lean, stable core of identity/attribution/pointers, push all SOP/protocol detail into lazily-referenced docs so it isn't paid on every turn), while Claude and Codex stay session-tier (richer inline content is acceptable since it's paid once, not N times) — Codex's session-tier status is provisional pending a second, independent confirmation method, explicitly flagged as such in the generator's own output/comments rather than silently treated as settled. Filename discovery becomes an explicit, verified-per-harness table rather than a naming convention: no `GROK.md` is emitted since Grok doesn't load it — Grok targets `AGENTS.md` (shared with Codex), and the writer should warn/fail loudly if it's ever asked to emit a file a harness's discovery won't pick up. Budget/compaction logic is removed from all model-side instruction text and lives solely in the dispatch-wrapper layer (`cost_entries`/telemetry), with one shared task-boundary compaction trigger and context-pack mechanism (replacing monolithic `todo.md`/`memory.md`/`roadmap.md` concatenation with scoped per-job packs: objective, decisions, evidence, changed files/verification state, open work, must-survive constraints) referenced identically from every harness template rather than duplicated four ways. This scope change — and Codex's still-open second-confirmation item — should be written into the design spec and filed as a follow-up tracked under story-c04f64b1/goal-e79062e8 before implementation proceeds.

> Signatures: see 2026-10-12-context-window-management-r2-revised-syn.json
